from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func

from app.core.db import get_db
from app.models.risk_case import RiskCase
from app.models.customer import Customer

router = APIRouter(prefix="/cases", tags=["cases"])


class RiskCaseOut(BaseModel):
    id: uuid.UUID
    merchant_id: uuid.UUID
    customer_id: uuid.UUID | None
    customer_name: str | None
    customer_email: str | None
    source_type: str
    source_id: str | None
    diagnosis_code: str | None
    diagnosis_confidence: float | None
    risk_score: float | None
    status: str
    attempts_count: int
    created_at: datetime
    resolved_at: datetime | None

    model_config = {"from_attributes": True}


@router.get("", response_model=list[RiskCaseOut])
async def list_cases(
    merchant_id: uuid.UUID,
    status: str | None = Query(default=None),
    source_type: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0),
    session: AsyncSession = Depends(get_db),
):
    """List risk cases for a merchant, with optional status/source_type filter."""
    from sqlalchemy import text
    await session.execute(
        text("SET LOCAL app.current_merchant_id = :mid"), {"mid": str(merchant_id)}
    )

    q = (
        select(RiskCase, Customer)
        .outerjoin(Customer, RiskCase.customer_id == Customer.id)
        .where(RiskCase.merchant_id == merchant_id)
        .order_by(desc(RiskCase.created_at))
        .limit(limit)
        .offset(offset)
    )
    if status:
        q = q.where(RiskCase.status == status)
    if source_type:
        q = q.where(RiskCase.source_type == source_type)

    result = await session.execute(q)
    rows = result.all()

    out = []
    for case, customer in rows:
        out.append(RiskCaseOut(
            id=case.id,
            merchant_id=case.merchant_id,
            customer_id=case.customer_id,
            customer_name=customer.name if customer else None,
            customer_email=customer.email if customer else None,
            source_type=case.source_type,
            source_id=case.source_id,
            diagnosis_code=case.diagnosis_code,
            diagnosis_confidence=case.diagnosis_confidence,
            risk_score=case.risk_score,
            status=case.status,
            attempts_count=case.attempts_count,
            created_at=case.created_at,
            resolved_at=case.resolved_at,
        ))
    return out


@router.get("/{case_id}", response_model=RiskCaseOut)
async def get_case(
    merchant_id: uuid.UUID,
    case_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
):
    from sqlalchemy import text
    await session.execute(
        text("SET LOCAL app.current_merchant_id = :mid"), {"mid": str(merchant_id)}
    )
    result = await session.execute(
        select(RiskCase, Customer)
        .outerjoin(Customer, RiskCase.customer_id == Customer.id)
        .where(RiskCase.id == case_id, RiskCase.merchant_id == merchant_id)
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Case not found")
    case, customer = row
    return RiskCaseOut(
        id=case.id,
        merchant_id=case.merchant_id,
        customer_id=case.customer_id,
        customer_name=customer.name if customer else None,
        customer_email=customer.email if customer else None,
        source_type=case.source_type,
        source_id=case.source_id,
        diagnosis_code=case.diagnosis_code,
        diagnosis_confidence=case.diagnosis_confidence,
        risk_score=case.risk_score,
        status=case.status,
        attempts_count=case.attempts_count,
        created_at=case.created_at,
        resolved_at=case.resolved_at,
    )


@router.post("/{case_id}/escalate", status_code=200)
async def escalate_case(
    merchant_id: uuid.UUID,
    case_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
):
    """Manually escalate a case to human review."""
    from sqlalchemy import text
    from app.services.audit import append_audit

    await session.execute(
        text("SET LOCAL app.current_merchant_id = :mid"), {"mid": str(merchant_id)}
    )
    result = await session.execute(
        select(RiskCase).where(RiskCase.id == case_id, RiskCase.merchant_id == merchant_id)
    )
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    case.status = "escalated"
    case.resolved_at = datetime.now(timezone.utc)
    await append_audit(
        session, merchant_id, actor="human",
        action="case.manually_escalated", target_id=str(case_id),
    )
    await session.commit()
    return {"status": "escalated", "case_id": str(case_id)}
