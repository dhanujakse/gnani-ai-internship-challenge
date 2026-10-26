"""Liveness endpoint. Upstream checks (Prisma, Timbre, Evon /v1/models, SQLite) come in later steps."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
