from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, text

from app.core.db import get_db
from app.models.agent_action import AgentAction

router = APIRouter(prefix="/actions", tags=["actions"])


class AgentActionOut(BaseModel):
    id: uuid.UUID
    risk_case_id: uuid.UUID
    tool_name: str
    input_json: dict | None
    reasoning_summary: str | None
    policy_check_result: str | None
    policy_check_reason: str | None
    output_json: dict | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("/cases/{case_id}/actions", response_model=list[AgentActionOut])
async def list_actions_for_case(
    merchant_id: uuid.UUID,
    case_id: uuid.UUID,
    limit: int = Query(default=50, le=200),
    session: AsyncSession = Depends(get_db),
):
    await session.execute(
        text(f"SET LOCAL app.current_merchant_id = '{merchant_id}'")
    )
    result = await session.execute(
        select(AgentAction)
        .where(
            AgentAction.risk_case_id == case_id,
            AgentAction.merchant_id == merchant_id,
        )
        .order_by(desc(AgentAction.created_at))
        .limit(limit)
    )
    return result.scalars().all()
