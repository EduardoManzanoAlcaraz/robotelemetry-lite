"""Caso de uso de ingesta: calcular alertas y guardar todo en una transacción."""

from robotelemetry.alerts import evaluate_alerts
from robotelemetry.config import AlertThresholds
from robotelemetry.models import TelemetryRecord, TelemetrySample
from robotelemetry.storage import SQLiteStore


class TelemetryService:
    def __init__(self, store: SQLiteStore, thresholds: AlertThresholds):
        self.store = store
        self.thresholds = thresholds

    def record(self, sample: TelemetrySample) -> TelemetryRecord:
        return self.store.record(sample, evaluate_alerts(sample, self.thresholds))
