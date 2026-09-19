"""
Webhook ingestion service.

Responsibilities:
  1. HMAC-SHA256 signature verification (called before this service)
  2. Upsert the raw event into the appropriate event table
  3. Find or create the customer record
  4. Create or update a risk_case
  5. Run the diagnosis step
  6. Enqueue the agent Celery task
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.customer import Customer
from app.models.invoice import Invoice
from app.models.merchant import Merchant
from app.models.order_tracked import OrderTracked
from app.models.payment_event import PaymentEvent
from app.models.risk_case import RiskCase
from app.models.subscription_tracked import SubscriptionTracked
from app.services import diagnosis as diag
from app.services.audit import append_audit

logger = logging.getLogger(__name__)


# ── Customer resolution ────────────────────────────────────────────────────────

async def _resolve_customer(
    session: AsyncSession,
    merchant_id: uuid.UUID,
    rzp_customer_id: str | None,
    email: str | None,
    name: str | None,
    phone: str | None,
) -> Customer | None:
    """Find an existing customer or create one."""
    if not (rzp_customer_id or email or phone):
        return None

    # Try by Razorpay customer ID
    if rzp_customer_id:
        result = await session.execute(
            select(Customer).where(
                Customer.merchant_id == merchant_id,
                Customer.razorpay_customer_id == rzp_customer_id,
            )
        )
        customer = result.scalar_one_or_none()
        if customer:
            return customer

    # Try by email
    if email:
        result = await session.execute(
            select(Customer).where(
                Customer.merchant_id == merchant_id,
                Customer.email == email,
            )
        )
        customer = result.scalar_one_or_none()
        if customer:
            return customer

    # Create new
    customer = Customer(
        merchant_id=merchant_id,
        razorpay_customer_id=rzp_customer_id,
        email=email,
        name=name,
        phone=phone,
    )
    session.add(customer)
    await session.flush()
    logger.info("Created customer %s for merchant %s", customer.id, merchant_id)
    return customer


# ── Risk case helpers ─────────────────────────────────────────────────────────

async def _get_or_create_risk_case(
    session: AsyncSession,
    merchant_id: uuid.UUID,
    source_type: str,
    source_id: str,
    customer_id: uuid.UUID | None,
) -> tuple[RiskCase, bool]:
    """Return (risk_case, created). Existing open cases are reused."""
    result = await session.execute(
        select(RiskCase).where(
            RiskCase.merchant_id == merchant_id,
            RiskCase.source_type == source_type,
            RiskCase.source_id == source_id,
            RiskCase.status.notin_(["recovered", "closed_unrecovered", "escalated"]),
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing, False

    case = RiskCase(
        merchant_id=merchant_id,
        customer_id=customer_id,
        source_type=source_type,
        source_id=source_id,
        status="detected",
    )
    session.add(case)
    await session.flush()
    return case, True


# ── Payment failure handler ───────────────────────────────────────────────────

async def handle_payment_failed(
    session: AsyncSession,
    merchant: Merchant,
    payload: dict,
) -> RiskCase | None:
    payment = payload.get("payload", {}).get("payment", {}).get("entity", {})
    if not payment:
        logger.warning("payment.failed webhook missing payment entity")
        return None

    rzp_payment_id = payment.get("id")
    amount = payment.get("amount")
    currency = payment.get("currency", "INR")
    error_code = payment.get("error_code")
    error_reason = payment.get("error_description")

    # Customer data from nested fields
    rzp_customer_id = payment.get("customer_id")
    email = payment.get("email")
    phone = payment.get("contact")
    name = None

    customer = await _resolve_customer(
        session, merchant.id, rzp_customer_id, email, name, phone
    )

    # Upsert payment event
    event = PaymentEvent(
        merchant_id=merchant.id,
        customer_id=customer.id if customer else None,
        razorpay_payment_id=rzp_payment_id,
        amount=amount,
        currency=currency,
        status="failed",
        error_code=error_code,
        error_reason=error_reason,
        raw_payload=payload,
    )
    session.add(event)

    # Create/get risk case
    risk_case, created = await _get_or_create_risk_case(
        session, merchant.id, "payment_failure", rzp_payment_id, customer.id if customer else None
    )

    # Diagnose
    result = diag.diagnose_payment_failure(error_code, error_reason)
    risk_case.diagnosis_code = result.code
    risk_case.diagnosis_confidence = result.confidence
    risk_case.status = "diagnosed"

    await append_audit(
        session, merchant.id, actor="system",
        action="risk_case.diagnosed",
        target_id=str(risk_case.id),
        detail=f"diagnosis={result.code} confidence={result.confidence:.0%} reason={result.reasoning}",
    )

    logger.info(
        "payment.failed | merchant=%s | payment=%s | diagnosis=%s",
        merchant.id, rzp_payment_id, result.code,
    )
    return risk_case


# ── Payment captured (for attribution) ───────────────────────────────────────

async def handle_payment_captured(
    session: AsyncSession,
    merchant: Merchant,
    payload: dict,
) -> None:
    payment = payload.get("payload", {}).get("payment", {}).get("entity", {})
    if not payment:
        return

    rzp_payment_id = payment.get("id")
    amount = payment.get("amount")
    currency = payment.get("currency", "INR")
    rzp_customer_id = payment.get("customer_id")
    email = payment.get("email")
    phone = payment.get("contact")

    customer = await _resolve_customer(
        session, merchant.id, rzp_customer_id, email, None, phone
    )

    event = PaymentEvent(
        merchant_id=merchant.id,
        customer_id=customer.id if customer else None,
        razorpay_payment_id=rzp_payment_id,
        amount=amount,
        currency=currency,
        status="captured",
        raw_payload=payload,
    )
    session.add(event)

    await append_audit(
        session, merchant.id, actor="system",
        action="payment.captured",
        target_id=rzp_payment_id,
        detail=f"amount={amount} currency={currency}",
    )
    logger.info("payment.captured | merchant=%s | payment=%s", merchant.id, rzp_payment_id)
    # Attribution is handled by the measurement watcher Celery task


# ── Invoice handlers ──────────────────────────────────────────────────────────

async def handle_invoice_event(
    session: AsyncSession,
    merchant: Merchant,
    event_type: str,
    payload: dict,
) -> RiskCase | None:
    invoice_entity = payload.get("payload", {}).get("invoice", {}).get("entity", {})
    if not invoice_entity:
        return None

    rzp_invoice_id = invoice_entity.get("id")
    amount = invoice_entity.get("amount", 0)
    amount_paid = invoice_entity.get("amount_paid", 0)
    status = invoice_entity.get("status", "issued")
    due_date_ts = invoice_entity.get("due_date")

    rzp_customer_id = invoice_entity.get("customer_id")
    customer_detail = invoice_entity.get("customer_details", {})
    email = customer_detail.get("email") or invoice_entity.get("email")
    name = customer_detail.get("name")
    phone = customer_detail.get("contact")

    customer = await _resolve_customer(
        session, merchant.id, rzp_customer_id, email, name, phone
    )

    # Upsert invoice
    result = await session.execute(
        select(Invoice).where(Invoice.razorpay_invoice_id == rzp_invoice_id)
    )
    invoice = result.scalar_one_or_none()
    if invoice:
        invoice.status = status
        invoice.amount_paid = amount_paid
    else:
        from datetime import date
        due_date = (
            datetime.fromtimestamp(due_date_ts, tz=timezone.utc).date()
            if due_date_ts else None
        )
        invoice = Invoice(
            merchant_id=merchant.id,
            razorpay_invoice_id=rzp_invoice_id,
            customer_id=customer.id if customer else None,
            amount=amount,
            amount_paid=amount_paid,
            due_date=due_date,
            status=status,
        )
        session.add(invoice)

    # Only create risk case for expired/overdue invoices
    if event_type not in ("invoice.expired", "invoice.payment_failed"):
        return None

    now = datetime.now(timezone.utc)
    days_overdue = 0
    if invoice.due_date:
        days_overdue = (now.date() - invoice.due_date).days

    risk_case, _ = await _get_or_create_risk_case(
        session, merchant.id, "overdue_invoice", rzp_invoice_id,
        customer.id if customer else None
    )

    # Prior late payment count (simplified: count prior overdue invoice cases)
    result2 = await session.execute(
        select(RiskCase).where(
            RiskCase.merchant_id == merchant.id,
            RiskCase.customer_id == customer.id if customer else None,
            RiskCase.source_type == "overdue_invoice",
        )
    )
    prior_count = len(result2.scalars().all()) - 1  # exclude current

    diag_result = diag.diagnose_invoice_overdue(days_overdue, max(prior_count, 0), amount)
    risk_case.diagnosis_code = diag_result.code
    risk_case.diagnosis_confidence = diag_result.confidence
    risk_case.status = "diagnosed"

    await append_audit(
        session, merchant.id, actor="system",
        action="risk_case.diagnosed",
        target_id=str(risk_case.id),
        detail=f"diagnosis={diag_result.code} days_overdue={days_overdue}",
    )
    return risk_case


# ── Subscription handlers ─────────────────────────────────────────────────────

async def handle_subscription_event(
    session: AsyncSession,
    merchant: Merchant,
    event_type: str,
    payload: dict,
) -> RiskCase | None:
    sub_entity = payload.get("payload", {}).get("subscription", {}).get("entity", {})
    if not sub_entity:
        return None

    rzp_sub_id = sub_entity.get("id")
    status = sub_entity.get("status", "active")
    rzp_customer_id = sub_entity.get("customer_id")
    charge_count = sub_entity.get("paid_count", 0)
    mandate_expired = status in ("expired", "cancelled")

    customer = await _resolve_customer(
        session, merchant.id, rzp_customer_id, None, None, None
    )

    # Upsert subscription
    result = await session.execute(
        select(SubscriptionTracked).where(
            SubscriptionTracked.razorpay_subscription_id == rzp_sub_id
        )
    )
    sub = result.scalar_one_or_none()
    if sub:
        sub.status = status
        if status == "halted":
            sub.halted_at = datetime.now(timezone.utc)
    else:
        sub = SubscriptionTracked(
            merchant_id=merchant.id,
            razorpay_subscription_id=rzp_sub_id,
            customer_id=customer.id if customer else None,
            status=status,
            halted_at=datetime.now(timezone.utc) if status == "halted" else None,
        )
        session.add(sub)

    if event_type not in ("subscription.halted", "subscription.charged"):
        return None

    risk_case, _ = await _get_or_create_risk_case(
        session, merchant.id, "subscription", rzp_sub_id, customer.id if customer else None
    )

    diag_result = diag.diagnose_subscription_failure(
        status, charge_count, mandate_expired=mandate_expired
    )
    risk_case.diagnosis_code = diag_result.code
    risk_case.diagnosis_confidence = diag_result.confidence
    risk_case.status = "diagnosed"

    await append_audit(
        session, merchant.id, actor="system",
        action="risk_case.diagnosed",
        target_id=str(risk_case.id),
        detail=f"diagnosis={diag_result.code} sub_status={status}",
    )
    return risk_case
