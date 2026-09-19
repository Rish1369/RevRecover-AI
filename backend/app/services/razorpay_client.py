"""
Razorpay client — thin async wrapper around the Razorpay Python SDK.

All methods operate in test mode when the merchant's `mode == 'test'`.
Errors are raised as RazorpayError with full context.
"""

from __future__ import annotations

import logging
from typing import Any

import razorpay

from app.core.security import decrypt_secret
from app.models.merchant import Merchant

logger = logging.getLogger(__name__)


class RazorpayError(Exception):
    """Wraps Razorpay API errors with context."""


def _get_client(merchant: Merchant) -> razorpay.Client:
    key_id = merchant.razorpay_key_id
    key_secret = decrypt_secret(merchant.razorpay_key_secret_enc)
    return razorpay.Client(auth=(key_id, key_secret))


# ── Payment links ─────────────────────────────────────────────────────────────

def create_payment_link(
    merchant: Merchant,
    amount_paise: int,
    currency: str = "INR",
    customer_name: str | None = None,
    customer_email: str | None = None,
    customer_phone: str | None = None,
    description: str = "Payment",
    reference_id: str | None = None,
    expire_by: int | None = None,  # unix timestamp
) -> dict[str, Any]:
    """Create a Razorpay payment link and return the response dict."""
    client = _get_client(merchant)
    payload: dict[str, Any] = {
        "amount": amount_paise,
        "currency": currency,
        "description": description,
    }
    if customer_name or customer_email or customer_phone:
        payload["customer"] = {}
        if customer_name:
            payload["customer"]["name"] = customer_name
        if customer_email:
            payload["customer"]["email"] = customer_email
        if customer_phone:
            payload["customer"]["contact"] = customer_phone
        payload["notify"] = {
            "sms": bool(customer_phone),
            "email": bool(customer_email),
        }
    if reference_id:
        payload["reference_id"] = reference_id
    if expire_by:
        payload["expire_by"] = expire_by

    try:
        response = client.payment_link.create(payload)
        logger.info("razorpay.create_payment_link | merchant=%s | id=%s", merchant.id, response.get("id"))
        return response
    except Exception as exc:
        logger.error("razorpay.create_payment_link failed: %s", exc)
        raise RazorpayError(f"create_payment_link failed: {exc}") from exc


# ── Email / SMS (via Razorpay notifications) ──────────────────────────────────

def resend_invoice(merchant: Merchant, razorpay_invoice_id: str) -> dict[str, Any]:
    """Resend an invoice notification via Razorpay."""
    client = _get_client(merchant)
    try:
        response = client.invoice.notify(razorpay_invoice_id, "email")
        logger.info("razorpay.resend_invoice | merchant=%s | invoice=%s", merchant.id, razorpay_invoice_id)
        return response
    except Exception as exc:
        raise RazorpayError(f"resend_invoice failed: {exc}") from exc


# ── Discount / offer links ────────────────────────────────────────────────────

def create_discount_payment_link(
    merchant: Merchant,
    original_amount_paise: int,
    discount_pct: float,
    **kwargs,
) -> dict[str, Any]:
    """Create a payment link with a discount applied."""
    discounted = int(original_amount_paise * (1 - discount_pct / 100))
    description = f"Special offer — {discount_pct:.0f}% discount applied"
    return create_payment_link(
        merchant, discounted, description=description, **kwargs
    )


# ── Mandate update ────────────────────────────────────────────────────────────

def send_mandate_update_link(
    merchant: Merchant,
    subscription_id: str,
    customer_email: str | None = None,
    customer_phone: str | None = None,
) -> dict[str, Any]:
    """
    Fetch the subscription and return the Razorpay auth link for mandate update.
    In test mode this returns a mock auth link.
    """
    client = _get_client(merchant)
    try:
        sub = client.subscription.fetch(subscription_id)
        auth_link = sub.get("short_url", f"https://rzp.io/sub/{subscription_id}")
        logger.info(
            "razorpay.mandate_update_link | merchant=%s | sub=%s", merchant.id, subscription_id
        )
        return {"auth_link": auth_link, "subscription": sub}
    except Exception as exc:
        raise RazorpayError(f"send_mandate_update_link failed: {exc}") from exc


# ── Payment fetch (for attribution) ──────────────────────────────────────────

def fetch_payment(merchant: Merchant, razorpay_payment_id: str) -> dict[str, Any]:
    client = _get_client(merchant)
    try:
        return client.payment.fetch(razorpay_payment_id)
    except Exception as exc:
        raise RazorpayError(f"fetch_payment failed: {exc}") from exc


def fetch_payments_for_customer(
    merchant: Merchant,
    razorpay_customer_id: str,
    from_timestamp: int,
    to_timestamp: int,
) -> list[dict[str, Any]]:
    """List captured payments for a customer in a time window."""
    client = _get_client(merchant)
    try:
        resp = client.payment.all({
            "customer_id": razorpay_customer_id,
            "from": from_timestamp,
            "to": to_timestamp,
        })
        items = resp.get("items", [])
        return [p for p in items if p.get("status") == "captured"]
    except Exception as exc:
        raise RazorpayError(f"fetch_payments_for_customer failed: {exc}") from exc
