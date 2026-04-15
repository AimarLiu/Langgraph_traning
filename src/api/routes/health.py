from __future__ import annotations

from fastapi import APIRouter

from api.schemas import HealthResponse
from api.settings import get_settings

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    # L3：用 pydantic-settings 讀 `.env`；**勿** log 整份 settings 或任何 SecretStr 內容。
    settings = get_settings()
    google_ok = settings.google_api_key_configured()
    return HealthResponse(
        status="ok" if google_ok else "degraded",
        google_api_key_configured=google_ok,
        langsmith_tracing=settings.langsmith_tracing,
        langsmith_api_key_configured=settings.langsmith_api_key_configured(),
        langsmith_project=settings.langsmith_project,
        checkpoint_db=settings.checkpoint_db,
    )

