import uuid
from typing import TYPE_CHECKING
from datetime import datetime, timezone, date

from sqlalchemy import String, BigInteger, DateTime, Date, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.core.db import Base

if TYPE_CHECKING:
    from app.models.risk_case import RiskCase


PROMISE_STATUSES = ("pending", "kept", "broken", "cancelled")


class Promise(Base):
    """Promise-to-pay tracker — created when a customer commits to paying by a date."""

    __tablename__ = "promises"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    risk_case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("risk_cases.id"), nullable=False, index=True
    )
    promised_date: Mapped[date] = mapped_column(Date, nullable=False)
    promised_amount: Mapped[int] = mapped_column(BigInteger)  # in paise
    status: Mapped[str] = mapped_column(
        SAEnum(*PROMISE_STATUSES, name="promise_status"),
        nullable=False,
        default="pending",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    risk_case: Mapped["RiskCase"] = relationship(back_populates="promises")
