"""
Policy engine — checks every proposed agent action against merchant guardrails.

Rules evaluated (in order):
  1. DNC:            customer flagged do_not_contact → skipped_dnc
  2. Tool allowed:   diagnosis_playbook gates which tools are valid for this diagnosis
  3. Attempt cap:    risk_case.attempts_count >= max_actions_per_case
  4. Auto-escalate:  2+ previous failed automated attempts on same case
  5. Cooldown:       last agent_action for this customer within cooldown_hours
  6. Contact hours:  SMS/email tools outside contact_hours_start–end window
  7. Spend ceiling:  today's cost_estimate >= max_agent_spend_per_day (in paise)
  8. Mandate compliance: immediate re-charge on mandate is always blocked

Every check — pass or fail — is written to the audit log.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.policy import Policy
from app.models.agent_action import AgentAction
from app.models.customer import Customer
from app.models.risk_case import RiskCase
from app.models.usage import Usage
from app.services.audit import append_audit

logger = logging.getLogger(__name__)

# Tools that are subject to contact-hours restrictions
CONTACT_HOUR_TOOLS = {"send_recovery_email", "send_recovery_sms"}

# Tools that require human approval (never auto-executed)
REQUIRES_HUMAN_APPROVAL = {"offer_payment_plan"}

# Mandate re-charge is always blocked (UPI Autopay compliance)
MANDATE_IMMEDIATE_RECHARGE_TOOLS = {"trigger_mandate_charge"}


@dataclass
class PolicyResult:
    allowed: bool
    reason: str
    action_status: str  # "approved" | "denied" | "skipped_dnc" | "escalated"


async def _get_policy(
    session: AsyncSession, merchant_id: uuid.UUID, key: str, default
):
    """Fetch a single policy value; return default if not set."""
    result = await session.execute(
        select(Policy.value)
        .where(Policy.merchant_id == merchant_id, Policy.key == key)
    )
    row = result.scalar_one_or_none()
    if row is None:
        return default
    # JSONB value is stored as {"v": actual_value} for scalars
    return row.get("v", default) if isinstance(row, dict) else default


async def check_policy(
    session: AsyncSession,
    merchant_id: uuid.UUID,
    risk_case: RiskCase,
    customer: Customer | None,
    tool_name: str,
    actor: str = "agent",
) -> PolicyResult:
    """
    Run all guardrail checks for a proposed tool call.
    Writes a pass/fail audit entry for every check.
    """

    async def _audit(action: str, detail: str, target: str | None = None):
        await append_audit(
            session, merchant_id, actor=actor,
            action=action, target_id=target, detail=detail
        )

    # ── 1. DNC check ─────────────────────────────────────────────────────────
    if customer and customer.do_not_contact:
        await _audit(
            "policy.dnc_block",
            f"Tool '{tool_name}' blocked: customer {customer.id} is on DNC list",
            target_id=str(risk_case.id),
        )
        return PolicyResult(False, "Customer is on do-not-contact list", "skipped_dnc")

    # ── 2. Diagnosis playbook check ───────────────────────────────────────────
    playbook_result = await session.execute(
        select(Policy.value)
        .where(
            Policy.merchant_id == merchant_id,
            Policy.key == "diagnosis_playbook",
        )
    )
    playbook_row = playbook_result.scalar_one_or_none()
    playbook: dict[str, list[str]] = playbook_row or {}

    diagnosis_code = risk_case.diagnosis_code or "unknown"
    allowed_tools = playbook.get(diagnosis_code, playbook.get("_default", None))

    if allowed_tools is not None and tool_name not in allowed_tools:
        await _audit(
            "policy.playbook_block",
            f"Tool '{tool_name}' not in playbook for diagnosis '{diagnosis_code}'. Allowed: {allowed_tools}",
            target_id=str(risk_case.id),
        )
        return PolicyResult(
            False,
            f"Tool '{tool_name}' is not in the allowed playbook for diagnosis '{diagnosis_code}'",
            "denied",
        )

    # ── 3. Attempt cap ────────────────────────────────────────────────────────
    max_attempts = int(await _get_policy(session, merchant_id, "max_actions_per_case", 3))
    if risk_case.attempts_count >= max_attempts:
        await _audit(
            "policy.attempt_cap",
            f"Attempt cap reached: {risk_case.attempts_count}/{max_attempts} for case {risk_case.id}",
            target_id=str(risk_case.id),
        )
        return PolicyResult(
            False,
            f"Attempt cap reached ({risk_case.attempts_count}/{max_attempts})",
            "escalated",
        )

    # ── 4. Auto-escalation: 2 prior failed automated actions ─────────────────
    failed_count_result = await session.execute(
        select(func.count(AgentAction.id))
        .where(
            AgentAction.risk_case_id == risk_case.id,
            AgentAction.status.in_(["failed", "denied"]),
        )
    )
    failed_count = failed_count_result.scalar_one()
    if failed_count >= 2:
        await _audit(
            "policy.auto_escalate",
            f"2+ failed/denied actions on case {risk_case.id}; escalating to human",
            target_id=str(risk_case.id),
        )
        return PolicyResult(
            False,
            f"Auto-escalation: {failed_count} failed/denied actions on this case",
            "escalated",
        )

    # ── 5. Cooldown check ─────────────────────────────────────────────────────
    if customer:
        cooldown_hours = float(await _get_policy(session, merchant_id, "cooldown_hours", 4.0))
        since = datetime.now(timezone.utc) - timedelta(hours=cooldown_hours)
        recent_result = await session.execute(
            select(AgentAction)
            .join(RiskCase, AgentAction.risk_case_id == RiskCase.id)
            .where(
                RiskCase.customer_id == customer.id,
                AgentAction.merchant_id == merchant_id,
                AgentAction.created_at >= since,
                AgentAction.status.in_(["executed", "approved"]),
            )
            .limit(1)
        )
        recent = recent_result.scalar_one_or_none()
        if recent:
            next_ok = recent.created_at + timedelta(hours=cooldown_hours)
            await _audit(
                "policy.cooldown_block",
                f"Cooldown active: last touch at {recent.created_at.isoformat()}; next allowed after {next_ok.isoformat()}",
                target_id=str(risk_case.id),
            )
            return PolicyResult(
                False,
                f"Cooldown: next action allowed after {next_ok.isoformat()}",
                "denied",
            )

    # ── 6. Contact hours check (SMS / email) ──────────────────────────────────
    if tool_name in CONTACT_HOUR_TOOLS:
        now_hour = datetime.now(timezone.utc).hour  # assumes IST offset handled by merchant config
        start = int(await _get_policy(session, merchant_id, "contact_hours_start", 9))
        end = int(await _get_policy(session, merchant_id, "contact_hours_end", 21))
        if not (start <= now_hour < end):
            await _audit(
                "policy.contact_hours_block",
                f"Tool '{tool_name}' blocked at {now_hour}h UTC (window {start}–{end}h)",
                target_id=str(risk_case.id),
            )
            return PolicyResult(
                False,
                f"Contact hours: '{tool_name}' not permitted at {now_hour}h UTC (allowed {start}–{end}h)",
                "denied",
            )

    # ── 7. Daily spend ceiling ─────────────────────────────────────────────────
    max_spend = float(await _get_policy(session, merchant_id, "max_agent_spend_per_day", 100_00000))  # ₹1L default
    today = datetime.now(timezone.utc).date()
    spend_result = await session.execute(
        select(Usage.cost_estimate)
        .where(Usage.merchant_id == merchant_id, Usage.date == today)
    )
    today_spend = spend_result.scalar_one_or_none() or 0.0
    if today_spend >= max_spend:
        await _audit(
            "policy.spend_ceiling",
            f"Daily spend ceiling hit: ${today_spend:.4f} >= ${max_spend:.4f}",
            target_id=str(risk_case.id),
        )
        return PolicyResult(
            False,
            f"Daily agent spend ceiling reached (${today_spend:.4f}/${max_spend:.4f})",
            "denied",
        )

    # ── 8. Mandate compliance ─────────────────────────────────────────────────
    if tool_name in MANDATE_IMMEDIATE_RECHARGE_TOOLS:
        await _audit(
            "policy.mandate_block",
            f"Immediate mandate re-charge via '{tool_name}' is always blocked (UPI Autopay compliance)",
            target_id=str(risk_case.id),
        )
        return PolicyResult(
            False,
            "Mandate immediate re-charge is prohibited by UPI Autopay compliance rules",
            "denied",
        )

    # ── 9. Human approval required ────────────────────────────────────────────
    if tool_name in REQUIRES_HUMAN_APPROVAL:
        await _audit(
            "policy.requires_approval",
            f"Tool '{tool_name}' requires human approval; escalating",
            target_id=str(risk_case.id),
        )
        return PolicyResult(
            False,
            f"Tool '{tool_name}' always requires human approval",
            "escalated",
        )

    # ── All checks passed ─────────────────────────────────────────────────────
    await _audit(
        "policy.approved",
        f"Tool '{tool_name}' approved for case {risk_case.id} (diagnosis: {diagnosis_code})",
        target_id=str(risk_case.id),
    )
    return PolicyResult(True, "All policy checks passed", "approved")
