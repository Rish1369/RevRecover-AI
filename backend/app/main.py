"""
Revenue Recovery Agent — FastAPI application entry point.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.settings import get_settings
from app.core.db import engine, Base
from app.api import webhooks, cases, actions, policies, metrics, audit

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Tables are managed by Alembic in production.
    # In development/test we can create them here for convenience.
    yield


app = FastAPI(
    title="Revenue Recovery Agent API",
    description="Multi-tenant AI-powered revenue recovery system",
    version="0.1.0",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(webhooks.router)
app.include_router(cases.router)
app.include_router(actions.router)
app.include_router(policies.router)
app.include_router(metrics.router)
app.include_router(audit.router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "revenue-recovery-agent"}
