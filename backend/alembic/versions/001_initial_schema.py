"""Initial schema with RLS.

Revision ID: 001
Revises:
Create Date: 2026-09-18
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Extensions ────────────────────────────────────────────────────────────
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    # ── Custom types ──────────────────────────────────────────────────────────
    op.execute("CREATE TYPE merchant_mode AS ENUM ('test', 'live')")
    op.execute(
        "CREATE TYPE risk_source_type AS ENUM "
        "('payment_failure', 'dropoff', 'overdue_invoice', 'subscription', 'mandate')"
    )
    op.execute(
        "CREATE TYPE risk_case_status AS ENUM "
        "('detected', 'diagnosed', 'action_taken', 'monitoring', "
        " 'recovered', 'escalated', 'closed_unrecovered')"
    )
    op.execute(
        "CREATE TYPE promise_status AS ENUM ('pending', 'kept', 'broken', 'cancelled')"
    )
    op.execute(
        "CREATE TYPE agent_action_status AS ENUM "
        "('pending', 'approved', 'denied', 'executed', 'failed', 'skipped_dnc', 'escalated')"
    )

    # ── merchants ─────────────────────────────────────────────────────────────
    op.create_table(
        "merchants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("razorpay_key_id", sa.String(255), nullable=False),
        sa.Column("razorpay_key_secret_enc", sa.String(512), nullable=False),
        sa.Column("razorpay_webhook_secret_enc", sa.String(512), nullable=False),
        sa.Column(
            "mode",
            postgresql.ENUM("test", "live", name="merchant_mode", create_type=False),
            nullable=False,
            server_default="test",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )
    op.execute("ALTER TABLE merchants ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY merchant_isolation ON merchants "
        "USING (id::text = current_setting('app.current_merchant_id', true))"
    )

    # ── customers ─────────────────────────────────────────────────────────────
    op.create_table(
        "customers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "merchant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("merchants.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(255)),
        sa.Column("email", sa.String(320)),
        sa.Column("phone", sa.String(20)),
        sa.Column("razorpay_customer_id", sa.String(64), index=True),
        sa.Column(
            "do_not_contact", sa.Boolean, nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )
    op.execute("ALTER TABLE customers ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY merchant_isolation ON customers "
        "USING (merchant_id::text = current_setting('app.current_merchant_id', true))"
    )

    # ── payment_events ────────────────────────────────────────────────────────
    op.create_table(
        "payment_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "merchant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("merchants.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "customer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customers.id"),
            nullable=True,
            index=True,
        ),
        sa.Column("razorpay_payment_id", sa.String(64), index=True),
        sa.Column("amount", sa.BigInteger),
        sa.Column("currency", sa.String(3), server_default="INR"),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("error_code", sa.String(128)),
        sa.Column("error_reason", sa.String(512)),
        sa.Column("raw_payload", postgresql.JSONB),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )
    op.execute("ALTER TABLE payment_events ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY merchant_isolation ON payment_events "
        "USING (merchant_id::text = current_setting('app.current_merchant_id', true))"
    )

    # ── orders_tracked ────────────────────────────────────────────────────────
    op.create_table(
        "orders_tracked",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "merchant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("merchants.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("razorpay_order_id", sa.String(64), unique=True, index=True),
        sa.Column(
            "customer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customers.id"),
            nullable=True,
        ),
        sa.Column("amount", sa.BigInteger, nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.Column("checkout_opened_at", sa.DateTime(timezone=True)),
        sa.Column("expired_flagged_at", sa.DateTime(timezone=True)),
    )
    op.execute("ALTER TABLE orders_tracked ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY merchant_isolation ON orders_tracked "
        "USING (merchant_id::text = current_setting('app.current_merchant_id', true))"
    )

    # ── invoices ──────────────────────────────────────────────────────────────
    op.create_table(
        "invoices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "merchant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("merchants.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("razorpay_invoice_id", sa.String(64), unique=True, index=True),
        sa.Column(
            "customer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customers.id"),
            nullable=True,
        ),
        sa.Column("amount", sa.BigInteger, nullable=False),
        sa.Column("amount_paid", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("due_date", sa.Date),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )
    op.execute("ALTER TABLE invoices ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY merchant_isolation ON invoices "
        "USING (merchant_id::text = current_setting('app.current_merchant_id', true))"
    )

    # ── subscriptions_tracked ─────────────────────────────────────────────────
    op.create_table(
        "subscriptions_tracked",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "merchant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("merchants.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "razorpay_subscription_id", sa.String(64), unique=True, index=True
        ),
        sa.Column(
            "customer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customers.id"),
            nullable=True,
        ),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("last_charge_attempt", sa.DateTime(timezone=True)),
        sa.Column("halted_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )
    op.execute("ALTER TABLE subscriptions_tracked ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY merchant_isolation ON subscriptions_tracked "
        "USING (merchant_id::text = current_setting('app.current_merchant_id', true))"
    )

    # ── risk_cases ────────────────────────────────────────────────────────────
    op.create_table(
        "risk_cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "merchant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("merchants.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "customer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customers.id"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "source_type",
            postgresql.ENUM(
                "payment_failure",
                "dropoff",
                "overdue_invoice",
                "subscription",
                "mandate",
                name="risk_source_type",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("source_id", sa.String(64), index=True),
        sa.Column("diagnosis_code", sa.String(64)),
        sa.Column("diagnosis_confidence", sa.Float),
        sa.Column("risk_score", sa.Float),
        sa.Column(
            "status",
            postgresql.ENUM(
                "detected",
                "diagnosed",
                "action_taken",
                "monitoring",
                "recovered",
                "escalated",
                "closed_unrecovered",
                name="risk_case_status",
                create_type=False,
            ),
            nullable=False,
            server_default="detected",
        ),
        sa.Column(
            "attempts_count", sa.Integer, nullable=False, server_default="0"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
    )
    op.execute("ALTER TABLE risk_cases ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY merchant_isolation ON risk_cases "
        "USING (merchant_id::text = current_setting('app.current_merchant_id', true))"
    )

    # ── promises ──────────────────────────────────────────────────────────────
    op.create_table(
        "promises",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "risk_case_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("risk_cases.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("promised_date", sa.Date, nullable=False),
        sa.Column("promised_amount", sa.BigInteger, nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending", "kept", "broken", "cancelled",
                name="promise_status", create_type=False
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )

    # ── policies ──────────────────────────────────────────────────────────────
    op.create_table(
        "policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "merchant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("merchants.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("key", sa.String(128), nullable=False),
        sa.Column("value", postgresql.JSONB, nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_policies_merchant_key", "policies", ["merchant_id", "key"], unique=True)
    op.execute("ALTER TABLE policies ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY merchant_isolation ON policies "
        "USING (merchant_id::text = current_setting('app.current_merchant_id', true))"
    )

    # ── agent_actions ─────────────────────────────────────────────────────────
    op.create_table(
        "agent_actions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "merchant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("merchants.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "risk_case_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("risk_cases.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("tool_name", sa.String(64), nullable=False),
        sa.Column("input_json", postgresql.JSONB),
        sa.Column("reasoning_summary", sa.Text),
        sa.Column("policy_check_result", sa.String(16)),
        sa.Column("policy_check_reason", sa.Text),
        sa.Column("output_json", postgresql.JSONB),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending", "approved", "denied", "executed",
                "failed", "skipped_dnc", "escalated",
                name="agent_action_status", create_type=False
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )
    op.execute("ALTER TABLE agent_actions ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY merchant_isolation ON agent_actions "
        "USING (merchant_id::text = current_setting('app.current_merchant_id', true))"
    )

    # ── audit_log ─────────────────────────────────────────────────────────────
    op.create_table(
        "audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "merchant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("merchants.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("actor", sa.String(128), nullable=False),
        sa.Column("action", sa.String(256), nullable=False),
        sa.Column("target_id", sa.String(64)),
        sa.Column("detail", sa.Text),
        sa.Column("prev_hash", sa.String(64)),
        sa.Column("hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )
    op.execute("ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY merchant_isolation ON audit_log "
        "USING (merchant_id::text = current_setting('app.current_merchant_id', true))"
    )

    # ── recovery_ledger ───────────────────────────────────────────────────────
    op.create_table(
        "recovery_ledger",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "merchant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("merchants.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "risk_case_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("risk_cases.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("amount_recovered", sa.BigInteger, nullable=False),
        sa.Column("currency", sa.String(3), server_default="INR"),
        sa.Column(
            "recovered_via_action_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_actions.id"),
            nullable=True,
        ),
        sa.Column(
            "attributed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )
    op.execute("ALTER TABLE recovery_ledger ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY merchant_isolation ON recovery_ledger "
        "USING (merchant_id::text = current_setting('app.current_merchant_id', true))"
    )

    # ── usage ─────────────────────────────────────────────────────────────────
    op.create_table(
        "usage",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "merchant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("merchants.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("agent_calls", sa.Integer, server_default="0"),
        sa.Column("tokens_used", sa.BigInteger, server_default="0"),
        sa.Column("cost_estimate", sa.Float, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_usage_merchant_date", "usage", ["merchant_id", "date"], unique=True)

    # ── Superuser bypass so migrations/seed can still write ───────────────────
    # RLS does not apply to the table owner (superuser), so migrations work fine.
    # Application connections use a non-superuser role 'rra_app' that RLS applies to.
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'rra_app') THEN
                CREATE ROLE rra_app LOGIN PASSWORD 'rra_app_secret';
            END IF;
        END $$;
        """
    )
    for table in [
        "merchants", "customers", "payment_events", "orders_tracked",
        "invoices", "subscriptions_tracked", "risk_cases", "promises",
        "policies", "agent_actions", "audit_log", "recovery_ledger", "usage",
    ]:
        op.execute(f"GRANT ALL ON {table} TO rra_app")


def downgrade() -> None:
    tables = [
        "usage", "recovery_ledger", "audit_log", "agent_actions",
        "policies", "promises", "risk_cases", "subscriptions_tracked",
        "invoices", "orders_tracked", "payment_events", "customers", "merchants",
    ]
    for t in tables:
        op.drop_table(t)

    for enum in [
        "merchant_mode", "risk_source_type", "risk_case_status",
        "promise_status", "agent_action_status",
    ]:
        op.execute(f"DROP TYPE IF EXISTS {enum}")
