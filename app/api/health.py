"""Health and readiness endpoints for k8s probes."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session

router = APIRouter(tags=["health"])


@router.get("/health/live")
async def liveness() -> dict:
    """Liveness probe — app process is running."""
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness(session: AsyncSession = Depends(get_session)) -> dict:
    """Readiness probe — app can serve traffic (DB is reachable)."""
    result = await session.execute(text("SELECT 1"))
    result.scalar_one()
    return {"status": "ready", "database": "connected"}
