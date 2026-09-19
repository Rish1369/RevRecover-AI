import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, ForeignKey, Text, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.core.db import Base
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.merchant import Merchant
    from app.models.risk_case import RiskCase

ACTION_STATUSES = ("pending", "approved", "denied", "executed", "failed", "skipped_dnc", "escalated")


class AgentAction(Base):
    """
    Records every action the agent proposes, the policy check result,
    and the final execution outcome. Denials are logged too — not silently dropped.
    """

    __tablename__ = "agent_actions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    merchant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("merchants.id"), nullable=False, index=True
    )
    risk_case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("risk_cases.id"), nullable=False, index=True
    )
    tool_name: Mapped[str] = mapped_column(String(64), nullable=False)
    input_json: Mapped[dict | None] = mapped_column(JSONB)
    reasoning_summary: Mapped[str | None] = mapped_column(Text)
    policy_check_result: Mapped[str | None] = mapped_column(String(16))  # allowed|denied
    policy_check_reason: Mapped[str | None] = mapped_column(Text)
    output_json: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(
        SAEnum(*ACTION_STATUSES, name="agent_action_status"),
        nullable=False,
        default="pending",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    merchant: Mapped["Merchant"] = relationship(back_populates="agent_actions")
    risk_case: Mapped["RiskCase"] = relationship(back_populates="agent_actions")
