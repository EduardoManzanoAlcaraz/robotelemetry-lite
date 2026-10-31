import pytest

from robotelemetry.alerts import evaluate_alerts
from robotelemetry.config import AlertThresholds
from robotelemetry.models import AlertKind


def test_normal_measurement_has_no_alerts(sample_factory):
    assert evaluate_alerts(sample_factory(), AlertThresholds()) == []


@pytest.mark.parametrize(
    ("overrides", "expected_kind", "expected_threshold"),
    [
        ({"battery_pct": 20}, AlertKind.LOW_BATTERY, 20),
        ({"temperature_c": 65}, AlertKind.HIGH_TEMPERATURE, 65),
        ({"obstacle_distance_m": 0.5}, AlertKind.NEAR_OBSTACLE, 0.5),
    ],
)
def test_thresholds_are_inclusive(
    sample_factory, overrides, expected_kind, expected_threshold
):
    sample = sample_factory(**overrides)
    alerts = evaluate_alerts(sample, AlertThresholds())
    assert len(alerts) == 1
    assert alerts[0].kind == expected_kind
    assert alerts[0].threshold == expected_threshold
    assert alerts[0].created_at == sample.timestamp
    assert alerts[0].message


def test_simultaneous_failures_emit_three_independent_alerts(sample_factory):
    sample = sample_factory(
        battery_pct=5, temperature_c=90, obstacle_distance_m=0.1
    )
    alerts = evaluate_alerts(sample, AlertThresholds())
    assert {alert.kind for alert in alerts} == set(AlertKind)
    assert len(alerts) == 3


def test_configured_thresholds_change_decisions(sample_factory):
    sample = sample_factory(
        battery_pct=30, temperature_c=50, obstacle_distance_m=0.8
    )
    assert evaluate_alerts(sample, AlertThresholds()) == []
    alerts = evaluate_alerts(
        sample,
        AlertThresholds(
            battery_low_pct=35, temperature_high_c=45, obstacle_near_m=1
        ),
    )
    assert {alert.kind for alert in alerts} == set(AlertKind)
