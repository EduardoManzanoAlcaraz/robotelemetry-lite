from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("battery_pct", -0.1),
        ("battery_pct", 100.1),
        ("temperature_c", -20.1),
        ("temperature_c", 150.1),
        ("speed_m_s", -0.01),
        ("speed_m_s", 3.01),
        ("obstacle_distance_m", -0.01),
        ("obstacle_distance_m", 20.01),
        ("battery_pct", float("nan")),
        ("temperature_c", float("inf")),
        ("speed_m_s", float("-inf")),
        ("obstacle_distance_m", float("nan")),
        ("sequence", 0),
        ("seed", 2**63),
        ("seed", -(2**63) - 1),
        ("run_id", ""),
        ("scenario", "made_up"),
    ],
)
def test_invalid_measurements_are_rejected(sample_factory, field, value):
    with pytest.raises(ValidationError):
        sample_factory(**{field: value})


def test_unknown_fields_are_rejected(sample_factory):
    with pytest.raises(ValidationError):
        sample_factory(unknown_sensor=123)


def test_naive_timestamp_is_rejected(sample_factory):
    with pytest.raises(ValidationError):
        sample_factory(timestamp=datetime(2026, 1, 1))


def test_aware_timestamp_is_normalized_to_utc(sample_factory):
    sample = sample_factory(
        timestamp=datetime(2026, 1, 1, 12, tzinfo=timezone(timedelta(hours=2)))
    )
    assert sample.timestamp == datetime(2026, 1, 1, 10, tzinfo=UTC)
    assert sample.timestamp.utcoffset() == timedelta(0)


def test_samples_are_immutable(sample_factory):
    sample = sample_factory()
    with pytest.raises(ValidationError):
        sample.battery_pct = 40


def test_physical_range_boundaries_are_valid(sample_factory):
    sample = sample_factory(
        battery_pct=0, temperature_c=-20, speed_m_s=0, obstacle_distance_m=0
    )
    assert sample.battery_pct == 0
    assert sample_factory(
        battery_pct=100, temperature_c=150, speed_m_s=3, obstacle_distance_m=20
    ).speed_m_s == 3


@pytest.mark.parametrize("seed", [-(2**63), 2**63 - 1])
def test_seed_accepts_sqlite_integer_boundaries(sample_factory, seed):
    assert sample_factory(seed=seed).seed == seed
