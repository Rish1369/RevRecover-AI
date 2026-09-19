import uuid
from typing import TYPE_CHECKING
from datetime import datetime, timezone

from sqlalchemy import String, BigInteger, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.core.db import Base

if TYPE_CHECKING:
    from app.models.risk_case import RiskCase
    from app.models.merchant import Merchant



class RecoveryLedger(Base):
    """
    The single source of truth for recovered revenue.

    An entry is inserted by the measurement/attribution watcher when a payment
    matching a monitored risk case is confirmed within the attribution window.
    This is never inferred after the fact.
    """

    __tablename__ = "recovery_ledger"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    merchant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("merchants.id"), nullable=False, index=True
    )
    risk_case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("risk_cases.id"), nullable=False, index=True
    )
    amount_recovered: Mapped[int] = mapped_column(BigInteger, nullable=False)  # in paise
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    recovered_via_action_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_actions.id"), nullable=True
    )
    attributed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    merchant: Mapped["Merchant"] = relationship(back_populates="recovery_ledger_entries")
    risk_case: Mapped["RiskCase"] = relationship(back_populates="recovery_entries")
