import uuid
from typing import TYPE_CHECKING
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.core.db import Base

if TYPE_CHECKING:
    from app.models.merchant import Merchant



class Policy(Base):
    """
    Per-merchant key-value policy store.

    Example keys:
      - max_actions_per_case        (int)
      - cooldown_hours              (float)
      - contact_hours_start         (int, 24h)
      - contact_hours_end           (int, 24h)
      - max_discount_pct            (float)
      - max_agent_spend_per_day     (int, in paise)
      - dnc_respect                 (bool)
      - diagnosis_playbook          (dict: diagnosis_code -> [allowed_tools])
    """

    __tablename__ = "policies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    merchant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("merchants.id"), nullable=False, index=True
    )
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    merchant: Mapped["Merchant"] = relationship(back_populates="policies")
