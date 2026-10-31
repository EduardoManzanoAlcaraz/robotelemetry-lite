"""Contratos compartidos y validación de datos en los límites del sistema."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Scenario(StrEnum):
    NORMAL = "normal"
    LOW_BATTERY = "low_battery"
    OVERHEATING = "overheating"
    OBSTACLE = "obstacle"
    DEMO = "demo"


class AlertKind(StrEnum):
    LOW_BATTERY = "low_battery"
    HIGH_TEMPERATURE = "high_temperature"
    NEAR_OBSTACLE = "near_obstacle"


class ValidatedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


def aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("La fecha debe incluir zona horaria.")
    return value.astimezone(UTC)


class TelemetrySample(ValidatedModel):
    run_id: str = Field(min_length=1, max_length=64)
    sequence: int = Field(ge=1, le=2**63 - 1)
    seed: int = Field(ge=-(2**63), le=2**63 - 1)
    scenario: Scenario
    timestamp: datetime
    battery_pct: float = Field(ge=0, le=100)
    temperature_c: float = Field(ge=-20, le=150)
    speed_m_s: float = Field(ge=0, le=3)
    obstacle_distance_m: float = Field(ge=0, le=20)

    @field_validator("timestamp")
    @classmethod
    def timestamp_is_aware(cls, value: datetime) -> datetime:
        return aware_utc(value)


class TelemetryRecord(TelemetrySample):
    id: int = Field(ge=1)


class AlertDraft(ValidatedModel):
    kind: AlertKind
    severity: Literal["warning", "critical"]
    message: str = Field(min_length=1)
    value: float
    threshold: float
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def timestamp_is_aware(cls, value: datetime) -> datetime:
        return aware_utc(value)


class AlertRecord(AlertDraft):
    id: int = Field(ge=1)
    measurement_id: int = Field(ge=1)
