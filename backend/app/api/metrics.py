from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text

from app.core.db import get_db
from app.models.risk_case import RiskCase
from app.models.recovery_ledger import RecoveryLedger
from app.models.agent_action import AgentAction

router = APIRouter(prefix="/metrics", tags=["metrics"])


class RecoveryMetrics(BaseModel):
    total_cases: int
    recovered_cases: int
    escalated_cases: int
    closed_unrecovered_cases: int
    monitoring_cases: int
    recovery_rate_pct: float
    total_at_risk_paise: int
    total_recovered_paise: int
    avg_recovery_days: float | None
    # Breakdown by diagnosis code
    by_diagnosis: list[dict]
    # Breakdown by intervention type
    by_tool: list[dict]


@router.get("/recovery", response_model=RecoveryMetrics)
async def get_recovery_metrics(
    merchant_id: uuid.UUID,
    days: int = Query(default=30, description="Lookback window in days"),
    session: AsyncSession = Depends(get_db),
):
    await session.execute(
        text("SET LOCAL app.current_merchant_id = :mid"), {"mid": str(merchant_id)}
    )
    since = datetime.now(timezone.utc) - timedelta(days=days)

    # Case counts by status
    result = await session.execute(
        select(RiskCase.status, func.count(RiskCase.id).label("cnt"))
        .where(RiskCase.merchant_id == merchant_id, RiskCase.created_at >= since)
        .group_by(RiskCase.status)
    )
    status_counts = {row.status: row.cnt for row in result.all()}

    total = sum(status_counts.values())
    recovered = status_counts.get("recovered", 0)
    recovery_rate = round((recovered / total * 100) if total else 0.0, 1)

    # Total recovered amount
    ledger_result = await session.execute(
        select(func.sum(RecoveryLedger.amount_recovered))
        .where(
            RecoveryLedger.merchant_id == merchant_id,
            RecoveryLedger.attributed_at >= since,
        )
    )
    total_recovered = ledger_result.scalar_one() or 0

    # Average time-to-recovery (days)
    avg_days_result = await session.execute(
        select(
            func.avg(
                func.extract(
                    "epoch",
                    RiskCase.resolved_at - RiskCase.created_at,
                )
            )
        )
        .where(
            RiskCase.merchant_id == merchant_id,
            RiskCase.status == "recovered",
            RiskCase.created_at >= since,
        )
    )
    avg_seconds = avg_days_result.scalar_one()
    avg_days = round(avg_seconds / 86400, 1) if avg_seconds else None

    # Breakdown by diagnosis code
    diag_result = await session.execute(
        select(
            RiskCase.diagnosis_code,
            func.count(RiskCase.id).label("total"),
            func.sum(
                (RiskCase.status == "recovered").cast(
                    __import__("sqlalchemy").Integer
                )
            ).label("recovered"),
        )
        .where(RiskCase.merchant_id == merchant_id, RiskCase.created_at >= since)
        .group_by(RiskCase.diagnosis_code)
        .order_by(func.count(RiskCase.id).desc())
    )
    by_diagnosis = [
        {
            "diagnosis_code": row.diagnosis_code or "unknown",
            "total": row.total,
            "recovered": row.recovered or 0,
            "recovery_rate_pct": round(
                ((row.recovered or 0) / row.total * 100) if row.total else 0, 1
            ),
        }
        for row in diag_result.all()
    ]

    # Breakdown by tool
    tool_result = await session.execute(
        select(AgentAction.tool_name, func.count(AgentAction.id).label("cnt"))
        .where(
            AgentAction.merchant_id == merchant_id,
            AgentAction.status == "executed",
            AgentAction.created_at >= since,
        )
        .group_by(AgentAction.tool_name)
        .order_by(func.count(AgentAction.id).desc())
    )
    by_tool = [{"tool": row.tool_name, "count": row.cnt} for row in tool_result.all()]

    return RecoveryMetrics(
        total_cases=total,
        recovered_cases=recovered,
        escalated_cases=status_counts.get("escalated", 0),
        closed_unrecovered_cases=status_counts.get("closed_unrecovered", 0),
        monitoring_cases=status_counts.get("monitoring", 0),
        recovery_rate_pct=recovery_rate,
        total_at_risk_paise=0,  # would require summing payment amounts across linked events
        total_recovered_paise=total_recovered,
        avg_recovery_days=avg_days,
        by_diagnosis=by_diagnosis,
        by_tool=by_tool,
    )
