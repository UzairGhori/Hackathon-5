"""Aggregates all channel intake routers under /api/v1/channels."""

from fastapi import APIRouter

from app.api.channels.web import router as web_router
from app.api.channels.gmail import router as gmail_router
from app.api.channels.whatsapp import router as whatsapp_router
from app.api.channels.twilio_whatsapp import router as twilio_whatsapp_router

router = APIRouter(prefix="/api/v1/channels", tags=["channels"])

router.include_router(web_router)
router.include_router(gmail_router)
router.include_router(whatsapp_router)
router.include_router(twilio_whatsapp_router)
