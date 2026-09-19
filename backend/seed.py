"""
Seed script — creates one test merchant with default policies and one test customer.

Run with:
    cd backend
    python seed.py
"""

import asyncio
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.db import AsyncSessionLocal, engine
from app.core.security import encrypt_secret
from app.core.settings import get_settings
from app.models.merchant import Merchant
from app.models.customer import Customer
from app.models.policy import Policy

settings = get_settings()

# ── Default diagnosis → tool playbook ────────────────────────────────────────
DEFAULT_PLAYBOOK = {
    "insufficient_funds":       ["create_payment_link", "send_recovery_email", "send_recovery_sms"],
    "card_expired":             ["send_recovery_email", "send_recovery_sms"],
    "bank_declined":            ["create_payment_link", "send_recovery_email"],
    "technical_error":          ["create_payment_link", "send_recovery_email"],
    "customer_cancelled":       ["send_recovery_email", "log_promise_to_pay", "escalate_to_human"],
    "price_hesitation":         ["offer_discount_link", "create_payment_link", "send_recovery_email"],
    "payment_method_friction":  ["create_payment_link", "send_recovery_sms"],
    "repeat_abandoner":         ["send_recovery_email", "log_promise_to_pay"],
    "first_time_failure":       ["create_payment_link", "send_recovery_email"],
    "recurring_failure":        ["send_recovery_email", "offer_payment_plan"],
    "mandate_expired":          ["send_mandate_update_link"],
    "early_overdue":            ["resend_invoice", "send_recovery_email"],
    "chronic_late_payer":       ["offer_payment_plan", "escalate_to_human"],
    "disputed_likely":          ["escalate_to_human"],
    "_default":                 ["send_recovery_email", "escalate_to_human"],
}

DEFAULT_POLICIES = {
    "max_actions_per_case":    {"v": 3},
    "cooldown_hours":          {"v": 4},
    "contact_hours_start":     {"v": 9},
    "contact_hours_end":       {"v": 21},
    "max_discount_pct":        {"v": 10},
    "max_agent_spend_per_day": {"v": 10.0},  # USD
    "dnc_respect":             {"v": True},
    "diagnosis_playbook":      DEFAULT_PLAYBOOK,
}


async def seed():
    async with AsyncSessionLocal() as session:
        # Check if already seeded
        result = await session.execute(
            select(Merchant).where(Merchant.name == "Test Merchant (Seed)")
        )
        existing = result.scalar_one_or_none()
        if existing:
            print(f"✓ Test merchant already exists: {existing.id}")
            merchant = existing
        else:
            # Create merchant
            merchant = Merchant(
                id=uuid.uuid4(),
                name="Test Merchant (Seed)",
                razorpay_key_id=settings.SEED_RAZORPAY_KEY_ID,
                razorpay_key_secret_enc=encrypt_secret(settings.SEED_RAZORPAY_KEY_SECRET),
                razorpay_webhook_secret_enc=encrypt_secret(settings.SEED_RAZORPAY_WEBHOOK_SECRET),
                mode="test",
            )
            session.add(merchant)
            await session.flush()
            print(f"✓ Created test merchant: {merchant.id}")

        # Seed policies (skip existing)
        for key, value in DEFAULT_POLICIES.items():
            policy_result = await session.execute(
                select(Policy).where(
                    Policy.merchant_id == merchant.id,
                    Policy.key == key,
                )
            )
            if not policy_result.scalar_one_or_none():
                session.add(Policy(merchant_id=merchant.id, key=key, value=value))
                print(f"  + Policy: {key}")

        # Seed test customer
        cust_result = await session.execute(
            select(Customer).where(
                Customer.merchant_id == merchant.id,
                Customer.email == "test.customer@example.com",
            )
        )
        if not cust_result.scalar_one_or_none():
            customer = Customer(
                merchant_id=merchant.id,
                name="Test Customer",
                email="test.customer@example.com",
                phone="+919999999999",
                razorpay_customer_id="cust_test_placeholder",
            )
            session.add(customer)
            print(f"  + Test customer created")

        await session.commit()
        print(f"\n✅ Seed complete.")
        print(f"   Merchant ID:  {merchant.id}")
        print(f"   Webhook URL:  POST /webhooks/razorpay/{merchant.id}")
        print(f"   Dashboard:    ?merchant_id={merchant.id}")


if __name__ == "__main__":
    asyncio.run(seed())
