from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from app.core.db import get_db
from app.models.policy import Policy

router = APIRouter(prefix="/policies", tags=["policies"])


class PolicyOut(BaseModel):
    id: uuid.UUID
    key: str
    value: dict
    updated_at: datetime

    model_config = {"from_attributes": True}


class PolicyUpsert(BaseModel):
    value: dict


@router.get("", response_model=list[PolicyOut])
async def list_policies(
    merchant_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
):
    await session.execute(
        text("SET LOCAL app.current_merchant_id = :mid"), {"mid": str(merchant_id)}
    )
    result = await session.execute(
        select(Policy).where(Policy.merchant_id == merchant_id).order_by(Policy.key)
    )
    return result.scalars().all()


@router.put("/{key}", response_model=PolicyOut)
async def upsert_policy(
    merchant_id: uuid.UUID,
    key: str,
    body: PolicyUpsert,
    session: AsyncSession = Depends(get_db),
):
    """Create or update a policy value for the merchant."""
    await session.execute(
        text("SET LOCAL app.current_merchant_id = :mid"), {"mid": str(merchant_id)}
    )
    result = await session.execute(
        select(Policy).where(Policy.merchant_id == merchant_id, Policy.key == key)
    )
    policy = result.scalar_one_or_none()
    if policy:
        policy.value = body.value
        policy.updated_at = datetime.now(timezone.utc)
    else:
        policy = Policy(
            merchant_id=merchant_id,
            key=key,
            value=body.value,
        )
        session.add(policy)

    from app.services.audit import append_audit
    await append_audit(
        session, merchant_id, actor="human",
        action=f"policy.updated.{key}",
        detail=str(body.value)[:200],
    )
    await session.commit()
    await session.refresh(policy)
    return policy
