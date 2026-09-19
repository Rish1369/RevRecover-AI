"""
Celery task definitions.

Tasks use asyncio.run() to bridge sync Celery into async SQLAlchemy sessions.
"""

from __future__ import annotations

import asyncio
import logging
import uuid

from app.workers.celery_app import celery_app
from app.core.db import get_db_session

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def run_agent_for_case(self, merchant_id: str, risk_case_id: str):
    """
    Run the agent loop for a single risk case.
    Enqueued by the webhook handler after a case is diagnosed.
    """
    async def _run():
        from sqlalchemy import select
        from app.models.merchant import Merchant
        from app.models.risk_case import RiskCase
        from app.models.customer import Customer
        from app.services.agent import run_agent

        mid = uuid.UUID(merchant_id)
        cid = uuid.UUID(risk_case_id)

        async with get_db_session(merchant_id=mid) as session:
            merchant_result = await session.execute(
                select(Merchant).where(Merchant.id == mid)
            )
            merchant = merchant_result.scalar_one_or_none()
            if not merchant:
                logger.error("Merchant %s not found", mid)
                return

            case_result = await session.execute(
                select(RiskCase).where(RiskCase.id == cid)
            )
            risk_case = case_result.scalar_one_or_none()
            if not risk_case:
                logger.error("RiskCase %s not found", cid)
                return

            customer = None
            if risk_case.customer_id:
                cust_result = await session.execute(
                    select(Customer).where(Customer.id == risk_case.customer_id)
                )
                customer = cust_result.scalar_one_or_none()

            action = await run_agent(session, merchant, risk_case, customer)
            logger.info(
                "Agent task complete | case=%s | action=%s | status=%s",
                cid, action.id, action.status,
            )

    try:
        asyncio.run(_run())
    except Exception as exc:
        logger.error("Agent task failed for case %s: %s", risk_case_id, exc)
        raise self.retry(exc=exc)


@celery_app.task
def run_attribution_scan_all_merchants():
    """
    Periodic beat task: run attribution scan for every merchant with
    risk cases in 'monitoring' status.
    """
    async def _run():
        from sqlalchemy import select
        from app.models.merchant import Merchant
        from app.models.risk_case import RiskCase
        from app.core.db import AsyncSessionLocal
        from app.services.measurement import run_attribution_scan

        # Get distinct merchant IDs that have monitoring cases
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(RiskCase.merchant_id)
                .where(RiskCase.status == "monitoring")
                .distinct()
            )
            merchant_ids = [row[0] for row in result.fetchall()]

        total = {"scanned": 0, "recovered": 0, "closed_unrecovered": 0}
        for mid in merchant_ids:
            async with get_db_session(merchant_id=mid) as session:
                from sqlalchemy import select as sel
                merchant_result = await session.execute(
                    sel(Merchant).where(Merchant.id == mid)
                )
                merchant = merchant_result.scalar_one_or_none()
                if not merchant:
                    continue
                summary = await run_attribution_scan(session, merchant)
                for k in total:
                    total[k] += summary.get(k, 0)

        logger.info("Attribution scan complete: %s", total)
        return total

    return asyncio.run(_run())
