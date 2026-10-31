"""Fixtures isolated from the developer's persistent telemetry database."""

from datetime import UTC, datetime

import pytest

from robotelemetry.config import AlertThresholds
from robotelemetry.models import Scenario, TelemetrySample
from robotelemetry.service import TelemetryService
from robotelemetry.storage import SQLiteStore


@pytest.fixture
def sample_factory():
    def make(**overrides):
        values = {
            "run_id": "test-run",
            "sequence": 1,
            "seed": 42,
            "scenario": Scenario.NORMAL,
            "timestamp": datetime(2026, 1, 1, tzinfo=UTC),
            "battery_pct": 80.0,
            "temperature_c": 35.0,
            "speed_m_s": 0.5,
            "obstacle_distance_m": 3.0,
        }
        values.update(overrides)
        return TelemetrySample(**values)

    return make


@pytest.fixture
def store(tmp_path):
    database = SQLiteStore(tmp_path / "telemetry.sqlite3")
    database.initialize()
    return database


@pytest.fixture
def service(store):
    return TelemetryService(store, AlertThresholds())
