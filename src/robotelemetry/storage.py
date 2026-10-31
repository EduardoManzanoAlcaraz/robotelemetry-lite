"""Repositorio SQLite con conexiones cortas y escritura atómica de lectura + alertas."""

from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
import sqlite3
from typing import Iterator

from robotelemetry.models import AlertDraft, AlertKind, AlertRecord, TelemetryRecord, TelemetrySample

MAX_SQLITE_OFFSET = 2**63 - 1


def utc_text(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("La fecha debe incluir zona horaria.")
    return value.astimezone(UTC).isoformat(timespec="microseconds")


class SQLiteStore:
    def __init__(self, path: Path):
        self.path = Path(path).resolve()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS measurements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL CHECK(length(run_id) BETWEEN 1 AND 64),
                    sequence INTEGER NOT NULL CHECK(sequence >= 1),
                    seed INTEGER NOT NULL,
                    scenario TEXT NOT NULL CHECK(scenario IN
                        ('normal','low_battery','overheating','obstacle','demo')),
                    timestamp TEXT NOT NULL,
                    battery_pct REAL NOT NULL CHECK(battery_pct BETWEEN 0 AND 100),
                    temperature_c REAL NOT NULL CHECK(temperature_c BETWEEN -20 AND 150),
                    speed_m_s REAL NOT NULL CHECK(speed_m_s BETWEEN 0 AND 3),
                    obstacle_distance_m REAL NOT NULL CHECK(obstacle_distance_m BETWEEN 0 AND 20),
                    UNIQUE(run_id, sequence)
                );
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    measurement_id INTEGER NOT NULL REFERENCES measurements(id),
                    kind TEXT NOT NULL CHECK(kind IN
                        ('low_battery','high_temperature','near_obstacle')),
                    severity TEXT NOT NULL CHECK(severity IN ('warning','critical')),
                    message TEXT NOT NULL,
                    value REAL NOT NULL,
                    threshold REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(measurement_id, kind)
                );
                CREATE INDEX IF NOT EXISTS idx_measurements_time ON measurements(timestamp DESC, id DESC);
                CREATE INDEX IF NOT EXISTS idx_alerts_time ON alerts(created_at DESC, id DESC);
                CREATE INDEX IF NOT EXISTS idx_alerts_kind_time ON alerts(kind, created_at DESC, id DESC);
            """)

    def record(self, sample: TelemetrySample, alerts: list[AlertDraft]) -> TelemetryRecord:
        with self._connection() as connection:
            cursor = connection.execute("""
                INSERT INTO measurements
                (run_id, sequence, seed, scenario, timestamp, battery_pct,
                 temperature_c, speed_m_s, obstacle_distance_m)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (sample.run_id, sample.sequence, sample.seed, sample.scenario.value,
                  utc_text(sample.timestamp), sample.battery_pct, sample.temperature_c,
                  sample.speed_m_s, sample.obstacle_distance_m))
            measurement_id = cursor.lastrowid
            connection.executemany("""
                INSERT INTO alerts (measurement_id, kind, severity, message, value, threshold, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, [(measurement_id, alert.kind, alert.severity, alert.message, alert.value,
                   alert.threshold, utc_text(alert.created_at)) for alert in alerts])
            return TelemetryRecord(**sample.model_dump(), id=measurement_id)

    def latest(self) -> TelemetryRecord | None:
        rows = self.history(limit=1)
        return rows[0] if rows else None

    @staticmethod
    def _pagination(limit: int, offset: int) -> None:
        if not 1 <= limit <= 1000 or not 0 <= offset <= MAX_SQLITE_OFFSET:
            raise ValueError(
                f"limit debe estar entre 1 y 1000; offset debe estar entre 0 y {MAX_SQLITE_OFFSET}."
            )

    def history(self, *, limit: int = 100, offset: int = 0,
                since: datetime | None = None, until: datetime | None = None) -> list[TelemetryRecord]:
        self._pagination(limit, offset)
        if since is not None and until is not None and since > until:
            raise ValueError("since debe ser anterior o igual a until.")
        clauses: list[str] = []
        values: list[object] = []
        for operator, date in ((">=", since), ("<=", until)):
            if date is not None:
                clauses.append(f"timestamp {operator} ?")
                values.append(utc_text(date))
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM measurements" + where + " ORDER BY timestamp DESC, id DESC LIMIT ? OFFSET ?",
                (*values, limit, offset),
            ).fetchall()
        return [TelemetryRecord(**dict(row)) for row in rows]

    def alerts(self, *, limit: int = 100, offset: int = 0,
               kind: AlertKind | None = None) -> list[AlertRecord]:
        self._pagination(limit, offset)
        where = " WHERE kind = ?" if kind is not None else ""
        values = (kind, limit, offset) if kind is not None else (limit, offset)
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM alerts" + where + " ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
                values,
            ).fetchall()
        return [AlertRecord(**dict(row)) for row in rows]

    def counts(self) -> dict[str, int]:
        with self._connection() as connection:
            row = connection.execute("""
                SELECT (SELECT COUNT(*) FROM measurements) AS measurements,
                       (SELECT COUNT(*) FROM alerts) AS alerts
            """).fetchone()
        return dict(row)
