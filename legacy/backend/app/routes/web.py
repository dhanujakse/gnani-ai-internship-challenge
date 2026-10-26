"""/v1/session and /v1/process for the share-target web app. Implemented in build step 9."""

from fastapi import APIRouter

router = APIRouter(prefix="/v1", tags=["web"])
