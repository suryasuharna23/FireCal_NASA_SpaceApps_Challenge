"""FastAPI entrypoint: ``uvicorn app.main:app --app-dir api``."""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.aoi import AoiError
from app.db import DataUnavailableError
from app.routers import calendar, export, globe, meta, points, regions, stats
from app.series import RangeError
from app.settings import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="FireCal API",
        version=__version__,
        description="Harmonized MODIS-VIIRS fire activity calendar. Data: NASA FIRMS.",
    )
    application.add_middleware(GZipMiddleware, minimum_size=1024)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition", "X-Row-Count"],
    )

    @application.exception_handler(AoiError)
    @application.exception_handler(RangeError)
    async def unprocessable(_: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @application.exception_handler(DataUnavailableError)
    async def unavailable(_: Request, exc: DataUnavailableError) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @application.middleware("http")
    async def cache_headers(request: Request, call_next):
        """Let browsers and CDNs cache read-only GET responses (T-37).

        Globe months and region boundaries only change with a new data version, so they
        can be cached for an hour; /meta is short-lived so NRT status stays fresh.
        """
        response = await call_next(request)
        if request.method == "GET" and response.status_code == 200:
            path = request.url.path
            if path.startswith(("/globe", "/regions")):
                response.headers.setdefault("Cache-Control", "public, max-age=3600")
            elif path == "/meta":
                response.headers.setdefault("Cache-Control", "public, max-age=60")
        return response

    @application.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    for module in (calendar, stats, points, export, globe, regions, meta):
        application.include_router(module.router)
    return application


app = create_app()
