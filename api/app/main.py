"""FastAPI entrypoint: ``uvicorn app.main:app --app-dir api``."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.routers import calendar, export, globe, meta, points, stats
from app.settings import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="FireCal API",
        version=__version__,
        description="Harmonized MODIS-VIIRS fire activity calendar. Data: NASA FIRMS.",
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    @application.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    for module in (calendar, stats, points, export, globe, meta):
        application.include_router(module.router)
    return application


app = create_app()
