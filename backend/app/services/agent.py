"""
Claude-powered agent loop.

Flow:
  1. Build system prompt with merchant guardrails injected explicitly
  2. Call Claude with the risk case, diagnosis, customer history, and tool definitions
  3. Receive a tool_use block
  4. Run through the policy engine
  5. If approved → execute against Razorpay → log AgentAction (executed)
  6. If denied   → log AgentAction (denied/skipped_dnc/escalated) → force escalate_to_human
  7. Update risk_case.status and attempts_count
  8. Update usage metrics
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

import anthropic
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.settings import get_settings
from app.models.agent_action import AgentAction
from app.models.customer import Customer
from app.models.merchant import Merchant
from app.models.risk_case import RiskCase
from app.models.usage import Usage
from app.services.audit import append_audit
from app.services.policy_engine import check_policy
from app.services import razorpay_client as rzp

settings = get_settings()
logger = logging.getLogger(__name__)

_anthropic = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

MODEL = "claude-sonnet-4-5"

# ── Tool definitions sent to Claude ──────────────────────────────────────────

TOOL_DEFINITIONS = [
    {
        "name": "create_payment_link",
        "description": "Create a Razorpay payment link and send it to the customer. Use for insufficient_funds, technical_error, or price_hesitation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "amount_paise": {"type": "integer", "description": "Amount in paise (₹1 = 100 paise)"},
                "description": {"type": "string"},
                "notify_email": {"type": "boolean"},
                "notify_sms": {"type": "boolean"},
            },
            "required": ["amount_paise"],
        },
    },
    {
        "name": "send_recovery_email",
        "description": "Send a recovery email to the customer. Allowed for all diagnosis codes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "subject": {"type": "string"},
                "body_summary": {"type": "string", "description": "Summary of the email body"},
            },
            "required": ["subject", "body_summary"],
        },
    },
    {
        "name": "send_recovery_sms",
        "description": "Send a recovery SMS. Subject to DNC and contact hours policy.",
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "maxLength": 160},
            },
            "required": ["message"],
        },
    },
    {
        "name": "offer_discount_link",
        "description": "Create a discounted payment link. Only for price_hesitation diagnosis.",
        "input_schema": {
            "type": "object",
            "properties": {
                "original_amount_paise": {"type": "integer"},
                "discount_pct": {"type": "number", "description": "Discount percentage e.g. 10 for 10%"},
            },
            "required": ["original_amount_paise", "discount_pct"],
        },
    },
    {
        "name": "resend_invoice",
        "description": "Resend invoice via Razorpay. Only for early_overdue diagnosis.",
        "input_schema": {
            "type": "object",
            "properties": {
                "razorpay_invoice_id": {"type": "string"},
            },
            "required": ["razorpay_invoice_id"],
        },
    },
    {
        "name": "offer_payment_plan",
        "description": "Propose a payment plan. Only for chronic_late_payer. ALWAYS requires human approval — will be escalated.",
        "input_schema": {
            "type": "object",
            "properties": {
                "plan_summary": {"type": "string"},
                "installments": {"type": "integer"},
            },
            "required": ["plan_summary"],
        },
    },
    {
        "name": "send_mandate_update_link",
        "description": "Send a UPI/NACH mandate update link. Only for mandate_expired.",
        "input_schema": {
            "type": "object",
            "properties": {
                "subscription_id": {"type": "string"},
            },
            "required": ["subscription_id"],
        },
    },
    {
        "name": "log_promise_to_pay",
        "description": "Record a customer's promise to pay by a specific date.",
        "input_schema": {
            "type": "object",
            "properties": {
                "promised_date": {"type": "string", "format": "date"},
                "promised_amount_paise": {"type": "integer"},
            },
            "required": ["promised_date", "promised_amount_paise"],
        },
    },
    {
        "name": "escalate_to_human",
        "description": "Hand off this case to the human review queue. Always available.",
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {"type": "string"},
            },
            "required": ["reason"],
        },
    },
]


def _build_system_prompt(merchant: Merchant, policies: dict) -> str:
    return f"""You are a revenue recovery agent for {merchant.name}.

Your job is to choose ONE action from the tool list to recover a failed payment or at-risk case.
Every proposed action will be checked against merchant guardrails BEFORE execution — you do not need
to re-check policies yourself, but you must stay within the spirit of the following rules:

MERCHANT GUARDRAILS:
- Max actions per case: {policies.get('max_actions_per_case', 3)}
- Cooldown between touches: {policies.get('cooldown_hours', 4)} hours
- Contact hours: {policies.get('contact_hours_start', 9)}:00 – {policies.get('contact_hours_end', 21)}:00
- Max discount: {policies.get('max_discount_pct', 10)}%
- Respect DNC list: always
- Mandate compliance: never trigger immediate re-charge; only notify-and-wait

DIAGNOSIS PLAYBOOK (tools allowed per diagnosis):
- insufficient_funds:   create_payment_link, send_recovery_email, send_recovery_sms
- card_expired:         send_recovery_email, send_recovery_sms
- bank_declined:        create_payment_link, send_recovery_email
- technical_error:      create_payment_link, send_recovery_email
- customer_cancelled:   send_recovery_email, log_promise_to_pay, escalate_to_human
- price_hesitation:     offer_discount_link, create_payment_link, send_recovery_email
- payment_method_friction: create_payment_link, send_recovery_sms
- repeat_abandoner:     send_recovery_email, log_promise_to_pay
- first_time_failure:   create_payment_link, send_recovery_email
- recurring_failure:    send_recovery_email, offer_payment_plan
- mandate_expired:      send_mandate_update_link
- early_overdue:        resend_invoice, send_recovery_email
- chronic_late_payer:   offer_payment_plan, escalate_to_human
- disputed_likely:      escalate_to_human

RULES:
1. Always pick the LEAST intrusive effective action first.
2. If the diagnosis is ambiguous or no tool seems right, call escalate_to_human.
3. Do NOT call more than one tool per response — choose the single best action.
4. Be concise in your reasoning; it will be stored in the audit trail.
"""


async def _load_policies(session: AsyncSession, merchant_id: uuid.UUID) -> dict:
    from app.models.policy import Policy
    result = await session.execute(
        select(Policy).where(Policy.merchant_id == merchant_id)
    )
    policies_rows = result.scalars().all()
    out = {}
    for row in policies_rows:
        val = row.value
        out[row.key] = val.get("v", val) if isinstance(val, dict) and "v" in val else val
    return out


async def _update_usage(
    session: AsyncSession,
    merchant_id: uuid.UUID,
    input_tokens: int,
    output_tokens: int,
):
    today = datetime.now(timezone.utc).date()
    result = await session.execute(
        select(Usage).where(Usage.merchant_id == merchant_id, Usage.date == today)
    )
    usage = result.scalar_one_or_none()
    # Rough cost estimate: claude-sonnet ≈ $3/M input, $15/M output
    cost = (input_tokens / 1_000_000) * 3.0 + (output_tokens / 1_000_000) * 15.0
    total_tokens = input_tokens + output_tokens
    if usage:
        usage.agent_calls += 1
        usage.tokens_used += total_tokens
        usage.cost_estimate += cost
    else:
        session.add(Usage(
            merchant_id=merchant_id,
            date=today,
            agent_calls=1,
            tokens_used=total_tokens,
            cost_estimate=cost,
        ))


async def _execute_tool(
    merchant: Merchant,
    customer: Customer | None,
    risk_case: RiskCase,
    tool_name: str,
    tool_input: dict,
) -> dict:
    """Execute the approved tool against Razorpay. Returns output dict."""
    c_name = customer.name if customer else None
    c_email = customer.email if customer else None
    c_phone = customer.phone if customer else None

    if tool_name == "create_payment_link":
        return rzp.create_payment_link(
            merchant,
            amount_paise=tool_input["amount_paise"],
            customer_name=c_name,
            customer_email=c_email,
            customer_phone=c_phone,
            description=tool_input.get("description", "Payment Recovery"),
        )

    elif tool_name == "offer_discount_link":
        return rzp.create_discount_payment_link(
            merchant,
            original_amount_paise=tool_input["original_amount_paise"],
            discount_pct=tool_input["discount_pct"],
            customer_name=c_name,
            customer_email=c_email,
            customer_phone=c_phone,
        )

    elif tool_name == "resend_invoice":
        return rzp.resend_invoice(merchant, tool_input["razorpay_invoice_id"])

    elif tool_name == "send_mandate_update_link":
        return rzp.send_mandate_update_link(
            merchant,
            subscription_id=tool_input["subscription_id"],
            customer_email=c_email,
            customer_phone=c_phone,
        )

    elif tool_name in {"send_recovery_email", "send_recovery_sms"}:
        # In Phase 1 we log the intended message; email/SMS gateway integration in Phase 2
        logger.info("MOCK %s | merchant=%s | customer=%s | payload=%s", tool_name, merchant.id, customer and customer.id, tool_input)
        return {"status": "queued", "channel": tool_name, "payload": tool_input}

    elif tool_name == "log_promise_to_pay":
        return {"status": "logged", **tool_input}

    elif tool_name == "escalate_to_human":
        return {"status": "escalated", "reason": tool_input.get("reason", "")}

    else:
        raise ValueError(f"Unknown tool: {tool_name}")


async def run_agent(
    session: AsyncSession,
    merchant: Merchant,
    risk_case: RiskCase,
    customer: Customer | None,
) -> AgentAction:
    """
    Run one iteration of the agent loop for the given risk case.
    Returns the AgentAction record created.
    """
    policies = await _load_policies(session, merchant.id)

    # Build context for Claude
    user_message = f"""
RISK CASE:
  ID:             {risk_case.id}
  Source type:    {risk_case.source_type}
  Source ID:      {risk_case.source_id}
  Diagnosis:      {risk_case.diagnosis_code} (confidence {risk_case.diagnosis_confidence or 0:.0%})
  Status:         {risk_case.status}
  Attempts so far: {risk_case.attempts_count}
  Created:        {risk_case.created_at.isoformat()}

CUSTOMER:
  ID:     {customer.id if customer else 'unknown'}
  Name:   {customer.name if customer else 'unknown'}
  Email:  {customer.email if customer else 'unknown'}
  Phone:  {customer.phone if customer else 'unknown'}

Choose ONE action to take now. Provide a one-sentence reasoning_summary.
""".strip()

    # Call Claude
    response = _anthropic.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=_build_system_prompt(merchant, policies),
        tools=TOOL_DEFINITIONS,
        messages=[{"role": "user", "content": user_message}],
        tool_choice={"type": "any"},  # force a tool call
    )

    await _update_usage(
        session, merchant.id,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
    )

    # Extract tool call
    tool_use_block = next(
        (b for b in response.content if b.type == "tool_use"), None
    )
    if not tool_use_block:
        logger.warning("Agent returned no tool_use block for case %s", risk_case.id)
        tool_name = "escalate_to_human"
        tool_input = {"reason": "Agent returned no tool call"}
        reasoning = "No tool_use block in response"
    else:
        tool_name = tool_use_block.name
        tool_input = tool_use_block.input
        # Extract text reasoning if present
        text_block = next((b for b in response.content if b.type == "text"), None)
        reasoning = text_block.text[:500] if text_block else f"Tool: {tool_name}"

    # Create AgentAction record (pending)
    action = AgentAction(
        merchant_id=merchant.id,
        risk_case_id=risk_case.id,
        tool_name=tool_name,
        input_json=tool_input,
        reasoning_summary=reasoning,
        status="pending",
    )
    session.add(action)
    await session.flush()  # get action.id

    # Run policy engine
    policy_result = await check_policy(
        session, merchant.id, risk_case, customer, tool_name, actor="agent"
    )

    action.policy_check_result = policy_result.action_status
    action.policy_check_reason = policy_result.reason
    action.status = policy_result.action_status

    if not policy_result.allowed:
        # Force escalate_to_human and log
        await append_audit(
            session, merchant.id, actor="policy_engine",
            action=f"action.denied.{policy_result.action_status}",
            target_id=str(action.id),
            detail=policy_result.reason,
        )
        # If the block is an escalation, mark the case escalated
        if policy_result.action_status == "escalated":
            risk_case.status = "escalated"
        return action

    # Execute the tool
    try:
        output = await _execute_tool(merchant, customer, risk_case, tool_name, tool_input)
        action.output_json = output
        action.status = "executed"
        risk_case.attempts_count += 1

        if tool_name == "escalate_to_human":
            risk_case.status = "escalated"
        else:
            risk_case.status = "monitoring"

        await append_audit(
            session, merchant.id, actor="agent",
            action=f"action.executed.{tool_name}",
            target_id=str(action.id),
            detail=json.dumps(output)[:500],
        )
        logger.info("Agent executed %s for case %s", tool_name, risk_case.id)

    except Exception as exc:
        action.status = "failed"
        action.output_json = {"error": str(exc)}
        await append_audit(
            session, merchant.id, actor="agent",
            action=f"action.failed.{tool_name}",
            target_id=str(action.id),
            detail=str(exc),
        )
        logger.error("Tool %s failed for case %s: %s", tool_name, risk_case.id, exc)

    return action
