from fastapi import APIRouter, HTTPException, status

router = APIRouter(tags=["stats"])


@router.get("/stats")
def get_stats() -> None:
    """Climatology, anomaly, summary and critical periods for an AOI."""
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail="Planned in ticket T-16")
