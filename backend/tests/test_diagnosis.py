"""Tests for the diagnosis classifier."""

import pytest
from app.services.diagnosis import (
    diagnose_payment_failure,
    diagnose_dropoff,
    diagnose_subscription_failure,
    diagnose_invoice_overdue,
)


class TestPaymentFailureDiagnosis:
    def test_insufficient_funds_by_error_code(self):
        result = diagnose_payment_failure("INSUFFICIENT_FUNDS", None)
        assert result.code == "insufficient_funds"
        assert result.confidence >= 0.90

    def test_card_expired_by_razorpay_error_code(self):
        result = diagnose_payment_failure(
            "BAD_REQUEST_ERROR.PAYMENT_CARD_INVALID_EXPIRY_DATE", None
        )
        assert result.code == "card_expired"
        assert result.confidence >= 0.90

    def test_customer_cancelled(self):
        result = diagnose_payment_failure("BAD_REQUEST_ERROR.PAYMENT_CANCELLED", None)
        assert result.code == "customer_cancelled"

    def test_keyword_fallback_insufficient(self):
        result = diagnose_payment_failure(None, "Payment failed due to insufficient balance")
        assert result.code == "insufficient_funds"

    def test_keyword_fallback_expired(self):
        result = diagnose_payment_failure(None, "Card has expired")
        assert result.code == "card_expired"

    def test_unknown_fallback(self):
        result = diagnose_payment_failure(None, None)
        assert result.code == "bank_declined"
        assert result.confidence == 0.50

    def test_gateway_error(self):
        result = diagnose_payment_failure("GATEWAY_ERROR", None)
        assert result.code == "technical_error"


class TestDropoffDiagnosis:
    def test_repeat_abandoner(self):
        result = diagnose_dropoff(
            age_minutes=10, cart_value_paise=5000, prior_dropoff_count=3, prior_successful_payments=1
        )
        assert result.code == "repeat_abandoner"
        assert result.confidence >= 0.80

    def test_high_value_price_hesitation(self):
        result = diagnose_dropoff(
            age_minutes=10, cart_value_paise=200_000, prior_dropoff_count=0, prior_successful_payments=2
        )
        assert result.code == "price_hesitation"

    def test_quick_exit_friction(self):
        result = diagnose_dropoff(
            age_minutes=2, cart_value_paise=5000, prior_dropoff_count=0, prior_successful_payments=0
        )
        assert result.code == "payment_method_friction"


class TestSubscriptionDiagnosis:
    def test_mandate_expired(self):
        result = diagnose_subscription_failure("expired", 5, mandate_expired=True)
        assert result.code == "mandate_expired"
        assert result.confidence >= 0.90

    def test_first_time_failure(self):
        result = diagnose_subscription_failure("halted", 1)
        assert result.code == "first_time_failure"

    def test_recurring_failure(self):
        result = diagnose_subscription_failure("halted", 3)
        assert result.code == "recurring_failure"


class TestInvoiceDiagnosis:
    def test_chronic_late_payer(self):
        result = diagnose_invoice_overdue(
            days_overdue=5, prior_late_payment_count=4, invoice_amount_paise=50_000
        )
        assert result.code == "chronic_late_payer"

    def test_early_overdue(self):
        result = diagnose_invoice_overdue(
            days_overdue=2, prior_late_payment_count=0, invoice_amount_paise=10_000
        )
        assert result.code == "early_overdue"

    def test_disputed_likely_high_value(self):
        result = diagnose_invoice_overdue(
            days_overdue=10, prior_late_payment_count=0, invoice_amount_paise=1_000_000
        )
        assert result.code == "disputed_likely"
