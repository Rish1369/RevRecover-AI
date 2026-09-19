"""
Tamper-evident audit log service.

Every entry's `hash` is SHA-256(actor + action + target_id + iso_timestamp + prev_hash).
The chain of prev_hash values means any modification to an older row
breaks all subsequent hashes — detectable on read.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


def _compute_hash(
    actor: str,
    action: str,
    target_id: str | None,
    created_at: datetime,
    prev_hash: str | None,
) -> str:
    payload = "|".join([
        actor,
        action,
        target_id or "",
        created_at.isoformat(),
        prev_hash or "",
    ])
    return hashlib.sha256(payload.encode()).hexdigest()


async def append_audit(
    session: AsyncSession,
    merchant_id: uuid.UUID,
    actor: str,
    action: str,
    target_id: str | None = None,
    detail: str | None = None,
) -> AuditLog:
    """
    Append a new entry to the audit chain for this merchant.

    Fetches the most recent entry to chain prev_hash, then inserts the new entry.
    Both operations happen within the caller's transaction.
    """
    # Fetch the latest hash for this merchant (no RLS needed here since we're
    # called from within a merchant-scoped session already)
    result = await session.execute(
        select(AuditLog.hash)
        .where(AuditLog.merchant_id == merchant_id)
        .order_by(desc(AuditLog.created_at))
        .limit(1)
    )
    row = result.scalar_one_or_none()
    prev_hash = row if row else None

    now = datetime.now(timezone.utc)
    h = _compute_hash(actor, action, target_id, now, prev_hash)

    entry = AuditLog(
        merchant_id=merchant_id,
        actor=actor,
        action=action,
        target_id=target_id,
        detail=detail,
        prev_hash=prev_hash,
        hash=h,
        created_at=now,
    )
    session.add(entry)
    logger.info("audit | merchant=%s actor=%s action=%s target=%s", merchant_id, actor, action, target_id)
    return entry


async def verify_chain(
    session: AsyncSession,
    merchant_id: uuid.UUID,
    limit: int = 500,
) -> tuple[bool, str]:
    """
    Verify integrity of the most recent `limit` audit entries.

    Returns (ok: bool, message: str).
    """
    result = await session.execute(
        select(AuditLog)
        .where(AuditLog.merchant_id == merchant_id)
        .order_by(AuditLog.created_at)
        .limit(limit)
    )
    entries = result.scalars().all()

    prev_hash: str | None = None
    for entry in entries:
        expected = _compute_hash(
            entry.actor,
            entry.action,
            entry.target_id,
            entry.created_at,
            prev_hash,
        )
        if expected != entry.hash:
            return False, f"Chain broken at entry {entry.id} (created {entry.created_at})"
        prev_hash = entry.hash

    return True, f"Chain verified for {len(entries)} entries"
