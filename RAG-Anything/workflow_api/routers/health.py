"""健康检查。"""

from __future__ import annotations

from fastapi import APIRouter

from .. import __version__
from ..schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """服务存活探针。"""
    return HealthResponse(
        status="ok",
        service="backend_api",
        version=__version__,
    )
