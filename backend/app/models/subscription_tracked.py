import uuid
from typing import TYPE_CHECKING
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.core.db import Base

if TYPE_CHECKING:
    from app.models.merchant import Merchant
    from app.models.customer import Customer



class SubscriptionTracked(Base):
    __tablename__ = "subscriptions_tracked"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    merchant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("merchants.id"), nullable=False, index=True
    )
    razorpay_subscription_id: Mapped[str] = mapped_column(
        String(64), unique=True, index=True
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id"), nullable=True
    )
    # active|pending|halted|cancelled|completed|expired
    status: Mapped[str] = mapped_column(String(32))
    last_charge_attempt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    halted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    merchant: Mapped["Merchant"] = relationship()
    customer: Mapped["Customer | None"] = relationship()
