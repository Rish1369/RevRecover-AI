"""
Razorpay webhook receiver.

POST /webhooks/razorpay/{merchant_id}

Verifies HMAC-SHA256 signature, routes to the correct service handler,
and enqueues the agent Celery task for cases that need intervention.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.db import get_db
from app.core.security import decrypt_secret, verify_razorpay_signature
from app.models.merchant import Merchant
from app.services import webhook as wh

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# Events that should trigger the agent
AGENT_TRIGGER_EVENTS = {
    "payment.failed",
    "invoice.expired",
    "invoice.payment_failed",
    "subscription.halted",
}


@router.post("/razorpay/{merchant_id}", status_code=200)
async def receive_razorpay_webhook(
    merchant_id: uuid.UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    x_razorpay_signature: str | None = Header(default=None),
    session: AsyncSession = Depends(get_db),
):
    """
    Receive and process a Razorpay webhook for a specific merchant.

    The merchant is looked up WITHOUT RLS (by-ID) to verify the signature,
    then subsequent DB writes use the merchant-scoped session.
    """
    # 1. Fetch merchant (no RLS needed for signature check)
    result = await session.execute(
        select(Merchant).where(Merchant.id == merchant_id)
    )
    merchant = result.scalar_one_or_none()
    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant not found")

    # 2. Read raw body (must be done before any parsing)
    raw_body = await request.body()

    # 3. Verify signature
    if not x_razorpay_signature:
        raise HTTPException(status_code=400, detail="Missing X-Razorpay-Signature header")

    webhook_secret = decrypt_secret(merchant.razorpay_webhook_secret_enc)
    if not verify_razorpay_signature(raw_body, x_razorpay_signature, webhook_secret):
        logger.warning("Invalid Razorpay signature for merchant %s", merchant_id)
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    # 4. Parse payload
    try:
        payload: dict = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    event_type: str = payload.get("event", "")
    logger.info("Webhook received | merchant=%s | event=%s", merchant_id, event_type)

    # 5. Set RLS context and route
    await session.execute(
        __import__("sqlalchemy").text(f"SET LOCAL app.current_merchant_id = '{merchant_id}'"),
    )

    risk_case = None

    if event_type == "payment.failed":
        risk_case = await wh.handle_payment_failed(session, merchant, payload)

    elif event_type == "payment.captured":
        await wh.handle_payment_captured(session, merchant, payload)

    elif event_type.startswith("invoice."):
        risk_case = await wh.handle_invoice_event(session, merchant, event_type, payload)

    elif event_type.startswith("subscription."):
        risk_case = await wh.handle_subscription_event(session, merchant, event_type, payload)

    else:
        logger.debug("Unhandled event type: %s", event_type)

    await session.commit()

    # 6. Enqueue agent task for actionable events
    if risk_case and event_type in AGENT_TRIGGER_EVENTS:
        from app.workers.tasks import run_agent_for_case
        background_tasks.add_task(
            run_agent_for_case.delay,
            str(merchant_id),
            str(risk_case.id),
        )
        logger.info("Enqueued agent task for case %s", risk_case.id)

    return {"status": "ok", "event": event_type}
