"""Reglas puras: una ocurrencia por regla incumplida y por medición."""

from robotelemetry.config import AlertThresholds
from robotelemetry.models import AlertDraft, AlertKind, TelemetrySample


def evaluate_alerts(sample: TelemetrySample, thresholds: AlertThresholds) -> list[AlertDraft]:
    rules = [
        (sample.battery_pct <= thresholds.battery_low_pct, AlertKind.LOW_BATTERY,
         "warning", "Batería baja", sample.battery_pct, thresholds.battery_low_pct),
        (sample.temperature_c >= thresholds.temperature_high_c, AlertKind.HIGH_TEMPERATURE,
         "critical", "Temperatura elevada", sample.temperature_c, thresholds.temperature_high_c),
        (sample.obstacle_distance_m <= thresholds.obstacle_near_m, AlertKind.NEAR_OBSTACLE,
         "critical", "Obstáculo próximo", sample.obstacle_distance_m, thresholds.obstacle_near_m),
    ]
    return [
        AlertDraft(kind=kind, severity=severity, message=message, value=value,
                   threshold=threshold, created_at=sample.timestamp)
        for triggered, kind, severity, message, value, threshold in rules if triggered
    ]
