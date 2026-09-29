"""
Razorpay Standard Checkout — Create Order & Verify Payment endpoints.
"""
from __future__ import annotations

import hashlib
import hmac
import uuid

import razorpay
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.settings import get_settings

router = APIRouter(prefix="/payments", tags=["payments"])


def _razorpay_client() -> razorpay.Client:
    s = get_settings()
    return razorpay.Client(
        auth=(s.RAZORPAY_KEY_ID, s.RAZORPAY_KEY_SECRET)
    )


# ── Schemas ───────────────────────────────────────────────────────────────────

class CreateOrderRequest(BaseModel):
    amount: int = Field(..., description="Amount in paise (INR × 100). Minimum 100.")
    currency: str = Field(default="INR")
    receipt: str | None = Field(default=None)


class CreateOrderResponse(BaseModel):
    order_id: str
    amount: int
    currency: str


class VerifyPaymentRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class VerifyPaymentResponse(BaseModel):
    success: bool
    payment_id: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/create-order", response_model=CreateOrderResponse)
async def create_order(body: CreateOrderRequest):
    """
    Create a Razorpay order and return the order_id needed to open the checkout
    modal on the frontend. Amount must be at least 100 paise (₹1).
    """
    if body.amount < 100:
        raise HTTPException(
            status_code=422,
            detail="amount must be at least 100 paise (₹1).",
        )

    receipt = body.receipt or f"rcpt_{uuid.uuid4().hex[:12]}"

    try:
        client = _razorpay_client()
        order = client.order.create(
            {
                "amount": body.amount,
                "currency": body.currency,
                "receipt": receipt,
                "payment_capture": 1,  # auto-capture
            }
        )
    except razorpay.errors.BadRequestError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except razorpay.errors.ServerError as exc:
        raise HTTPException(status_code=502, detail="Razorpay server error.") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Could not create order.") from exc

    return CreateOrderResponse(
        order_id=order["id"],
        amount=order["amount"],
        currency=order["currency"],
    )


@router.post("/verify-payment", response_model=VerifyPaymentResponse)
async def verify_payment(body: VerifyPaymentRequest):
    """
    Verify the HMAC-SHA256 signature returned by Razorpay after a successful
    payment. Returns 400 if the signature does not match — the caller must NOT
    mark the payment as complete in that case.
    """
    settings = get_settings()

    # HMAC-SHA256(order_id + "|" + payment_id, KEY_SECRET)
    payload = f"{body.razorpay_order_id}|{body.razorpay_payment_id}"
    expected = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected, body.razorpay_signature):
        raise HTTPException(status_code=400, detail="Payment signature mismatch.")

    return VerifyPaymentResponse(
        success=True,
        payment_id=body.razorpay_payment_id,
    )
