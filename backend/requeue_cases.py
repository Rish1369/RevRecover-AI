"""Re-enqueue agent tasks for all diagnosed risk cases."""
import asyncio
from sqlalchemy import select, text
from app.core.db import AsyncSessionLocal
from app.workers.tasks import run_agent_for_case

async def requeue():
    async with AsyncSessionLocal() as s:
        r = await s.execute(
            text("SELECT id, merchant_id FROM risk_cases WHERE status = 'diagnosed'")
        )
        rows = r.fetchall()
        print(f"Found {len(rows)} diagnosed cases to re-queue")
        for row in rows:
            case_id = str(row[0])
            merchant_id = str(row[1])
            run_agent_for_case.delay(merchant_id, case_id)
            print(f"  Queued agent for case {case_id}")

asyncio.run(requeue())
