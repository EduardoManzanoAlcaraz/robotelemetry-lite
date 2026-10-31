"""Exercise the real Streamlit entrypoint without external servers."""

import csv
from datetime import UTC, datetime, timedelta
import io
import json
from pathlib import Path

import httpx
import pyarrow as pa
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from robotelemetry.dashboard import DashboardError, fetch_snapshot


ENTRYPOINT = Path(__file__).resolve().parents[1] / "dashboard.py"
SECTION_TITLES = (
    "Estado actual",
    "Alertas en la última lectura",
    "Gráficas históricas",
    "Incidencias históricas",
    "Datos y exportación",
)


def api_responses(monkeypatch, *, has_data=True, status_code=200,
                  latest_overrides=None, history_overrides=None, alert_overrides=None):
    timestamp = datetime.now(UTC).isoformat()
    measurement = {
        "id": 1,
        "run_id": "dashboard-test",
        "sequence": 1,
        "seed": 42,
        "scenario": "demo",
        "timestamp": timestamp,
        "battery_pct": 15.0,
        "temperature_c": 40.0,
        "speed_m_s": 0.7,
        "obstacle_distance_m": 2.0,
    }
    measurement.update(latest_overrides or {})
    history = [measurement] if has_data else []
    if has_data and history_overrides is not None:
        history = [
            {**measurement, "id": index, "sequence": index, **overrides}
            for index, overrides in enumerate(history_overrides, start=1)
        ]
    alert = {
        "id": 1,
        "measurement_id": 1,
        "kind": "low_battery",
        "severity": "warning",
        "message": "Batería baja",
        "value": 15.0,
        "threshold": 20.0,
        "created_at": timestamp,
    }
    alerts = [alert] if has_data else []
    if has_data and alert_overrides is not None:
        alerts = [
            {**alert, "id": index, "measurement_id": index, **overrides}
            for index, overrides in enumerate(alert_overrides, start=1)
        ]
    payloads = {
        "/health": {"status": "ok", "measurements": len(history), "alerts": len(alerts)},
        "/config": {"battery_low_pct": 20.0, "temperature_high_c": 65.0, "obstacle_near_m": 0.5},
        "/telemetry/latest": measurement,
        "/telemetry/history": history,
        "/alerts": alerts,
    }
    calls = []

    def get(self, url, **kwargs):
        calls.append((url, kwargs))
        status = 404 if url == "/telemetry/latest" and not has_data else status_code
        return httpx.Response(status, json=payloads[url], request=httpx.Request("GET", f"http://test{url}"))

    monkeypatch.setattr(httpx.Client, "get", get)
    return calls


def chart_elements(app):
    # Streamlit renamed this protobuf element; support both supported versions.
    return list(app.get("vega_lite_chart")) or list(app.get("arrow_vega_lite_chart"))


def chart_dataframe(chart):
    """Decode the data actually sent to the browser, not the input fixture."""
    proto = chart.proto
    payload = proto.data.data
    if not payload:
        assert len(proto.datasets) == 1
        payload = proto.datasets[0].data.data
    return pa.ipc.open_stream(payload).read_all().to_pandas()


def section_elements(app, title):
    """Scope assertions by visible headings, independent of CSS or containers."""
    nodes = list(app.main)
    headings = {"header", "subheader"}
    start = next(index for index, node in enumerate(nodes) if node.type in headings and node.value == title)
    end = next(
        (index for index in range(start + 1, len(nodes))
         if nodes[index].type in headings and nodes[index].value in SECTION_TITLES),
        len(nodes),
    )
    return nodes[start + 1:end]


def test_dashboard_displays_measurements_history_and_alerts(monkeypatch):
    api_responses(monkeypatch)
    app = AppTest.from_file(str(ENTRYPOINT), default_timeout=20).run()
    assert not app.exception
    assert [metric.label for metric in app.metric] == ["Batería", "Temperatura", "Velocidad", "Obstáculo más próximo"]
    assert [metric.value for metric in app.metric] == ["15.0 %", "40.0 °C", "0.70 m/s", "2.00 m"]
    assert any("SENSORES SIMULADOS" in message.value for message in app.info)
    assert any("API conectada" in message.value for message in app.success)
    assert any("Batería baja" in message.value for message in app.warning)
    assert len(app.dataframe) == 2


def test_dashboard_empty_database_has_executable_guidance(monkeypatch):
    api_responses(monkeypatch, has_data=False)
    app = AppTest.from_file(str(ENTRYPOINT), default_timeout=20).run()
    assert not app.exception
    assert not app.metric
    assert any("Aún no hay telemetría" in message.value for message in app.info)
    assert any("No hay incidencias" in message.value for message in app.info)
    assert any("API conectada" in message.value for message in app.success)


def test_dashboard_connection_failure_is_visible_without_traceback(monkeypatch):
    def disconnected(self, url, **kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(httpx.Client, "get", disconnected)
    app = AppTest.from_file(str(ENTRYPOINT), default_timeout=20).run()
    assert not app.exception
    assert any("API no disponible" in message.value for message in app.error)
    assert any("No se puede conectar" in message.value for message in app.error)


def test_dashboard_manual_refresh_and_history_control_consult_api(monkeypatch):
    calls = api_responses(monkeypatch)
    app = AppTest.from_file(str(ENTRYPOINT), default_timeout=20).run()
    before_toggle = len(calls)
    app.toggle[0].set_value(False).run()
    assert len(calls) > before_toggle
    assert any(path == "/health" for path, _ in calls[before_toggle:])
    before_slider = len(calls)
    app.select_slider[0].set_value(60).run()
    assert len(calls) > before_slider
    assert any(path == "/telemetry/history" and params.get("params", {}).get("limit") == 60
               for path, params in calls[before_slider:])
    before_button = len(calls)
    app.button[0].click().run()
    assert not app.exception
    assert len(calls) > before_button
    assert any(path == "/telemetry/latest" for path, _ in calls[before_button:])
    assert any(path == "/telemetry/history" and params.get("params", {}).get("limit") == 60
               for path, params in calls[before_button:])


def test_dashboard_service_failure_reports_http_status(monkeypatch):
    api_responses(monkeypatch, status_code=503)
    with pytest.raises(DashboardError, match="HTTP 503"):
        fetch_snapshot("http://test", 60)


def test_dashboard_http_failure_has_visible_disconnected_state(monkeypatch):
    api_responses(monkeypatch, status_code=503)
    app = AppTest.from_file(str(ENTRYPOINT), default_timeout=20).run()
    assert not app.exception
    assert any("API no disponible" in message.value for message in app.error)
    assert any("HTTP 503" in message.value for message in app.error)
    assert not any("API conectada" in message.value for message in app.success)


def test_dashboard_invalid_json_is_recoverable(monkeypatch):
    def malformed(self, url, **kwargs):
        return httpx.Response(200, content=b"broken", request=httpx.Request("GET", f"http://test{url}"))

    monkeypatch.setattr(httpx.Client, "get", malformed)
    with pytest.raises(DashboardError, match="respuesta no válida"):
        fetch_snapshot("http://test", 60)


def test_dashboard_separates_current_state_history_and_export(monkeypatch):
    api_responses(monkeypatch)
    app = AppTest.from_file(str(ENTRYPOINT), default_timeout=20).run()
    assert not app.exception
    headings = [node.value for node in app.main
                if node.type in {"header", "subheader"} and node.value in SECTION_TITLES]
    assert headings == list(SECTION_TITLES)
    assert len(chart_elements(app)) == 4
    assert any(node.type == "download_button" for node in section_elements(app, "Datos y exportación"))


def test_dashboard_historical_incidents_do_not_become_current_alerts(monkeypatch):
    api_responses(
        monkeypatch,
        latest_overrides={"battery_pct": 80.0, "temperature_c": 35.0, "obstacle_distance_m": 2.0},
        alert_overrides=[{"measurement_id": 42, "message": "Batería baja en una lectura anterior"}],
    )
    app = AppTest.from_file(str(ENTRYPOINT), default_timeout=20).run()
    assert not app.exception
    current = section_elements(app, "Alertas en la última lectura")
    assert not [node for node in current if node.type in {"warning", "error"}]
    historical = section_elements(app, "Incidencias históricas")
    assert any("Batería baja en una lectura anterior" in node.value
               for node in historical if node.type in {"warning", "error", "markdown", "caption"})
    tables = [node for node in historical if node.type == "dataframe"]
    assert len(tables) == 1
    assert tables[0].value["measurement_id"].tolist() == [42]


def test_dashboard_shows_all_three_current_rules_at_inclusive_thresholds(monkeypatch):
    api_responses(
        monkeypatch,
        latest_overrides={"battery_pct": 20.0, "temperature_c": 65.0, "obstacle_distance_m": 0.5},
        alert_overrides=[],
    )
    app = AppTest.from_file(str(ENTRYPOINT), default_timeout=20).run()
    assert not app.exception
    active = [node for node in section_elements(app, "Alertas en la última lectura")
              if node.type in {"warning", "error"}]
    assert len(active) == 3
    assert any("batería" in node.value.lower() and node.type == "warning" for node in active)
    assert any("temperatura" in node.value.lower() and node.type == "error" for node in active)
    assert any("obstáculo" in node.value.lower() and node.type == "error" for node in active)


def test_dashboard_previews_three_historical_incidents_and_preserves_full_table(monkeypatch):
    messages = [f"Incidencia histórica {index}" for index in range(1, 6)]
    calls = api_responses(monkeypatch, alert_overrides=[{"message": message} for message in messages])
    app = AppTest.from_file(str(ENTRYPOINT), default_timeout=20).run()
    assert not app.exception
    historical = section_elements(app, "Incidencias históricas")
    visible_text = "\n".join(node.value for node in historical
                             if node.type in {"warning", "error", "markdown", "caption", "info"})
    assert all(message in visible_text for message in messages[:3])
    assert all(message not in visible_text for message in messages[3:])
    tables = [node for node in historical if node.type == "dataframe"]
    assert len(tables) == 1
    assert tables[0].value["message"].tolist() == messages
    assert any(node.type == "expander" and len(node.dataframe) == 1 for node in historical)
    assert any(path == "/alerts" and params.get("params", {}).get("limit") == 30 for path, params in calls)


def test_dashboard_csv_download_contains_the_displayed_history(monkeypatch):
    api_responses(monkeypatch, history_overrides=[{"battery_pct": 75.0}, {"battery_pct": 76.0}])
    downloads = []
    original_download_button = st.download_button

    def capture_download(*args, **kwargs):
        downloads.append(kwargs)
        return original_download_button(*args, **kwargs)

    monkeypatch.setattr(st, "download_button", capture_download)
    app = AppTest.from_file(str(ENTRYPOINT), default_timeout=20).run()
    assert not app.exception
    buttons = app.get("download_button")
    assert len(buttons) == 1
    assert not buttons[0].proto.disabled
    assert buttons[0].proto.url
    assert len(downloads) == 1
    assert downloads[0]["mime"] == "text/csv"
    assert downloads[0]["file_name"].endswith(".csv")
    content = downloads[0]["data"]
    if isinstance(content, bytes):
        content = content.decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(content)))
    displayed = app.dataframe[-1].value
    assert len(rows) == len(displayed) == 2
    assert [int(row["id"]) for row in rows] == displayed["id"].tolist()
    assert [float(row["battery_pct"]) for row in rows] == displayed["battery_pct"].tolist()
    assert [datetime.fromisoformat(row["timestamp"]).astimezone(UTC) for row in rows] == displayed["timestamp"].tolist()


def test_dashboard_preserves_mixed_iso8601_readings_in_table_and_all_charts(monkeypatch):
    timestamps = [
        "2026-10-25T10:00:00.123456Z",
        "2026-10-25T11:00:01+01:00",
        "2026-10-25T06:00:02.25-04:00",
        "2026-10-25T10:00:03Z",
        "2026-10-25T11:00:04.987+01:00",
        "2026-10-25T06:00:05-04:00",
    ]
    history = [
        {"timestamp": timestamp, "battery_pct": 70.0 + index,
         "run_id": f"run-{index % 2}"}
        for index, timestamp in reversed(list(enumerate(timestamps)))
    ]
    api_responses(monkeypatch, history_overrides=history)
    app = AppTest.from_file(str(ENTRYPOINT), default_timeout=20).run()
    assert not app.exception
    assert not app.error
    charts = chart_elements(app)
    assert len(charts) == 4
    table = app.dataframe[-1].value
    expected_times = [datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC) for value in timestamps]
    assert len(table) == len(timestamps)
    assert set(table["id"]) == set(range(1, 7))
    assert list(table["timestamp"]) == expected_times
    assert str(table["timestamp"].dt.tz) == "UTC"
    for chart in charts:
        plotted = chart_dataframe(chart)
        assert len(plotted) == len(timestamps)
        assert list(plotted["timestamp"]) == expected_times
        assert str(plotted["timestamp"].dt.tz) == "UTC"
        field = json.loads(chart.proto.spec)["encoding"]["y"]["field"]
        assert list(plotted[field]) == list(table[field])
        assert list(plotted["run_id"]) == list(table["run_id"])


def test_dashboard_chart_time_scales_explicitly_use_utc(monkeypatch):
    api_responses(monkeypatch)
    app = AppTest.from_file(str(ENTRYPOINT), default_timeout=20).run()
    assert not app.exception
    assert not app.error
    charts = chart_elements(app)
    assert len(charts) == 4
    fields = set()
    for chart in charts:
        encoding = json.loads(chart.proto.spec)["encoding"]
        assert encoding["x"]["field"] == "timestamp"
        assert encoding["x"]["type"] == "temporal"
        assert encoding["x"].get("scale", {}).get("type") == "utc"
        assert encoding["color"]["field"] == "run_id"
        assert encoding["color"]["type"] == "nominal"
        fields.add(encoding["y"]["field"])
    assert fields == {"battery_pct", "temperature_c", "speed_m_s", "obstacle_distance_m"}


@pytest.mark.parametrize("runs", [1, 2])
@pytest.mark.parametrize("span_days", [0, 4])
def test_chart_axes_distinguish_dates_and_preserve_utc_for_one_or_multiple_runs(
    monkeypatch, runs, span_days
):
    start = datetime(2026, 10, 26, 10, 13, 41, tzinfo=UTC)
    end = start + timedelta(days=span_days, seconds=59)
    history = [
        {"timestamp": value.isoformat(), "run_id": f"run-{index % runs}"}
        for index, value in enumerate([start, end])
    ]
    api_responses(monkeypatch, history_overrides=history)
    app = AppTest.from_file(str(ENTRYPOINT), default_timeout=20).run()
    assert not app.exception
    assert not app.error
    assert len(chart_elements(app)) == 4
    for chart in chart_elements(app):
        encoding = json.loads(chart.proto.spec)["encoding"]
        assert encoding["x"]["scale"]["type"] == "utc"
        # Daily UTC ticks all have the same time; include their date as well.
        assert encoding["x"]["axis"]["format"] == (
            "%d/%m %H:%M:%S" if span_days else "%H:%M:%S"
        )
        plotted = chart_dataframe(chart)
        assert list(plotted["timestamp"]) == [start, end]
        assert plotted["run_id"].nunique() == runs
        assert all(label.endswith("UTC") for label in plotted["date_label"])


def test_dashboard_warns_about_readings_dated_in_the_future(monkeypatch):
    future = (datetime.now(UTC) + timedelta(minutes=2)).isoformat()
    api_responses(monkeypatch, latest_overrides={"timestamp": future})
    app = AppTest.from_file(str(ENTRYPOINT), default_timeout=20).run()
    assert not app.exception
    assert any("futur" in warning.value.lower() and "reloj" in warning.value.lower() for warning in app.warning)
    assert not any("Datos sin actualizar" in warning.value for warning in app.warning)


def test_dashboard_distinguishes_logical_time_from_utc_measurement_date(monkeypatch):
    api_responses(monkeypatch, latest_overrides={"sequence": 9})
    app = AppTest.from_file(str(ENTRYPOINT), default_timeout=20).run()
    assert not app.exception
    assert any("Paso 9" in caption.value and "t_sim=8 s" in caption.value for caption in app.caption)
    assert any("Última lectura:" in caption.value and "UTC" in caption.value for caption in app.caption)


def test_dashboard_keeps_warning_when_latest_reading_is_stale(monkeypatch):
    old = (datetime.now(UTC) - timedelta(seconds=30)).isoformat()
    api_responses(monkeypatch, latest_overrides={"timestamp": old})
    app = AppTest.from_file(str(ENTRYPOINT), default_timeout=20).run()
    assert not app.exception
    assert any("Datos sin actualizar" in warning.value for warning in app.warning)
    assert not any("futur" in warning.value.lower() for warning in app.warning)
