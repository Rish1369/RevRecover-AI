import uuid
from typing import TYPE_CHECKING
from datetime import datetime, timezone

from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.core.db import Base

if TYPE_CHECKING:
    from app.models.merchant import Merchant
    from app.models.recovery_ledger import RecoveryLedger
    from app.models.promise import Promise
    from app.models.customer import Customer
    from app.models.agent_action import AgentAction


# All possible source types
SOURCE_TYPES = ("payment_failure", "dropoff", "overdue_invoice", "subscription", "mandate")

# All possible statuses
RISK_CASE_STATUSES = (
    "detected",
    "diagnosed",
    "action_taken",
    "monitoring",
    "recovered",
    "escalated",
    "closed_unrecovered",
)


class RiskCase(Base):
    __tablename__ = "risk_cases"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    merchant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("merchants.id"), nullable=False, index=True
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id"), nullable=True, index=True
    )
    source_type: Mapped[str] = mapped_column(
        SAEnum(*SOURCE_TYPES, name="risk_source_type"), nullable=False
    )
    source_id: Mapped[str | None] = mapped_column(String(64), index=True)

    # Diagnosis
    diagnosis_code: Mapped[str | None] = mapped_column(String(64))
    diagnosis_confidence: Mapped[float | None] = mapped_column(Float)

    risk_score: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(
        SAEnum(*RISK_CASE_STATUSES, name="risk_case_status"),
        nullable=False,
        default="detected",
    )
    attempts_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    merchant: Mapped["Merchant"] = relationship(back_populates="risk_cases")
    customer: Mapped["Customer | None"] = relationship(back_populates="risk_cases")
    agent_actions: Mapped[list["AgentAction"]] = relationship(back_populates="risk_case")
    promises: Mapped[list["Promise"]] = relationship(back_populates="risk_case")
    recovery_entries: Mapped[list["RecoveryLedger"]] = relationship(
        back_populates="risk_case"
    )
