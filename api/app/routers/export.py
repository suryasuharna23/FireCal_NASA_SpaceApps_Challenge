from fastapi import APIRouter, HTTPException, status

router = APIRouter(tags=["export"])


@router.get("/export")
def get_export() -> None:
    """Streaming CSV export of monthly aggregates or raw points."""
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail="Planned in ticket T-18")
