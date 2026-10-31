"""Seguridad de la herramienta de demo: ninguna prueba usa el histórico local."""

import importlib.util
from contextlib import closing
from pathlib import Path
import sqlite3

import pytest


spec = importlib.util.spec_from_file_location(
    "prepare_demo", Path(__file__).resolve().parents[1] / "scripts" / "prepare_demo.py"
)
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)


def rows(path):
    with closing(sqlite3.connect(path)) as connection:
        return connection.execute(
            "SELECT scenario, sequence, seed, battery_pct, temperature_c, speed_m_s, obstacle_distance_m "
            "FROM measurements ORDER BY id"
        ).fetchall()


def test_prepares_two_reproducible_runs_and_all_alert_kinds(tmp_path):
    first = tmp_path / "first.sqlite3"
    second = tmp_path / "second.sqlite3"
    result = demo.prepare_demo(first)
    demo.prepare_demo(second)
    assert result["measurements"] == 140
    assert result["alerts"] == 34
    assert result["runs"] == 2
    assert rows(first) == rows(second)
    with closing(sqlite3.connect(first)) as connection:
        assert connection.execute("SELECT COUNT(DISTINCT run_id) FROM measurements").fetchone()[0] == 2
        assert connection.execute("SELECT scenario,COUNT(*) FROM measurements GROUP BY scenario").fetchall() == [
            ("demo", 80), ("normal", 60)
        ]
        assert {row[0] for row in connection.execute("SELECT DISTINCT kind FROM alerts")} == {
            "low_battery", "high_temperature", "near_obstacle"
        }
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


@pytest.mark.parametrize("existing", ["database", "-wal", "-shm", "-journal"])
def test_refuses_existing_database_or_sidecar_without_changing_bytes(tmp_path, existing):
    target = tmp_path / "existing.sqlite3"
    protected = target if existing == "database" else Path(f"{target}{existing}")
    content = b"existing local data must remain untouched"
    protected.write_bytes(content)
    with pytest.raises(FileExistsError, match="requiere una ruta nueva"):
        demo.prepare_demo(target)
    assert protected.read_bytes() == content
    if existing != "database":
        assert not target.exists()


def test_invalid_seed_does_not_create_database(tmp_path):
    target = tmp_path / "invalid.sqlite3"
    with pytest.raises(ValueError, match="64 bits"):
        demo.prepare_demo(target, seed=2**63)
    assert not target.exists()
