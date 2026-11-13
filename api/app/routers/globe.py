from fastapi import APIRouter, HTTPException, status

router = APIRouter(tags=["globe"])


@router.get("/globe")
def get_globe() -> None:
    """Harmonized global grid cells for one month (globe view)."""
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail="Planned in ticket T-42")
