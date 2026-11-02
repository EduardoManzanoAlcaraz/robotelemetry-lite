from datetime import UTC, datetime, timedelta
import logging
import sqlite3
import sys
from types import SimpleNamespace

import pytest

from robotelemetry.alerts import evaluate_alerts
from robotelemetry.config import AlertThresholds
from robotelemetry.models import AlertKind, Scenario
from robotelemetry.simulator import RobotSimulator, run_simulation
import robotelemetry.simulator as simulator_module
from robotelemetry.storage import SQLiteStore


@pytest.fixture
def cli_database(tmp_path, monkeypatch):
    """La CLI real usa exclusivamente una ruta y umbrales controlados por el test."""
    database = tmp_path / "cli.sqlite3"
    monkeypatch.setenv("ROBO_DB_PATH", str(database))
    monkeypatch.setenv("ROBO_BATTERY_LOW_PCT", "20")
    monkeypatch.setenv("ROBO_TEMPERATURE_HIGH_C", "65")
    monkeypatch.setenv("ROBO_OBSTACLE_NEAR_M", "0.5")
    return database


def invoke_cli(monkeypatch, *arguments):
    monkeypatch.setattr(sys, "argv", ["robotelemetry.simulator", *arguments])
    return simulator_module.main()


@pytest.fixture
def acquisition_clock(monkeypatch):
    """Avanzar ambos relojes sin esperar ni depender de la velocidad del equipo."""
    epoch = datetime(2026, 10, 26, tzinfo=UTC)
    elapsed = [0.0]

    class Clock:
        @staticmethod
        def now(tz=None):
            return (epoch + timedelta(seconds=elapsed[0])).astimezone(tz)

    def sleep(seconds):
        elapsed[0] += seconds

    monkeypatch.setattr(simulator_module, "datetime", Clock)
    monkeypatch.setattr(simulator_module, "time", SimpleNamespace(
        monotonic=lambda: elapsed[0], sleep=sleep,
    ))
    return epoch, Clock


@pytest.mark.parametrize("interval", [0.1, 0.25, 0.5, 1.0, 2.0])
def test_paced_run_records_acquisition_times_without_future_readings(store, acquisition_clock, interval):
    epoch, clock = acquisition_clock
    run_simulation(store, AlertThresholds(), samples=4, interval=interval)
    readings = sorted(store.history(), key=lambda reading: reading.sequence)
    assert all(reading.timestamp <= clock.now(UTC) for reading in readings)
    assert [reading.timestamp for reading in readings] == [
        epoch + timedelta(seconds=index * interval) for index in range(4)
    ]
    # La simulación sigue avanzando cuatro pasos, aunque se acelere su adquisición.
    expected = RobotSimulator(start_time=epoch, run_id="reference")
    sensors = {"battery_pct", "temperature_c", "speed_m_s", "obstacle_distance_m"}
    assert [reading.model_dump(include=sensors) for reading in readings] == [
        expected.step().model_dump(include=sensors) for _ in range(4)
    ]


def test_unbounded_accelerated_run_records_acquisition_times(store, acquisition_clock, monkeypatch):
    epoch, clock = acquisition_clock
    original_record = store.record

    def stop_after_four_readings(sample, alerts):
        record = original_record(sample, alerts)
        if sample.sequence == 4:
            raise KeyboardInterrupt
        return record

    monkeypatch.setattr(store, "record", stop_after_four_readings)
    with pytest.raises(KeyboardInterrupt):
        run_simulation(store, AlertThresholds(), interval=0.1)
    readings = sorted(store.history(), key=lambda reading: reading.sequence)
    assert len(readings) == 4
    assert all(reading.timestamp <= clock.now(UTC) for reading in readings)
    assert [reading.timestamp for reading in readings] == [
        epoch + timedelta(seconds=index / 10) for index in range(4)
    ]


def test_zero_interval_batch_keeps_historical_timeline(store, acquisition_clock):
    epoch, clock = acquisition_clock
    run_simulation(store, AlertThresholds(), samples=4, interval=0)
    readings = sorted(store.history(), key=lambda reading: reading.sequence)
    assert [reading.timestamp for reading in readings] == [
        epoch - timedelta(seconds=3 - index) for index in range(4)
    ]
    assert readings[-1].timestamp == clock.now(UTC)


def test_seed_reproduces_complete_samples_with_same_clock_and_run_id():
    options = dict(
        seed=1729,
        scenario=Scenario.DEMO,
        start_time=datetime(2026, 1, 1, tzinfo=UTC),
        run_id="reproducible-run",
    )
    first = RobotSimulator(**options)
    second = RobotSimulator(**options)
    assert [first.step() for _ in range(80)] == [second.step() for _ in range(80)]


def test_different_seeds_produce_different_sensor_values():
    first = RobotSimulator(seed=1)
    second = RobotSimulator(seed=2)
    first_values = [first.step().model_dump(exclude={"run_id", "timestamp", "seed"}) for _ in range(10)]
    second_values = [second.step().model_dump(exclude={"run_id", "timestamp", "seed"}) for _ in range(10)]
    assert first_values != second_values


def test_sequences_and_timestamps_advance_one_second():
    start = datetime(2026, 1, 1, tzinfo=UTC)
    simulator = RobotSimulator(start_time=start)
    samples = [simulator.step() for _ in range(5)]
    assert [sample.sequence for sample in samples] == [1, 2, 3, 4, 5]
    assert [sample.timestamp for sample in samples] == [
        start + timedelta(seconds=index) for index in range(5)
    ]


@pytest.mark.parametrize("scenario", list(Scenario))
def test_long_runs_respect_physics_and_valid_ranges(scenario):
    simulator = RobotSimulator(seed=42, scenario=scenario)
    previous_battery = 100.0
    for _ in range(240):
        sample = simulator.step()
        assert 0 <= sample.battery_pct <= previous_battery
        previous_battery = sample.battery_pct
        assert -20 <= sample.temperature_c <= 150
        assert 0 <= sample.obstacle_distance_m <= 20
        braking_limit = min(3, max(0, (sample.obstacle_distance_m - 0.2) * 1.5))
        assert 0 <= sample.speed_m_s <= braking_limit + 0.002
        if sample.battery_pct == 0:
            assert sample.speed_m_s == 0


@pytest.mark.parametrize(
    ("scenario", "expected_kind"),
    [
        (Scenario.LOW_BATTERY, AlertKind.LOW_BATTERY),
        (Scenario.OVERHEATING, AlertKind.HIGH_TEMPERATURE),
        (Scenario.OBSTACLE, AlertKind.NEAR_OBSTACLE),
    ],
)
def test_anomaly_scenarios_trigger_expected_rule(scenario, expected_kind):
    simulator = RobotSimulator(scenario=scenario)
    kinds = {
        alert.kind
        for _ in range(20)
        for alert in evaluate_alerts(simulator.step(), AlertThresholds())
    }
    assert expected_kind in kinds


def test_demo_exercises_all_three_alert_rules():
    simulator = RobotSimulator(scenario=Scenario.DEMO)
    kinds = {
        alert.kind
        for _ in range(80)
        for alert in evaluate_alerts(simulator.step(), AlertThresholds())
    }
    assert kinds == set(AlertKind)


def test_separate_runs_have_distinct_ids():
    assert RobotSimulator().step().run_id != RobotSimulator().step().run_id


@pytest.mark.parametrize("seed", [-(2**63) - 1, 2**63])
def test_out_of_range_seed_is_rejected_before_simulation_starts(seed):
    with pytest.raises(ValueError):
        RobotSimulator(seed=seed)


@pytest.mark.parametrize("seed", [-(2**63), 2**63 - 1])
def test_seed_integer_boundaries_can_be_persisted(store, seed):
    run_simulation(store, AlertThresholds(), seed=seed, samples=1, interval=0)
    assert store.latest().seed == seed


def test_fast_batch_records_real_measurements_and_alerts(store):
    count = run_simulation(
        store, AlertThresholds(), seed=42, scenario=Scenario.LOW_BATTERY,
        samples=20, interval=0,
    )
    assert count == 20
    assert store.counts()["measurements"] == 20
    assert store.counts()["alerts"] > 0


def test_restart_of_batch_appends_a_distinct_run_without_resetting_data(store):
    for _ in range(2):
        run_simulation(store, AlertThresholds(), samples=3, interval=0)
    records = store.history()
    assert len(records) == 6
    assert len({record.run_id for record in records}) == 2
    assert sorted(record.sequence for record in records) == [1, 1, 2, 2, 3, 3]


@pytest.mark.parametrize(
    "options",
    [
        {"samples": 0, "interval": 0},
        {"samples": 1, "interval": -1},
        {"samples": 1, "interval": float("nan")},
        {"samples": 1, "interval": float("inf")},
        {"samples": None, "interval": 0},
        {"samples": 1, "interval": 0, "seed": 2**63},
        {"samples": 1, "interval": 0, "seed": -(2**63) - 1},
    ],
)
def test_invalid_runner_options_fail_before_any_measurement_is_written(store, options):
    with pytest.raises(ValueError):
        run_simulation(store, AlertThresholds(), **options)
    assert store.counts() == {"measurements": 0, "alerts": 0}


def test_simulator_rejects_start_time_without_timezone():
    with pytest.raises(ValueError, match="start_time debe incluir zona horaria"):
        RobotSimulator(start_time=datetime(2026, 1, 1))


def test_cli_parses_options_and_persists_demo_to_configured_database(
    cli_database, monkeypatch, caplog
):
    with caplog.at_level(logging.INFO, logger="robotelemetry.simulator"):
        exit_code = invoke_cli(
            monkeypatch, "--seed", "42", "--scenario", "demo", "--samples", "80", "--interval", "0"
        )
    assert exit_code == 0
    persisted = SQLiteStore(cli_database)
    assert persisted.counts() == {"measurements": 80, "alerts": 34}
    assert {reading.scenario for reading in persisted.history()} == {Scenario.DEMO}
    assert {reading.seed for reading in persisted.history()} == {42}
    assert {alert.kind for alert in persisted.alerts()} == set(AlertKind)
    assert "Sensores SIMULADOS" in caplog.text
    assert "Fin: 80 lecturas guardadas." in caplog.text


def test_cli_invalid_argument_reports_usage_without_creating_database(
    cli_database, monkeypatch, capsys
):
    with pytest.raises(SystemExit) as error:
        invoke_cli(monkeypatch, "--scenario", "unsupported-scenario")
    assert error.value.code == 2
    assert "usage:" in capsys.readouterr().err
    assert not cli_database.exists()


def test_cli_invalid_runner_option_returns_argument_error_without_creating_database(
    cli_database, monkeypatch, capsys
):
    with pytest.raises(SystemExit) as error:
        invoke_cli(monkeypatch, "--samples", "0", "--interval", "0")
    assert error.value.code == 2
    assert "samples debe ser >= 1" in capsys.readouterr().err
    assert not cli_database.exists()


def test_cli_invalid_environment_returns_argument_error_without_creating_database(
    cli_database, monkeypatch, capsys
):
    monkeypatch.setenv("ROBO_BATTERY_LOW_PCT", "101")
    with pytest.raises(SystemExit) as error:
        invoke_cli(monkeypatch, "--samples", "1", "--interval", "0")
    assert error.value.code == 2
    assert "battery_low_pct" in capsys.readouterr().err
    assert not cli_database.exists()


def test_cli_database_open_error_returns_failure_and_preserves_existing_path(
    cli_database, monkeypatch, caplog
):
    cli_database.mkdir()
    sentinel = cli_database / "keep.txt"
    sentinel.write_text("existing data", encoding="utf-8")
    exit_code = invoke_cli(monkeypatch, "--samples", "1", "--interval", "0")
    assert exit_code == 1
    assert sentinel.read_text(encoding="utf-8") == "existing data"
    assert any(record.exc_info and isinstance(record.exc_info[1], sqlite3.Error)
               for record in caplog.records)
    assert "No se pudo escribir en SQLite" in caplog.text


def test_cli_filesystem_error_returns_failure_and_preserves_existing_file(
    cli_database, monkeypatch, caplog
):
    blocked_parent = cli_database.parent / "existing-file"
    blocked_parent.write_bytes(b"preserve")
    monkeypatch.setenv("ROBO_DB_PATH", str(blocked_parent / "telemetry.sqlite3"))
    exit_code = invoke_cli(monkeypatch, "--samples", "1", "--interval", "0")
    assert exit_code == 1
    assert blocked_parent.read_bytes() == b"preserve"
    assert any(record.exc_info and isinstance(record.exc_info[1], OSError)
               for record in caplog.records)
    assert "No se pudo escribir en SQLite" in caplog.text


def test_cli_interruption_keeps_committed_readings_and_exits_cleanly(
    cli_database, monkeypatch, acquisition_clock, caplog
):
    record = SQLiteStore.record

    def interrupt_after_commit(store, sample, alerts):
        saved = record(store, sample, alerts)
        if sample.sequence == 4:
            raise KeyboardInterrupt
        return saved

    # Interrumpir en un punto conocido conserva simulación, servicio y SQL reales.
    monkeypatch.setattr(SQLiteStore, "record", interrupt_after_commit)
    with caplog.at_level(logging.INFO, logger="robotelemetry.simulator"):
        exit_code = invoke_cli(monkeypatch, "--scenario", "low_battery", "--interval", "0.1")
    assert exit_code == 0
    persisted = SQLiteStore(cli_database)
    assert persisted.counts()["measurements"] == 4
    assert [reading.sequence for reading in reversed(persisted.history())] == [1, 2, 3, 4]
    assert "Simulación detenida. Las lecturas confirmadas permanecen en SQLite." in caplog.text
    assert "Fin:" not in caplog.text
