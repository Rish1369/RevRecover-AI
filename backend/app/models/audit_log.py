import uuid
from typing import TYPE_CHECKING
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.core.db import Base

if TYPE_CHECKING:
    from app.models.merchant import Merchant



class AuditLog(Base):
    """
    Tamper-evident audit log.

    Each entry's `hash` is SHA-256(actor + action + target_id + created_at + prev_hash).
    The `prev_hash` field chains entries — any modification to an older row breaks the chain.
    """

    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    merchant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("merchants.id"), nullable=False, index=True
    )
    actor: Mapped[str] = mapped_column(String(128), nullable=False)  # "agent" | "system" | "human:<id>"
    action: Mapped[str] = mapped_column(String(256), nullable=False)
    target_id: Mapped[str | None] = mapped_column(String(64))
    detail: Mapped[str | None] = mapped_column(Text)
    prev_hash: Mapped[str | None] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    merchant: Mapped["Merchant"] = relationship(back_populates="audit_logs")
