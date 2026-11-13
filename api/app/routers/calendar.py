from fastapi import APIRouter, HTTPException, status

router = APIRouter(tags=["calendar"])


@router.get("/calendar")
def get_calendar() -> None:
    """Year x month matrix of harmonized hotspot counts for an AOI."""
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail="Planned in ticket T-15")
