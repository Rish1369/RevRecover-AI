from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, text

from app.core.db import get_db
from app.models.audit_log import AuditLog

router = APIRouter(prefix="/audit", tags=["audit"])


class AuditLogOut(BaseModel):
    id: uuid.UUID
    actor: str
    action: str
    target_id: str | None
    detail: str | None
    hash: str
    prev_hash: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("", response_model=list[AuditLogOut])
async def list_audit_log(
    merchant_id: uuid.UUID,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0),
    session: AsyncSession = Depends(get_db),
):
    await session.execute(
        text("SET LOCAL app.current_merchant_id = :mid"), {"mid": str(merchant_id)}
    )
    result = await session.execute(
        select(AuditLog)
        .where(AuditLog.merchant_id == merchant_id)
        .order_by(desc(AuditLog.created_at))
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()


@router.get("/verify-chain")
async def verify_audit_chain(
    merchant_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
):
    """Verify the integrity of the audit log hash chain."""
    from app.services.audit import verify_chain
    await session.execute(
        text("SET LOCAL app.current_merchant_id = :mid"), {"mid": str(merchant_id)}
    )
    ok, message = await verify_chain(session, merchant_id)
    return {"chain_valid": ok, "message": message}
