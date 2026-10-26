"""GET verify + POST webhook for WhatsApp. Implemented in build step 7."""

from fastapi import APIRouter

router = APIRouter(prefix="/webhook", tags=["whatsapp"])
