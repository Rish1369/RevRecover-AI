"""
Groq-powered agent loop (replaces Gemini).

Flow:
  1. Build system prompt with merchant guardrails
  2. Call Groq (llama-3.3-70b-versatile) with JSON-mode for structured tool selection
  3. Parse the tool + args from the JSON response
  4. Run through the policy engine
  5. If approved → execute against Razorpay → log AgentAction (executed)
  6. If denied   → log AgentAction (denied/skipped_dnc/escalated) → force escalate_to_human
  7. Update risk_case.status and attempts_count
  8. Update usage metrics
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timezone

from groq import Groq, RateLimitError, APIError
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

# ── Groq client (synchronous SDK; we run it in an executor) ───────────────────
_client = Groq(api_key=settings.GROQ_API_KEY)
MODEL = settings.GROQ_MODEL  # default: "llama-3.3-70b-versatile"

# ── Allowed tool names ─────────────────────────────────────────────────────────
ALLOWED_TOOLS = [
    "create_payment_link",
    "send_recovery_email",
    "send_recovery_sms",
    "offer_discount_link",
    "resend_invoice",
    "offer_payment_plan",
    "send_mandate_update_link",
    "log_promise_to_pay",
    "escalate_to_human",
]

# ── Tool schemas injected into the system prompt ──────────────────────────────
TOOL_SCHEMAS = {
    "create_payment_link": {
        "description": "Create a Razorpay payment link and send it to the customer. Use for insufficient_funds, technical_error, or price_hesitation.",
        "required": ["amount_paise"],
        "properties": {
            "amount_paise": "integer – Amount in paise (₹1 = 100 paise)",
            "description": "string – optional description",
            "notify_email": "boolean",
            "notify_sms": "boolean",
        },
    },
    "send_recovery_email": {
        "description": "Send a recovery email to the customer. Allowed for all diagnosis codes.",
        "required": ["subject", "body_summary"],
        "properties": {
            "subject": "string",
            "body_summary": "string – Summary of the email body",
        },
    },
    "send_recovery_sms": {
        "description": "Send a recovery SMS. Subject to DNC and contact hours policy.",
        "required": ["message"],
        "properties": {"message": "string – max 160 chars"},
    },
    "offer_discount_link": {
        "description": "Create a discounted payment link. Only for price_hesitation diagnosis.",
        "required": ["original_amount_paise", "discount_pct"],
        "properties": {
            "original_amount_paise": "integer",
            "discount_pct": "number – e.g. 10 for 10%",
        },
    },
    "resend_invoice": {
        "description": "Resend invoice via Razorpay. Only for early_overdue diagnosis.",
        "required": ["razorpay_invoice_id"],
        "properties": {"razorpay_invoice_id": "string"},
    },
    "offer_payment_plan": {
        "description": "Propose a payment plan. Only for chronic_late_payer. ALWAYS requires human approval.",
        "required": ["plan_summary"],
        "properties": {
            "plan_summary": "string",
            "installments": "integer – optional",
        },
    },
    "send_mandate_update_link": {
        "description": "Send a UPI/NACH mandate update link. Only for mandate_expired.",
        "required": ["subscription_id"],
        "properties": {"subscription_id": "string"},
    },
    "log_promise_to_pay": {
        "description": "Record a customer's promise to pay by a specific date.",
        "required": ["promised_date", "promised_amount_paise"],
        "properties": {
            "promised_date": "string – YYYY-MM-DD",
            "promised_amount_paise": "integer",
        },
    },
    "escalate_to_human": {
        "description": "Hand off this case to the human review queue. Always available.",
        "required": ["reason"],
        "properties": {"reason": "string"},
    },
}


def _build_system_prompt(merchant: Merchant, policies: dict) -> str:
    tool_doc = "\n".join(
        f"  - {name}: {meta['description']}  Required fields: {meta['required']}"
        for name, meta in TOOL_SCHEMAS.items()
    )
    return f"""You are a revenue recovery agent for {merchant.name}.

Your ONLY job: choose ONE tool call from the list below to recover a failed payment or at-risk case.
Respond with ONLY valid JSON in this exact shape — no markdown, no prose, no extra keys:
{{
  "tool": "<tool_name>",
  "args": {{<key>: <value>, ...}},
  "reasoning": "<one sentence explaining the choice>"
}}

AVAILABLE TOOLS:
{tool_doc}

MERCHANT GUARDRAILS:
- Max actions per case: {policies.get('max_actions_per_case', 3)}
- Cooldown between touches: {policies.get('cooldown_hours', 4)} hours
- Contact hours: {policies.get('contact_hours_start', 9)}:00 – {policies.get('contact_hours_end', 21)}:00
- Max discount: {policies.get('max_discount_pct', 10)}%
- Respect DNC list: always
- Mandate compliance: never trigger immediate re-charge; only notify-and-wait

DIAGNOSIS PLAYBOOK (tools allowed per diagnosis):
- insufficient_funds:       create_payment_link, send_recovery_email, send_recovery_sms
- card_expired:             send_recovery_email, send_recovery_sms
- bank_declined:            create_payment_link, send_recovery_email
- technical_error:          create_payment_link, send_recovery_email
- customer_cancelled:       send_recovery_email, log_promise_to_pay, escalate_to_human
- price_hesitation:         offer_discount_link, create_payment_link, send_recovery_email
- payment_method_friction:  create_payment_link, send_recovery_sms
- repeat_abandoner:         send_recovery_email, log_promise_to_pay
- first_time_failure:       create_payment_link, send_recovery_email
- recurring_failure:        send_recovery_email, offer_payment_plan
- mandate_expired:          send_mandate_update_link
- early_overdue:            resend_invoice, send_recovery_email
- chronic_late_payer:       offer_payment_plan, escalate_to_human
- disputed_likely:          escalate_to_human

RULES:
1. Always pick the LEAST intrusive effective action first.
2. If the diagnosis is ambiguous or no tool seems right, call escalate_to_human.
3. Do NOT call more than one tool — choose the single best action.
4. Your response MUST be valid JSON only — no markdown fences, no extra text.
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
    # Groq llama-3.3-70b-versatile pricing: ~$0.59/M input, $0.79/M output
    cost = (input_tokens / 1_000_000) * 0.59 + (output_tokens / 1_000_000) * 0.79
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
        # Phase 1: log intent; real gateway in Phase 2
        logger.info(
            "MOCK %s | merchant=%s | customer=%s | payload=%s",
            tool_name, merchant.id, customer and customer.id, tool_input,
        )
        return {"status": "queued", "channel": tool_name, "payload": tool_input}

    elif tool_name == "log_promise_to_pay":
        return {"status": "logged", **tool_input}

    elif tool_name == "escalate_to_human":
        return {"status": "escalated", "reason": tool_input.get("reason", "")}

    else:
        raise ValueError(f"Unknown tool: {tool_name}")


def _call_groq_sync(
    system_prompt: str,
    user_message: str,
    max_retries: int = 5,
    initial_delay: float = 8.0,
) -> tuple[str, int, int]:
    """
    Synchronous Groq call with exponential backoff on rate-limit errors.
    Returns (raw_json_text, input_tokens, output_tokens).
    """
    delay = initial_delay
    for attempt in range(max_retries):
        try:
            response = _client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.1,
                max_tokens=512,
                response_format={"type": "json_object"},
            )
            text = response.choices[0].message.content or ""
            input_tokens = response.usage.prompt_tokens if response.usage else 0
            output_tokens = response.usage.completion_tokens if response.usage else 0
            return text, input_tokens, output_tokens

        except RateLimitError as exc:
            if attempt == max_retries - 1:
                logger.error("Groq rate limit max retries (%d) exhausted.", max_retries)
                raise exc
            logger.warning(
                "Groq 429 rate limit hit (attempt %d/%d). Sleeping %.1fs...",
                attempt + 1, max_retries, delay,
            )
            time.sleep(delay)
            delay = min(delay * 2, 120)  # cap at 2 minutes

        except APIError as exc:
            logger.error("Groq API error: %s", exc)
            raise exc

    raise RuntimeError("Groq call exhausted retries without success or exception")


async def _call_groq(system_prompt: str, user_message: str) -> tuple[str, int, int]:
    """Async wrapper — runs the blocking Groq call in the default thread pool."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, _call_groq_sync, system_prompt, user_message
    )


def _parse_tool_response(raw: str) -> tuple[str, dict, str]:
    """
    Parse JSON from Groq response.
    Returns (tool_name, args_dict, reasoning).
    Falls back to escalate_to_human on parse failure.
    """
    try:
        data = json.loads(raw)
        tool_name = str(data.get("tool", "")).strip()
        args = data.get("args", {})
        reasoning = str(data.get("reasoning", ""))
        if tool_name not in ALLOWED_TOOLS:
            logger.warning("Agent returned unknown tool '%s', escalating.", tool_name)
            return "escalate_to_human", {"reason": f"Unknown tool: {tool_name}"}, reasoning
        if not isinstance(args, dict):
            args = {}
        return tool_name, args, reasoning
    except (json.JSONDecodeError, TypeError, AttributeError) as exc:
        logger.warning("Failed to parse Groq JSON: %s | raw=%s", exc, raw[:200])
        return "escalate_to_human", {"reason": "Agent JSON parse error"}, raw[:200]


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
    system_prompt = _build_system_prompt(merchant, policies)

    user_message = f"""RISK CASE:
  ID:              {risk_case.id}
  Source type:     {risk_case.source_type}
  Source ID:       {risk_case.source_id}
  Diagnosis:       {risk_case.diagnosis_code} (confidence {risk_case.diagnosis_confidence or 0:.0%})
  Status:          {risk_case.status}
  Attempts so far: {risk_case.attempts_count}
  Created:         {risk_case.created_at.isoformat()}

CUSTOMER:
  ID:    {customer.id if customer else 'unknown'}
  Name:  {customer.name if customer else 'unknown'}
  Email: {customer.email if customer else 'unknown'}
  Phone: {customer.phone if customer else 'unknown'}

Choose ONE action. Respond with ONLY the JSON object described in the system prompt."""

    raw_text, input_tokens, output_tokens = await _call_groq(system_prompt, user_message)
    await _update_usage(session, merchant.id, input_tokens=input_tokens, output_tokens=output_tokens)

    tool_name, tool_input, reasoning = _parse_tool_response(raw_text)
    logger.info(
        "Agent chose tool=%s for case=%s | reasoning=%.120s",
        tool_name, risk_case.id, reasoning,
    )

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
        await append_audit(
            session, merchant.id, actor="policy_engine",
            action=f"action.denied.{policy_result.action_status}",
            target_id=str(action.id),
            detail=policy_result.reason,
        )
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
