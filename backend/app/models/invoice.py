import uuid
from datetime import datetime, timezone, date
from typing import TYPE_CHECKING

from sqlalchemy import String, BigInteger, DateTime, Date, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.core.db import Base

if TYPE_CHECKING:
    from app.models.merchant import Merchant
    from app.models.customer import Customer


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    merchant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("merchants.id"), nullable=False, index=True
    )
    razorpay_invoice_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id"), nullable=True
    )
    amount: Mapped[int] = mapped_column(BigInteger)       # in paise
    amount_paid: Mapped[int] = mapped_column(BigInteger, default=0)
    due_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(32))       # draft|issued|paid|cancelled|expired
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    merchant: Mapped["Merchant"] = relationship()
    customer: Mapped["Customer | None"] = relationship()
