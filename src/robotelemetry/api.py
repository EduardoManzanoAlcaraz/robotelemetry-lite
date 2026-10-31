"""API REST de consulta; nunca inicia simulación ni elimina datos."""

from contextlib import asynccontextmanager
from datetime import UTC, datetime
import logging
import sqlite3
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import AfterValidator, AwareDatetime

from robotelemetry import __version__
from robotelemetry.config import AlertThresholds, Settings, get_settings
from robotelemetry.models import AlertKind, AlertRecord, TelemetryRecord
from robotelemetry.storage import MAX_SQLITE_OFFSET, SQLiteStore

logger = logging.getLogger(__name__)
Limit = Annotated[int, Query(ge=1, le=1000)]
Offset = Annotated[int, Query(ge=0, le=MAX_SQLITE_OFFSET)]


def _filter_utc(value: datetime) -> datetime:
    """Reject offsets that would move an otherwise valid date outside datetime's range."""
    try:
        return value.astimezone(UTC)
    except (OverflowError, ValueError) as exc:
        raise ValueError("La fecha debe poder representarse en UTC entre los años 1 y 9999.") from exc


UTCFilter = Annotated[AwareDatetime, AfterValidator(_filter_utc)]


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings if settings is not None else get_settings()
    store = SQLiteStore(settings.db_path)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        store.initialize()
        yield

    application = FastAPI(
        title="RoboTelemetry Lite", version=__version__,
        description="Telemetría de sensores SIMULADOS. API local de solo lectura.",
        lifespan=lifespan,
    )
    application.state.store = store

    @application.exception_handler(sqlite3.Error)
    async def storage_unavailable(request: Request, exc: sqlite3.Error):
        logger.error("Error SQLite en %s", request.url.path, exc_info=exc)
        return JSONResponse(status_code=503, content={"detail": "Almacenamiento temporalmente no disponible."})

    @application.get("/health", tags=["Sistema"])
    def health() -> dict[str, str | int]:
        return {"status": "ok", **store.counts()}

    @application.get("/config", response_model=AlertThresholds, tags=["Sistema"])
    def config() -> AlertThresholds:
        return settings.thresholds

    @application.get("/telemetry/latest", response_model=TelemetryRecord, tags=["Telemetría"],
                     responses={404: {"description": "Todavía no hay lecturas"},
                                503: {"description": "Almacenamiento no disponible"}})
    def latest() -> TelemetryRecord:
        sample = store.latest()
        if sample is None:
            raise HTTPException(status_code=404, detail="Todavía no hay lecturas. Inicia el simulador.")
        return sample

    @application.get("/telemetry/history", response_model=list[TelemetryRecord], tags=["Telemetría"])
    def history(limit: Limit = 100, offset: Offset = 0,
                since: UTCFilter | None = None, until: UTCFilter | None = None) -> list[TelemetryRecord]:
        if since is not None and until is not None and since > until:
            raise HTTPException(status_code=422, detail="since debe ser anterior o igual a until.")
        return store.history(limit=limit, offset=offset, since=since, until=until)

    @application.get("/alerts", response_model=list[AlertRecord], tags=["Alertas"])
    def alerts(limit: Limit = 100, offset: Offset = 0, kind: AlertKind | None = None) -> list[AlertRecord]:
        return store.alerts(limit=limit, offset=offset, kind=kind)

    return application


app = create_app()
