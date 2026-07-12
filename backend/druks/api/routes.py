from fastapi import APIRouter, Response

from druks.api import schemas as api_schemas
from druks.api.health_status import build_health

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get(
    "/api/system/health",
    response_model=api_schemas.DashboardHealth,
    response_model_by_alias=True,
)
async def system_health(response: Response) -> api_schemas.DashboardHealth:
    """Webhook freshness / spend for the persistent status strip.

    The strip rides above every tab and only needs this block, so it polls
    here rather than the full research dashboard.
    """
    response.headers["Cache-Control"] = "no-store"
    return await build_health()
