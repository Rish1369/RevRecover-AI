import uuid
from typing import TYPE_CHECKING
from datetime import datetime, timezone

from sqlalchemy import String, BigInteger, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.core.db import Base

if TYPE_CHECKING:
    from app.models.merchant import Merchant
    from app.models.customer import Customer



class PaymentEvent(Base):
    __tablename__ = "payment_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    merchant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("merchants.id"), nullable=False, index=True
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id"), nullable=True, index=True
    )
    razorpay_payment_id: Mapped[str | None] = mapped_column(String(64), index=True)
    amount: Mapped[int | None] = mapped_column(BigInteger)  # in paise
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    status: Mapped[str] = mapped_column(String(32))  # created|authorized|captured|failed
    error_code: Mapped[str | None] = mapped_column(String(128))
    error_reason: Mapped[str | None] = mapped_column(String(512))
    raw_payload: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    merchant: Mapped["Merchant"] = relationship(back_populates="payment_events")
    customer: Mapped["Customer | None"] = relationship(back_populates="payment_events")
