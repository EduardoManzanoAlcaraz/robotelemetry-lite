"""Simulador determinista; el reloj y la persistencia viven fuera de step()."""

import argparse
from datetime import UTC, datetime, timedelta
import logging
import math
import random
import sqlite3
import time
from uuid import uuid4

from pydantic import ValidationError

from robotelemetry.config import AlertThresholds, get_settings
from robotelemetry.models import Scenario, TelemetrySample
from robotelemetry.service import TelemetryService
from robotelemetry.storage import SQLiteStore

logger = logging.getLogger(__name__)


class RobotSimulator:
    """Modelo didáctico de pasos de un segundo, sin pretensión de física real."""

    def __init__(self, seed: int = 42, scenario: Scenario | str = Scenario.NORMAL,
                 start_time: datetime | None = None, run_id: str | None = None):
        if not -(2**63) <= seed <= 2**63 - 1:
            raise ValueError("seed debe ser un entero de 64 bits con signo.")
        self.seed = seed
        self.scenario = Scenario(scenario)
        self.start_time = start_time if start_time is not None else datetime.now(UTC)
        if self.start_time.tzinfo is None or self.start_time.utcoffset() is None:
            raise ValueError("start_time debe incluir zona horaria.")
        self.start_time = self.start_time.astimezone(UTC)
        self.run_id = run_id if run_id is not None else str(uuid4())
        self.random = random.Random(seed)
        self.sequence = 0
        self.battery = 23.0 if self.scenario == Scenario.LOW_BATTERY else 100.0
        self.temperature = 63.0 if self.scenario == Scenario.OVERHEATING else 30.0
        self.speed = 0.0

    def step(self) -> TelemetrySample:
        self.sequence += 1
        tick = self.sequence - 1
        phase = tick % 80
        near_obstacle = self.scenario == Scenario.OBSTACLE or (
            self.scenario == Scenario.DEMO and 20 <= phase < 40
        )
        hot = self.scenario == Scenario.OVERHEATING or (
            self.scenario == Scenario.DEMO and 40 <= phase < 60
        )
        drain = self.scenario == Scenario.LOW_BATTERY or (
            self.scenario == Scenario.DEMO and phase >= 60
        )
        if near_obstacle:
            obstacle_tick = phase - 20 if self.scenario == Scenario.DEMO else tick
            distance = max(0.15, 2.8 - obstacle_tick * 0.3 + self.random.uniform(-0.04, 0.04))
        else:
            distance = max(1.0, 3 + 1.2 * math.sin(tick / 12) + self.random.uniform(-0.1, 0.1))
        distance = round(distance, 3)

        target_speed = max(0.0, 1.1 + 0.3 * math.sin(tick / 9) + self.random.uniform(-0.12, 0.12))
        safe_speed = min(3.0, max(0.0, (distance - 0.2) * 1.5))
        self.speed = min(safe_speed, self.speed + (target_speed - self.speed) * 0.35)
        self.battery = max(0.0, self.battery - (5.0 if drain else 0.015 + self.speed * 0.015))
        if self.battery <= 0:
            self.speed = 0.0
        target_temperature = 85.0 if hot else 28 + self.speed * 10
        self.temperature += (target_temperature - self.temperature) * 0.15 + self.random.uniform(-0.12, 0.12)
        return TelemetrySample(
            run_id=self.run_id, sequence=self.sequence, seed=self.seed, scenario=self.scenario,
            timestamp=self.start_time + timedelta(seconds=tick),
            battery_pct=round(self.battery, 3), temperature_c=round(self.temperature, 3),
            speed_m_s=math.floor(self.speed * 1000) / 1000, obstacle_distance_m=distance,
        )


def run_simulation(store: SQLiteStore, thresholds: AlertThresholds, *, seed: int = 42,
                   scenario: Scenario | str = Scenario.NORMAL, samples: int | None = None,
                   interval: float = 1.0) -> int:
    if samples is not None and samples < 1:
        raise ValueError("samples debe ser >= 1.")
    if not math.isfinite(interval) or interval < 0:
        raise ValueError("interval debe ser un número finito >= 0.")
    if interval == 0 and samples is None:
        raise ValueError("El modo de lote (--interval 0) requiere --samples.")
    start_time = datetime.now(UTC)
    if interval == 0 and samples is not None:
        start_time -= timedelta(seconds=samples - 1)
    simulator = RobotSimulator(seed=seed, scenario=scenario, start_time=start_time)
    store.initialize()
    service = TelemetryService(store, thresholds)
    logger.info("Sensores SIMULADOS | run_id=%s | seed=%s | escenario=%s | SQLite=%s",
                simulator.run_id, seed, scenario, store.path)
    count = 0
    deadline = time.monotonic()
    while samples is None or count < samples:
        if interval > 0:
            time.sleep(max(0.0, deadline - time.monotonic()))
        sample = simulator.step()
        if interval > 0:
            # step() conserva su reloj lógico. La ejecución con espera registra
            # la adquisición UTC real, también cuando se acelera o se retrasa.
            sample = sample.model_copy(update={"timestamp": datetime.now(UTC)})
        record = service.record(sample)
        count += 1
        logger.info("Lectura %s | batería=%.1f%% | temperatura=%.1f°C | velocidad=%.3f m/s | obstáculo=%.3f m",
                    record.sequence, record.battery_pct, record.temperature_c,
                    record.speed_m_s, record.obstacle_distance_m)
        deadline += interval
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description="RoboTelemetry Lite: sensores SIMULADOS; los datos se añaden a SQLite.")
    parser.add_argument("--seed", type=int, default=42, help="Semilla del generador reproducible (42).")
    parser.add_argument("--scenario", choices=[s.value for s in Scenario], default="normal")
    parser.add_argument("--samples", type=int, default=None, help="Lecturas a generar; omitido: hasta Ctrl+C.")
    parser.add_argument("--interval", type=float, default=1.0,
                        help="Intervalo real en segundos (1); se registra la hora de adquisición. "
                             "El paso lógico es 1 s. Con 0 se genera historial sintético y se requiere --samples.")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        settings = get_settings()
        count = run_simulation(SQLiteStore(settings.db_path), settings.thresholds,
                               seed=args.seed, scenario=args.scenario, samples=args.samples, interval=args.interval)
        logger.info("Fin: %s lecturas guardadas.", count)
    except KeyboardInterrupt:
        logger.info("Simulación detenida. Las lecturas confirmadas permanecen en SQLite.")
    except (ValueError, ValidationError) as exc:
        parser.error(str(exc))
    except (sqlite3.Error, OSError):
        logger.exception("No se pudo escribir en SQLite. Comprueba ruta, permisos y espacio disponible.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
