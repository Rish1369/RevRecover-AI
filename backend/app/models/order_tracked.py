import uuid
from typing import TYPE_CHECKING
from datetime import datetime, timezone

from sqlalchemy import String, BigInteger, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.core.db import Base

if TYPE_CHECKING:
    from app.models.merchant import Merchant
    from app.models.customer import Customer



class OrderTracked(Base):
    __tablename__ = "orders_tracked"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    merchant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("merchants.id"), nullable=False, index=True
    )
    razorpay_order_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id"), nullable=True
    )
    amount: Mapped[int] = mapped_column(BigInteger)  # in paise
    status: Mapped[str] = mapped_column(String(32))  # created|attempted|paid
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    checkout_opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expired_flagged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    merchant: Mapped["Merchant"] = relationship()
    customer: Mapped["Customer | None"] = relationship()
