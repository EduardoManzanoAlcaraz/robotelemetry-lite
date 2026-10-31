"""Configuración explícita; las rutas relativas se anclan a la raíz del proyecto."""

import os
from pathlib import Path

from pydantic import Field, field_validator

from robotelemetry.models import ValidatedModel

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class AlertThresholds(ValidatedModel):
    battery_low_pct: float = Field(default=20, ge=0, le=100)
    temperature_high_c: float = Field(default=65, ge=-20, le=150)
    obstacle_near_m: float = Field(default=0.5, ge=0, le=20)


class Settings(ValidatedModel):
    db_path: Path = PROJECT_ROOT / "data" / "robotelemetry.sqlite3"
    thresholds: AlertThresholds = Field(default_factory=AlertThresholds)

    @field_validator("db_path")
    @classmethod
    def absolute_path(cls, value: Path) -> Path:
        return (PROJECT_ROOT / value).resolve() if not value.is_absolute() else value.resolve()


def get_settings() -> Settings:
    """Leer en cada arranque, sin caché global ni archivos .env implícitos."""
    thresholds = AlertThresholds(**{
        key: os.environ[env]
        for key, env in {
            "battery_low_pct": "ROBO_BATTERY_LOW_PCT",
            "temperature_high_c": "ROBO_TEMPERATURE_HIGH_C",
            "obstacle_near_m": "ROBO_OBSTACLE_NEAR_M",
        }.items()
        if env in os.environ
    })
    return Settings(db_path=os.environ.get("ROBO_DB_PATH", str(Settings().db_path)), thresholds=thresholds)
