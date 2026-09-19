"""
Rule-based diagnosis classifier.

Input:  signal type + key fields from the raw webhook event.
Output: (diagnosis_code, confidence)

The mapping is intentionally transparent rule logic — no ML needed at this stage.
Each diagnosis code gates which tools the agent is allowed to use.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class DiagnosisResult:
    code: str
    confidence: float  # 0.0 – 1.0
    reasoning: str


# ── Payment failure diagnosis ──────────────────────────────────────────────────

# Razorpay error_code → (diagnosis_code, confidence)
_PAYMENT_ERROR_MAP: dict[str, tuple[str, float]] = {
    # Insufficient funds
    "BAD_REQUEST_ERROR.PAYMENT_INSUFFICIENT_FUNDS": ("insufficient_funds", 0.97),
    "INSUFFICIENT_FUNDS": ("insufficient_funds", 0.95),
    # Card expired
    "BAD_REQUEST_ERROR.PAYMENT_CARD_INVALID_EXPIRY_DATE": ("card_expired", 0.97),
    "CARD_EXPIRED": ("card_expired", 0.95),
    # Bank / issuer decline (generic)
    "BAD_REQUEST_ERROR.PAYMENT_DECLINED_BY_BANK": ("bank_declined", 0.90),
    "BAD_REQUEST_ERROR.PAYMENT_DECLINED_BY_ISSUING_BANK": ("bank_declined", 0.90),
    "BANK_DECLINED": ("bank_declined", 0.90),
    # Technical / gateway error
    "GATEWAY_ERROR": ("technical_error", 0.85),
    "BAD_REQUEST_ERROR.PAYMENT_PROCESSING_FAILED": ("technical_error", 0.80),
    "SERVER_ERROR": ("technical_error", 0.85),
    # Customer cancelled
    "BAD_REQUEST_ERROR.PAYMENT_CANCELLED": ("customer_cancelled", 0.97),
    "PAYMENT_CANCELLED": ("customer_cancelled", 0.95),
}

_PAYMENT_REASON_KEYWORDS: dict[str, tuple[str, float]] = {
    "insufficient": ("insufficient_funds", 0.80),
    "expired": ("card_expired", 0.80),
    "declined by bank": ("bank_declined", 0.75),
    "cancelled by customer": ("customer_cancelled", 0.80),
    "gateway": ("technical_error", 0.70),
}


def diagnose_payment_failure(
    error_code: str | None,
    error_reason: str | None,
    description: str | None = None,
) -> DiagnosisResult:
    """Classify a payment.failed event."""
    # 1. Try exact error_code match
    if error_code:
        upper = error_code.upper()
        if upper in _PAYMENT_ERROR_MAP:
            code, conf = _PAYMENT_ERROR_MAP[upper]
            return DiagnosisResult(code, conf, f"Matched error_code: {error_code}")
        # Partial key match
        for key, (code, conf) in _PAYMENT_ERROR_MAP.items():
            if key in upper or upper in key:
                return DiagnosisResult(
                    code, conf * 0.9, f"Partial error_code match: {error_code}"
                )

    # 2. Keyword scan of error_reason / description
    text = f"{error_reason or ''} {description or ''}".lower()
    for keyword, (code, conf) in _PAYMENT_REASON_KEYWORDS.items():
        if keyword in text:
            return DiagnosisResult(code, conf, f"Keyword match in reason: '{keyword}'")

    # 3. Fallback
    return DiagnosisResult("bank_declined", 0.50, "No specific signal; defaulting to bank_declined")


# ── Checkout drop-off diagnosis ────────────────────────────────────────────────

def diagnose_dropoff(
    age_minutes: float,
    cart_value_paise: int,
    prior_dropoff_count: int,
    prior_successful_payments: int,
) -> DiagnosisResult:
    """Classify an order drop-off (no payment within the window)."""
    # Repeat abandoner: 2+ prior drop-offs for same customer
    if prior_dropoff_count >= 2:
        return DiagnosisResult(
            "repeat_abandoner",
            0.85,
            f"Customer has {prior_dropoff_count} prior drop-offs",
        )

    # High-value cart drop-off → price hesitation
    if cart_value_paise >= 100_000:  # ≥ ₹1,000
        return DiagnosisResult(
            "price_hesitation",
            0.75,
            f"Cart value ₹{cart_value_paise / 100:.0f} suggests price hesitation",
        )

    # Quick exit → likely payment method friction
    if age_minutes < 5:
        return DiagnosisResult(
            "payment_method_friction",
            0.70,
            f"Checkout exited after only {age_minutes:.1f} minutes",
        )

    return DiagnosisResult(
        "price_hesitation",
        0.55,
        "No strong signal; defaulting to price_hesitation",
    )


# ── Subscription failure diagnosis ────────────────────────────────────────────

def diagnose_subscription_failure(
    subscription_status: str,
    charge_attempt_count: int,
    mandate_expired: bool = False,
) -> DiagnosisResult:
    if mandate_expired:
        return DiagnosisResult("mandate_expired", 0.95, "Mandate marked expired")

    if charge_attempt_count == 1:
        return DiagnosisResult(
            "first_time_failure",
            0.80,
            "First charge attempt failed",
        )

    if charge_attempt_count >= 2:
        return DiagnosisResult(
            "recurring_failure",
            0.88,
            f"Recurring failure; attempt #{charge_attempt_count}",
        )

    if subscription_status == "halted":
        return DiagnosisResult(
            "recurring_failure",
            0.75,
            "Subscription halted",
        )

    return DiagnosisResult("first_time_failure", 0.50, "Subscription failure; no further signal")


# ── Invoice overdue diagnosis ─────────────────────────────────────────────────

def diagnose_invoice_overdue(
    days_overdue: int,
    prior_late_payment_count: int,
    invoice_amount_paise: int,
) -> DiagnosisResult:
    if prior_late_payment_count >= 3:
        return DiagnosisResult(
            "chronic_late_payer",
            0.90,
            f"Customer has {prior_late_payment_count} prior late payments",
        )

    if days_overdue <= 3:
        return DiagnosisResult(
            "early_overdue",
            0.85,
            f"Invoice {days_overdue} day(s) overdue — likely oversight",
        )

    if invoice_amount_paise >= 500_000:  # ≥ ₹5,000
        return DiagnosisResult(
            "disputed_likely",
            0.65,
            f"High-value invoice (₹{invoice_amount_paise/100:.0f}) overdue {days_overdue} days",
        )

    return DiagnosisResult(
        "early_overdue",
        0.55,
        f"Invoice {days_overdue} days overdue; no chronic pattern",
    )
