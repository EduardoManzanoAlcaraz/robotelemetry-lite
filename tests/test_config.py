from pathlib import Path

import pytest
from pydantic import ValidationError

from robotelemetry.config import AlertThresholds, PROJECT_ROOT, Settings, get_settings


@pytest.fixture
def clean_environment(monkeypatch):
    for name in (
        "ROBO_DB_PATH", "ROBO_BATTERY_LOW_PCT", "ROBO_TEMPERATURE_HIGH_C",
        "ROBO_OBSTACLE_NEAR_M",
    ):
        monkeypatch.delenv(name, raising=False)


def test_default_database_path_is_independent_of_working_directory(
    monkeypatch, tmp_path, clean_environment
):
    first = get_settings().db_path
    monkeypatch.chdir(tmp_path)
    assert get_settings().db_path == first
    assert first == PROJECT_ROOT / "data" / "robotelemetry.sqlite3"
    assert first.is_absolute()


def test_relative_database_path_is_anchored_to_project_root():
    assert Settings(db_path=Path("custom/test.sqlite3")).db_path == (
        PROJECT_ROOT / "custom" / "test.sqlite3"
    )


def test_environment_settings_are_read_and_not_cached(monkeypatch, tmp_path, clean_environment):
    monkeypatch.setenv("ROBO_DB_PATH", str(tmp_path / "custom.sqlite3"))
    monkeypatch.setenv("ROBO_BATTERY_LOW_PCT", "30")
    monkeypatch.setenv("ROBO_TEMPERATURE_HIGH_C", "70")
    monkeypatch.setenv("ROBO_OBSTACLE_NEAR_M", "0.75")
    settings = get_settings()
    assert settings.db_path == tmp_path / "custom.sqlite3"
    assert settings.thresholds == AlertThresholds(
        battery_low_pct=30, temperature_high_c=70, obstacle_near_m=0.75
    )
    monkeypatch.setenv("ROBO_BATTERY_LOW_PCT", "25")
    assert get_settings().thresholds.battery_low_pct == 25


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("battery_low_pct", -1),
        ("battery_low_pct", 101),
        ("temperature_high_c", -21),
        ("temperature_high_c", 151),
        ("obstacle_near_m", -1),
        ("obstacle_near_m", 21),
        ("battery_low_pct", float("nan")),
        ("temperature_high_c", float("inf")),
        ("obstacle_near_m", float("nan")),
    ],
)
def test_invalid_alert_configuration_is_rejected(field, value):
    with pytest.raises(ValidationError):
        AlertThresholds(**{field: value})


def test_invalid_environment_threshold_fails_visibly(monkeypatch, clean_environment):
    monkeypatch.setenv("ROBO_BATTERY_LOW_PCT", "not-a-number")
    with pytest.raises((ValidationError, ValueError)):
        get_settings()
