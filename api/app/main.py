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

    @application.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    for module in (calendar, stats, points, export, globe, regions, meta):
        application.include_router(module.router)
    return application


app = create_app()
