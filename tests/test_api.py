import sqlite3
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from robotelemetry.api import create_app
from robotelemetry.config import AlertThresholds, Settings
from robotelemetry.service import TelemetryService


@pytest.fixture
def client(tmp_path):
    app = create_app(Settings(db_path=tmp_path / "api.sqlite3"))
    with TestClient(app) as test_client:
        yield test_client


def test_empty_api_has_healthy_database_and_explicit_no_data_response(client):
    assert client.get("/health").json() == {
        "status": "ok", "measurements": 0, "alerts": 0
    }
    response = client.get("/telemetry/latest")
    assert response.status_code == 404
    assert response.json()["detail"]
    assert client.get("/telemetry/history").json() == []
    assert client.get("/alerts").json() == []


def test_api_exposes_configured_thresholds(tmp_path):
    thresholds = AlertThresholds(
        battery_low_pct=30, temperature_high_c=70, obstacle_near_m=0.8
    )
    app = create_app(Settings(db_path=tmp_path / "config.sqlite3", thresholds=thresholds))
    with TestClient(app) as client:
        response = client.get("/config")
        assert response.status_code == 200
        assert response.json() == thresholds.model_dump()


def test_stored_sample_flows_through_latest_history_and_alert_endpoints(
    client, sample_factory
):
    sample = sample_factory(battery_pct=5)
    stored = TelemetryService(client.app.state.store, AlertThresholds()).record(sample)
    latest = client.get("/telemetry/latest")
    assert latest.status_code == 200
    assert latest.json()["id"] == stored.id
    assert latest.json()["battery_pct"] == 5
    assert latest.json()["run_id"] == "test-run"
    assert latest.json()["timestamp"].endswith("Z") or latest.json()["timestamp"].endswith("+00:00")
    assert client.get("/telemetry/history").json() == [latest.json()]
    alerts = client.get("/alerts").json()
    assert len(alerts) == 1
    assert alerts[0]["measurement_id"] == stored.id
    assert alerts[0]["kind"] == "low_battery"
    assert client.get("/health").json()["measurements"] == 1


@pytest.mark.parametrize(
    "path",
    [
        "/telemetry/history?limit=0",
        "/telemetry/history?limit=1001",
        "/telemetry/history?offset=-1",
        "/telemetry/history?limit=abc",
        "/telemetry/history?since=not-a-date",
        "/telemetry/history?since=2026-01-01T12:00:00",
        "/telemetry/history?until=2026-01-01T12:00:00",
        "/telemetry/history?since=2026-01-02T00:00:00Z&until=2026-01-01T00:00:00Z",
        "/alerts?limit=0",
        "/alerts?limit=1001",
        "/alerts?offset=-1",
        "/alerts?kind=unknown",
    ],
)
def test_invalid_queries_return_validation_errors(client, path):
    response = client.get(path)
    assert response.status_code == 422
    assert "detail" in response.json()


@pytest.mark.parametrize(
    ("endpoint", "store_method"),
    [("/telemetry/history", "history"), ("/alerts", "alerts")],
)
@pytest.mark.parametrize("offset", [-1, 2**63, 10**100])
def test_invalid_offsets_are_rejected_before_storage_is_called(
    client, monkeypatch, endpoint, store_method, offset
):
    def unexpected_storage_call(**kwargs):
        raise AssertionError("Invalid query offset reached the storage layer")

    monkeypatch.setattr(client.app.state.store, store_method, unexpected_storage_call)
    response = client.get(endpoint, params={"offset": str(offset)})
    assert response.status_code == 422
    assert "detail" in response.json()


@pytest.mark.parametrize("endpoint", ["/telemetry/history", "/alerts"])
def test_oversized_offset_returns_validation_error_instead_of_server_error(
    tmp_path, endpoint
):
    app = create_app(Settings(db_path=tmp_path / "offset.sqlite3"))
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(endpoint, params={"offset": str(2**63)})
    assert response.status_code == 422


@pytest.mark.parametrize("endpoint", ["/telemetry/history", "/alerts"])
def test_largest_sqlite_offset_is_accepted(client, endpoint):
    response = client.get(endpoint, params={"offset": str(2**63 - 1)})
    assert response.status_code == 200
    assert response.json() == []


def test_api_history_filters_normalize_timezone_and_include_boundaries(
    client, sample_factory
):
    start = sample_factory().timestamp
    service = TelemetryService(client.app.state.store, AlertThresholds())
    for index in range(5):
        service.record(
            sample_factory(sequence=index + 1, timestamp=start + timedelta(seconds=index))
        )
    response = client.get(
        "/telemetry/history",
        params={
            "since": "2026-01-01T01:00:01+01:00",
            "until": "2026-01-01T00:00:03Z",
            "limit": 2,
            "offset": 1,
        },
    )
    assert response.status_code == 200
    assert [sample["sequence"] for sample in response.json()] == [3, 2]


@pytest.mark.parametrize("parameter", ["since", "until"])
@pytest.mark.parametrize("timestamp", [
    "0001-01-01T00:00:00+01:00",
    "9999-12-31T23:59:59.999999-01:00",
])
def test_history_rejects_dates_outside_utc_range_instead_of_server_error(
    tmp_path, parameter, timestamp
):
    app = create_app(Settings(db_path=tmp_path / "extreme-date.sqlite3"))
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/telemetry/history", params={parameter: timestamp})
    assert response.status_code == 422
    assert "detail" in response.json()


@pytest.mark.parametrize(("parameter", "timestamp"), [
    ("since", "0001-01-01T00:00:00Z"),
    ("since", "0001-01-01T01:00:00+01:00"),
    ("until", "9999-12-31T23:59:59.999999Z"),
    ("until", "9999-12-31T22:59:59.999999-01:00"),
])
def test_history_accepts_representable_utc_boundaries(
    client, sample_factory, parameter, timestamp
):
    stored = TelemetryService(client.app.state.store, AlertThresholds()).record(sample_factory())
    response = client.get("/telemetry/history", params={parameter: timestamp})
    assert response.status_code == 200
    assert [sample["id"] for sample in response.json()] == [stored.id]


def test_api_alert_filter_returns_only_requested_rule(client, sample_factory):
    service = TelemetryService(client.app.state.store, AlertThresholds())
    service.record(sample_factory(battery_pct=5, temperature_c=90, obstacle_distance_m=0.1))
    response = client.get("/alerts", params={"kind": "high_temperature"})
    assert response.status_code == 200
    assert [alert["kind"] for alert in response.json()] == ["high_temperature"]


def test_database_errors_return_503_without_sensitive_details(client, monkeypatch):
    def unavailable():
        raise sqlite3.OperationalError("sensitive/local/path.sqlite3: database is locked")

    monkeypatch.setattr(client.app.state.store, "latest", unavailable)
    response = client.get("/telemetry/latest")
    assert response.status_code == 503
    assert response.json() == {"detail": "Almacenamiento temporalmente no disponible."}
    assert "sensitive" not in response.text


def test_api_restart_preserves_data(tmp_path, sample_factory):
    settings = Settings(db_path=tmp_path / "restart.sqlite3")
    with TestClient(create_app(settings)) as first:
        TelemetryService(first.app.state.store, settings.thresholds).record(sample_factory())
    with TestClient(create_app(settings)) as restarted:
        assert restarted.get("/health").json()["measurements"] == 1
        assert restarted.get("/telemetry/latest").json()["sequence"] == 1


def test_openapi_documents_endpoints_and_schema(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert {"/health", "/config", "/telemetry/latest", "/telemetry/history", "/alerts"} <= paths.keys()


def test_read_only_api_rejects_unsupported_writes(client):
    assert client.post("/telemetry/latest", json={}).status_code == 405
