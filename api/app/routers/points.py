from fastapi import APIRouter, HTTPException, status

router = APIRouter(tags=["points"])


@router.get("/points")
def get_points() -> None:
    """Raw hotspot points for an AOI and month as GeoJSON."""
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail="Planned in ticket T-17")
