from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import text

from resolveai.schemas import HealthResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", response_model=HealthResponse)
def live() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/ready", response_model=HealthResponse)
def ready(request: Request) -> HealthResponse:
    try:
        with request.app.state.session_factory() as session:
            session.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="database unavailable",
        ) from exc
    return HealthResponse(status="ready")
