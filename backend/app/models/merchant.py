import uuid
from typing import TYPE_CHECKING
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.core.db import Base

if TYPE_CHECKING:
    from app.models.audit_log import AuditLog
    from app.models.risk_case import RiskCase
    from app.models.policy import Policy
    from app.models.recovery_ledger import RecoveryLedger
    from app.models.customer import Customer
    from app.models.payment_event import PaymentEvent
    from app.models.agent_action import AgentAction



class Merchant(Base):
    __tablename__ = "merchants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    razorpay_key_id: Mapped[str] = mapped_column(String(255), nullable=False)
    # Stored encrypted via Fernet
    razorpay_key_secret_enc: Mapped[str] = mapped_column(String(512), nullable=False)
    razorpay_webhook_secret_enc: Mapped[str] = mapped_column(String(512), nullable=False)
    mode: Mapped[str] = mapped_column(
        SAEnum("test", "live", name="merchant_mode"), nullable=False, default="test"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    customers: Mapped[list["Customer"]] = relationship(back_populates="merchant")
    payment_events: Mapped[list["PaymentEvent"]] = relationship(back_populates="merchant")
    risk_cases: Mapped[list["RiskCase"]] = relationship(back_populates="merchant")
    policies: Mapped[list["Policy"]] = relationship(back_populates="merchant")
    agent_actions: Mapped[list["AgentAction"]] = relationship(back_populates="merchant")
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="merchant")
    recovery_ledger_entries: Mapped[list["RecoveryLedger"]] = relationship(
        back_populates="merchant"
    )
