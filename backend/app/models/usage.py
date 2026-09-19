import uuid
from typing import TYPE_CHECKING
from datetime import datetime, timezone, date

from sqlalchemy import String, BigInteger, Integer, Float, DateTime, Date, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.core.db import Base

if TYPE_CHECKING:
    from app.models.merchant import Merchant



class Usage(Base):
    """Per-merchant daily usage metrics for cost tracking."""

    __tablename__ = "usage"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    merchant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("merchants.id"), nullable=False, index=True
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    agent_calls: Mapped[int] = mapped_column(Integer, default=0)
    tokens_used: Mapped[int] = mapped_column(BigInteger, default=0)
    cost_estimate: Mapped[float] = mapped_column(Float, default=0.0)  # in USD
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    merchant: Mapped["Merchant"] = relationship()
