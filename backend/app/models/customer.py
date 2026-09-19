import uuid
from typing import TYPE_CHECKING
from datetime import datetime, timezone

from sqlalchemy import String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.core.db import Base

if TYPE_CHECKING:
    from app.models.risk_case import RiskCase
    from app.models.merchant import Merchant
    from app.models.payment_event import PaymentEvent



class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    merchant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("merchants.id"), nullable=False, index=True
    )
    name: Mapped[str | None] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(20))
    razorpay_customer_id: Mapped[str | None] = mapped_column(String(64), index=True)
    do_not_contact: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    merchant: Mapped["Merchant"] = relationship(back_populates="customers")
    payment_events: Mapped[list["PaymentEvent"]] = relationship(back_populates="customer")
    risk_cases: Mapped[list["RiskCase"]] = relationship(back_populates="customer")
