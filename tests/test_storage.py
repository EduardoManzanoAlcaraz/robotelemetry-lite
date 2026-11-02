import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta, timezone, tzinfo

import pytest

from robotelemetry.alerts import evaluate_alerts
from robotelemetry.config import AlertThresholds
from robotelemetry.models import AlertDraft, AlertKind
from robotelemetry.storage import SQLiteStore


def test_empty_database_returns_empty_results(store):
    assert store.latest() is None
    assert store.history() == []
    assert store.alerts() == []
    assert store.counts() == {"measurements": 0, "alerts": 0}


def test_database_initialization_creates_parent_directories(tmp_path):
    path = tmp_path / "nested" / "data" / "telemetry.sqlite3"
    database = SQLiteStore(path)
    database.initialize()
    assert path.is_file()
    with closing(sqlite3.connect(path)) as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_reopening_and_reinitializing_preserves_measurements_and_alerts(
    tmp_path, sample_factory
):
    path = tmp_path / "persistent.sqlite3"
    first = SQLiteStore(path)
    first.initialize()
    sample = sample_factory(battery_pct=5)
    stored = first.record(sample, evaluate_alerts(sample, AlertThresholds()))
    second = SQLiteStore(path)
    second.initialize()
    second.initialize()
    assert second.latest() == stored
    assert second.counts() == {"measurements": 1, "alerts": 1}
    alert = second.alerts()[0]
    assert alert.measurement_id == stored.id
    assert alert.kind == AlertKind.LOW_BATTERY
    assert alert.value == 5
    assert alert.threshold == 20


def test_duplicate_run_and_sequence_are_rejected_without_partial_write(
    store, sample_factory
):
    sample = sample_factory(battery_pct=5)
    alerts = evaluate_alerts(sample, AlertThresholds())
    store.record(sample, alerts)
    with pytest.raises(sqlite3.IntegrityError):
        store.record(sample, alerts)
    assert store.counts() == {"measurements": 1, "alerts": 1}


def test_invalid_alert_rolls_back_its_measurement_and_closes_connections(
    store, sample_factory, monkeypatch
):
    opened_connections = []
    original_connect = sqlite3.connect

    def track_connection(*args, **kwargs):
        connection = original_connect(*args, **kwargs)
        opened_connections.append(connection)
        return connection

    monkeypatch.setattr(sqlite3, "connect", track_connection)
    sample = sample_factory()
    # Bypass the model solely to exercise the database constraint and rollback.
    invalid_alert = AlertDraft.model_construct(
        kind=AlertKind.LOW_BATTERY,
        severity="invalid",
        message="Force a SQL constraint failure",
        value=5,
        threshold=20,
        created_at=sample.timestamp,
    )
    with pytest.raises(sqlite3.IntegrityError):
        store.record(sample, [invalid_alert])
    assert store.counts() == {"measurements": 0, "alerts": 0}
    # Keep strong references so garbage collection cannot hide leaked handles.
    # Both the failed transaction and the successful count query must close.
    assert opened_connections
    for connection in opened_connections:
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            connection.execute("SELECT 1")


def test_latest_uses_measurement_time_instead_of_insertion_order(
    store, sample_factory
):
    newer = sample_factory(sequence=2)
    older = sample_factory(sequence=1, timestamp=newer.timestamp - timedelta(seconds=1))
    newer_record = store.record(newer, [])
    store.record(older, [])
    assert store.latest() == newer_record


def test_history_pagination_is_stable_for_tied_timestamps(store, sample_factory):
    records = [store.record(sample_factory(sequence=index), []) for index in range(1, 6)]
    assert store.history(limit=2) == [records[4], records[3]]
    assert store.history(limit=2, offset=2) == [records[2], records[1]]
    assert store.history(offset=99) == []


@pytest.mark.parametrize("store_method", ["history", "alerts"])
@pytest.mark.parametrize("offset", [-1, 2**63, 10**100])
def test_invalid_offsets_are_rejected_before_opening_a_connection(
    store, monkeypatch, store_method, offset
):
    def unexpected_connection():
        raise AssertionError("Invalid offset opened a database connection")

    monkeypatch.setattr(store, "_connection", unexpected_connection)
    with pytest.raises(ValueError):
        getattr(store, store_method)(offset=offset)


@pytest.mark.parametrize("store_method", ["history", "alerts"])
def test_largest_sqlite_offset_is_accepted(store, store_method):
    assert getattr(store, store_method)(offset=2**63 - 1) == []


def test_history_date_filters_are_inclusive(store, sample_factory):
    start = sample_factory().timestamp
    for index in range(5):
        store.record(
            sample_factory(sequence=index + 1, timestamp=start + timedelta(seconds=index)),
            [],
        )
    history = store.history(
        since=start + timedelta(seconds=1), until=start + timedelta(seconds=3)
    )
    assert [sample.sequence for sample in history] == [4, 3, 2]


class UndefinedOffset(tzinfo):
    """A tzinfo can still be naive when its UTC offset is undefined."""

    def utcoffset(self, value):
        return None


@pytest.mark.parametrize(("parameter", "timestamp"), [
    ("since", datetime(2026, 1, 1)),
    ("until", datetime(2026, 1, 1, tzinfo=UndefinedOffset())),
])
def test_history_rejects_dates_without_utc_offset_before_opening_database(
    tmp_path, parameter, timestamp
):
    path = tmp_path / "not-created" / "telemetry.sqlite3"
    database = SQLiteStore(path)
    with pytest.raises(ValueError, match="zona horaria"):
        database.history(**{parameter: timestamp})
    assert not path.parent.exists()


def test_history_rejects_reversed_utc_range_before_opening_database(tmp_path):
    path = tmp_path / "not-created" / "telemetry.sqlite3"
    database = SQLiteStore(path)
    since = datetime(2026, 1, 1, 1, tzinfo=timezone(timedelta(hours=1)))
    until = datetime(2025, 12, 31, 19, 59, 59, tzinfo=timezone(timedelta(hours=-4)))
    with pytest.raises(ValueError, match="since debe ser anterior o igual a until"):
        database.history(since=since, until=until)
    assert not path.parent.exists()


def test_history_equal_bounds_in_different_timezones_select_same_instant(
    store, sample_factory
):
    timestamp = datetime(2026, 1, 1, microsecond=123456, tzinfo=UTC)
    record = store.record(sample_factory(timestamp=timestamp), [])
    since = timestamp.astimezone(timezone(timedelta(hours=5, minutes=30)))
    until = timestamp.astimezone(timezone(timedelta(hours=-4)))
    assert store.history(since=since, until=until) == [record]


def test_alert_history_can_be_filtered_and_paginated(store, sample_factory):
    sample = sample_factory(battery_pct=5, temperature_c=90, obstacle_distance_m=0.1)
    store.record(sample, evaluate_alerts(sample, AlertThresholds()))
    assert len(store.alerts(limit=2)) == 2
    assert len(store.alerts(limit=2, offset=2)) == 1
    selected = store.alerts(kind=AlertKind.HIGH_TEMPERATURE)
    assert len(selected) == 1
    assert selected[0].kind == AlertKind.HIGH_TEMPERATURE


def test_service_evaluates_and_stores_alerts_with_the_measurement(
    store, service, sample_factory
):
    record = service.record(sample_factory(battery_pct=10))
    assert record.id > 0
    assert store.counts() == {"measurements": 1, "alerts": 1}
    assert store.alerts()[0].measurement_id == record.id


def test_sql_metacharacters_in_run_id_are_stored_as_data(store, sample_factory):
    sample = sample_factory(run_id="Robert'); DROP TABLE measurements;--")
    store.record(sample, [])
    assert store.latest().run_id == sample.run_id
    assert store.counts()["measurements"] == 1
