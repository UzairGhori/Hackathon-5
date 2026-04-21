"""Central API router — aggregates all sub-routers."""

from fastapi import APIRouter

from app.api.health import router as health_router
from app.api.channels import channels_router
from app.api.tickets import router as tickets_router
from app.api.metrics import router as metrics_router
from app.api.demo import router as demo_router

api_router = APIRouter()

# Health checks (no prefix — mounted at root)
api_router.include_router(health_router)

# Channel intake endpoints
api_router.include_router(channels_router)

# Ticket management endpoints (human agent dashboard)
api_router.include_router(tickets_router)

# Metrics and analytics dashboard
api_router.include_router(metrics_router)

# Demo endpoints for live demonstration
api_router.include_router(demo_router)
