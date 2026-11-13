from fastapi import APIRouter

from app import __version__

router = APIRouter(tags=["meta"])


@router.get("/meta")
def get_meta() -> dict[str, object]:
    """Data version, last update and NRT status (FR-D-07, FR-W-22).

    Real values are wired in T-19; until then the response reports no data.
    """
    return {
        "api_version": __version__,
        "data_version": None,
        "last_updated": None,
        "nrt_provisional": None,
        "attribution": "NASA FIRMS (https://firms.modaps.eosdis.nasa.gov)",
    }
