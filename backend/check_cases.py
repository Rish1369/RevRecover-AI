import asyncio
from sqlalchemy import select, text
from app.core.db import AsyncSessionLocal

async def check():
    async with AsyncSessionLocal() as s:
        r = await s.execute(text("SELECT id, status, source_id, diagnosis_code FROM risk_cases ORDER BY created_at DESC LIMIT 10"))
        rows = r.fetchall()
        for row in rows:
            print(f"{row[0]} | status={row[1]} | source={row[2]} | diag={row[3]}")

asyncio.run(check())
