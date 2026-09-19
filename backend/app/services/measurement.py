"""
Attribution / measurement watcher.

Called by the Celery periodic task every ATTRIBUTION_SCAN_INTERVAL seconds.
For each risk_case in 'monitoring' status:
  - Check if a matching successful payment arrived within the attribution window
  - If yes → insert RecoveryLedger entry, mark case 'recovered'
  - If window expired → mark case 'closed_unrecovered'
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.settings import get_settings
from app.models.customer import Customer
from app.models.merchant import Merchant
from app.models.payment_event import PaymentEvent
from app.models.recovery_ledger import RecoveryLedger
from app.models.risk_case import RiskCase
from app.services.audit import append_audit

settings = get_settings()
logger = logging.getLogger(__name__)


async def run_attribution_scan(session: AsyncSession, merchant: Merchant) -> dict:
    """
    Scan all monitoring cases for this merchant and attribute recoveries.
    Returns a summary dict.
    """
    window = timedelta(days=settings.ATTRIBUTION_WINDOW_DAYS)
    now = datetime.now(timezone.utc)

    # Fetch all cases in monitoring status
    result = await session.execute(
        select(RiskCase).where(
            RiskCase.merchant_id == merchant.id,
            RiskCase.status == "monitoring",
        )
    )
    cases = result.scalars().all()

    recovered_count = 0
    unrecovered_count = 0

    for case in cases:
        # Check if attribution window has expired
        if now - case.created_at > window:
            case.status = "closed_unrecovered"
            case.resolved_at = now
            await append_audit(
                session, merchant.id, actor="measurement",
                action="case.closed_unrecovered",
                target_id=str(case.id),
                detail=f"Attribution window ({settings.ATTRIBUTION_WINDOW_DAYS}d) expired",
            )
            unrecovered_count += 1
            continue

        if not case.customer_id:
            continue

        # Look for a captured payment from this customer after the last action
        result2 = await session.execute(
            select(PaymentEvent).where(
                PaymentEvent.merchant_id == merchant.id,
                PaymentEvent.customer_id == case.customer_id,
                PaymentEvent.status == "captured",
                PaymentEvent.created_at >= case.created_at,
            ).order_by(PaymentEvent.created_at.desc()).limit(1)
        )
        payment = result2.scalar_one_or_none()

        if payment:
            # Attribute the recovery
            ledger_entry = RecoveryLedger(
                merchant_id=merchant.id,
                risk_case_id=case.id,
                amount_recovered=payment.amount or 0,
                currency=payment.currency or "INR",
                attributed_at=now,
            )
            session.add(ledger_entry)
            case.status = "recovered"
            case.resolved_at = now

            await append_audit(
                session, merchant.id, actor="measurement",
                action="case.recovered",
                target_id=str(case.id),
                detail=f"Payment {payment.razorpay_payment_id} captured. Amount: {payment.amount} {payment.currency}",
            )
            logger.info(
                "Attribution: case %s recovered via payment %s (₹%s)",
                case.id, payment.razorpay_payment_id, (payment.amount or 0) / 100,
            )
            recovered_count += 1

    return {
        "scanned": len(cases),
        "recovered": recovered_count,
        "closed_unrecovered": unrecovered_count,
    }
