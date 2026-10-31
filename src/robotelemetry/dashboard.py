"""Read-only Streamlit client; all telemetry comes from the REST API."""

from dataclasses import dataclass
from datetime import UTC, datetime
from html import escape
import os
from typing import Any

import httpx
import pandas as pd
import streamlit as st

from robotelemetry.dashboard_styles import STYLES


class DashboardError(Exception):
    """A recoverable API error that can be shown without a traceback."""


@dataclass(frozen=True)
class Snapshot:
    health: dict[str, Any]
    config: dict[str, Any]
    latest: dict[str, Any] | None
    history: list[dict[str, Any]]
    alerts: list[dict[str, Any]]


def fetch_snapshot(base_url: str, limit: int) -> Snapshot:
    """Fetch a bounded view without caching live data or reading the database."""
    try:
        with httpx.Client(base_url=base_url, timeout=3.0) as client:
            health = client.get("/health")
            health.raise_for_status()
            config = client.get("/config")
            config.raise_for_status()
            latest = client.get("/telemetry/latest")
            if latest.status_code != 404:
                latest.raise_for_status()
            history = client.get("/telemetry/history", params={"limit": limit})
            history.raise_for_status()
            alerts = client.get("/alerts", params={"limit": 30})
            alerts.raise_for_status()
            snapshot = Snapshot(
                health=health.json(),
                config=config.json(),
                latest=None if latest.status_code == 404 else latest.json(),
                history=history.json(),
                alerts=alerts.json(),
            )
            if not (
                isinstance(snapshot.health, dict)
                and isinstance(snapshot.config, dict)
                and (snapshot.latest is None or isinstance(snapshot.latest, dict))
                and isinstance(snapshot.history, list)
                and isinstance(snapshot.alerts, list)
            ):
                raise ValueError("Unexpected response structure")
            return snapshot
    except httpx.HTTPStatusError as exc:
        raise DashboardError(
            f"La API ha respondido con HTTP {exc.response.status_code}. "
            "Comprueba su terminal y vuelve a actualizar."
        ) from exc
    except (httpx.RequestError, httpx.InvalidURL) as exc:
        raise DashboardError(
            "No se puede conectar con la API. Inicia FastAPI y comprueba ROBO_API_URL."
        ) from exc
    except (ValueError, TypeError) as exc:
        raise DashboardError("La API ha devuelto una respuesta no válida.") from exc


def _utc_time(value: str) -> datetime:
    timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if timestamp.tzinfo is None:
        raise ValueError("The API must supply an aware timestamp")
    return timestamp.astimezone(UTC)


def _pill(label: str, tone: str = "neutral") -> str:
    return f'<span class="rt-pill rt-pill--{tone}">{escape(label)}</span>'


def _render_header(snapshot: Snapshot | None) -> None:
    title, connection = st.columns([3, 1], gap="large", vertical_alignment="center")
    with title:
        st.markdown('<div class="rt-eyebrow">CENTRO DE TELEMETRÍA</div>', unsafe_allow_html=True)
        st.title("RoboTelemetry Lite")
        st.markdown("Estado, tendencias y alertas de tu robot en una sola vista.")
    with connection:
        if snapshot is None:
            st.error("API no disponible")
        else:
            st.success("API conectada")
            st.caption(f"{snapshot.health['measurements']:,} lecturas · {snapshot.health['alerts']:,} incidencias")
    st.info("**SENSORES SIMULADOS** · Datos generados por software, sin conexión a un robot físico.")


def _render_current(latest: dict[str, Any], config: dict[str, Any]) -> None:
    st.subheader("Estado actual")
    battery_low = latest["battery_pct"] <= config["battery_low_pct"]
    temperature_high = latest["temperature_c"] >= config["temperature_high_c"]
    obstacle_near = latest["obstacle_distance_m"] <= config["obstacle_near_m"]
    cards = (
        ("Batería", "battery_pct", f"{latest['battery_pct']:.1f} %",
         "Batería baja" if battery_low else "Nivel estable", "warning" if battery_low else "ok"),
        ("Temperatura", "temperature_c", f"{latest['temperature_c']:.1f} °C",
         "Temperatura elevada" if temperature_high else "Dentro del umbral", "critical" if temperature_high else "ok"),
        ("Velocidad", "speed_m_s", f"{latest['speed_m_s']:.2f} m/s",
         "En movimiento" if latest["speed_m_s"] > 0 else "En reposo", "info"),
        ("Obstáculo más próximo", "obstacle_distance_m", f"{latest['obstacle_distance_m']:.2f} m",
         "Obstáculo próximo" if obstacle_near else "Distancia segura", "critical" if obstacle_near else "ok"),
    )
    for column, (label, field, value, state, tone) in zip(st.columns(4, gap="small"), cards, strict=True):
        with column.container(border=True, key=f"metric-{field}"):
            st.metric(label, value)
            st.markdown(_pill(state, tone), unsafe_allow_html=True)

    timestamp = _utc_time(latest["timestamp"])
    age_seconds = (datetime.now(UTC) - timestamp).total_seconds()
    st.caption(f"Última lectura: {timestamp:%d/%m/%Y %H:%M:%S} UTC · Escenario: {latest['scenario']}")
    if age_seconds < 0:
        st.warning(
            f"La última lectura está fechada en el futuro ({-age_seconds:.0f} s). "
            "Comprueba el reloj del sistema y la ejecución que generó estos datos."
        )
    elif age_seconds > 5:
        st.warning(f"Datos sin actualizar desde hace {age_seconds:.0f} s. El simulador puede estar detenido.")
    with st.expander("Detalles de la lectura y umbrales"):
        st.caption(
            f"Paso {latest['sequence']} · t_sim={latest['sequence'] - 1} s · "
            f"Semilla {latest['seed']} · Lectura #{latest['id']} · Ejecución {latest['run_id']}"
        )
        st.caption(
            f"Batería ≤ {config['battery_low_pct']:g} % · Temperatura ≥ {config['temperature_high_c']:g} °C · "
            f"Obstáculo ≤ {config['obstacle_near_m']:g} m"
        )


def _render_active_alerts(latest: dict[str, Any] | None, config: dict[str, Any]) -> None:
    st.subheader("Alertas en la última lectura")
    if latest is None:
        st.info("Las alertas actuales aparecerán cuando llegue la primera lectura.")
        return
    active = []
    if latest["battery_pct"] <= config["battery_low_pct"]:
        active.append(("warning", "Batería baja", latest["battery_pct"], config["battery_low_pct"], "%", "≤"))
    if latest["temperature_c"] >= config["temperature_high_c"]:
        active.append(("critical", "Temperatura elevada", latest["temperature_c"], config["temperature_high_c"], "°C", "≥"))
    if latest["obstacle_distance_m"] <= config["obstacle_near_m"]:
        active.append(("critical", "Obstáculo próximo", latest["obstacle_distance_m"], config["obstacle_near_m"], "m", "≤"))
    if not active:
        st.success("Sin alertas en la última lectura.")
        return
    for column, (severity, label, value, threshold, unit, operator) in zip(st.columns(len(active)), active, strict=True):
        with column:
            message = f"**{label}** · {value:g} {unit}\n\nUmbral {operator} {threshold:g} {unit}"
            if severity == "critical":
                st.error(message)
            else:
                st.warning(message)


def _render_history(history: list[dict[str, Any]]) -> pd.DataFrame:
    st.subheader("Gráficas históricas")
    if not history:
        st.info("Todavía no hay mediciones en el histórico.")
        return pd.DataFrame()
    frame = pd.DataFrame(history)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], format="ISO8601", utc=True)
    frame = frame.sort_values(["timestamp", "id"])
    plotted_frame = frame.assign(date_label=frame["timestamp"].dt.strftime("%d/%m/%Y %H:%M:%S UTC"))
    # En ventanas de varios días los ticks UTC pueden caer todos a medianoche.
    # Incluir la fecha distingue esos ticks sin alterar datos ni zonas horarias.
    spans_days = (frame["timestamp"].iloc[-1] - frame["timestamp"].iloc[0]).total_seconds() >= 86400
    time_format = "%d/%m %H:%M:%S" if spans_days else "%H:%M:%S"
    # Las filas persistidas son inmutables. Cambiar el nombre de la vista al
    # cambiar su ventana evita conservar datasets/escalas del render anterior.
    revision = f"{frame['id'].iloc[0]}_{frame['id'].iloc[-1]}_{len(frame)}"
    st.caption(f"{len(frame)} lecturas visibles · Hora UTC · Una serie por ejecución")
    charts = (
        ("Batería", "battery_pct", "%", 0, 100),
        ("Temperatura", "temperature_c", "°C", None, None),
        ("Velocidad", "speed_m_s", "m/s", 0, None),
        ("Distancia a obstáculos", "obstacle_distance_m", "m", 0, None),
    )
    for row in (charts[:2], charts[2:]):
        for column, (title, field, unit, minimum, maximum) in zip(st.columns(2, gap="medium"), row, strict=True):
            with column.container(border=True):
                st.markdown(f"**{title}**")
                scale = {"zero": minimum == 0}
                if maximum is not None:
                    scale["domain"] = [minimum, maximum]
                st.vega_lite_chart(plotted_frame, spec={
                    "name": f"history_{field}_{revision}",
                    "width": "container", "height": 220,
                    "mark": {"type": "line", "point": {"filled": True, "size": 18}, "strokeWidth": 2.3},
                    "encoding": {
                        "x": {"field": "timestamp", "type": "temporal", "title": "Fecha y hora (UTC)" if spans_days else "Hora (UTC)",
                              "scale": {"type": "utc"}, "axis": {"format": time_format, "labelOverlap": True, "tickCount": 5}},
                        "y": {"field": field, "type": "quantitative", "title": unit, "scale": scale,
                              "axis": {"gridDash": [3, 3], "tickCount": 4}},
                        "color": {"field": "run_id", "type": "nominal", "title": "Ejecución",
                                  "scale": {"scheme": "tableau10"}, "legend": {"orient": "bottom", "labelLimit": 90}},
                        "tooltip": [
                            {"field": "date_label", "type": "nominal", "title": "Fecha"},
                            {"field": field, "type": "quantitative", "title": f"{title} ({unit})", "format": ".3~f"},
                            {"field": "run_id", "type": "nominal", "title": "Ejecución"},
                        ],
                    },
                    "config": {"view": {"stroke": None}, "axis": {"domain": False, "labelFontSize": 11, "titleFontSize": 11}},
                })
    return frame


def _render_alerts(alerts: list[dict[str, Any]]) -> None:
    st.subheader("Incidencias históricas")
    st.caption("Últimas 30 ocurrencias guardadas. Un registro histórico no implica una alerta actual.")
    if not alerts:
        st.info("No hay incidencias registradas.")
        return
    units = {"low_battery": "%", "high_temperature": "°C", "near_obstacle": "m"}
    rows = []
    for alert in alerts[:3]:
        timestamp = _utc_time(alert["created_at"])
        critical = alert["severity"] == "critical"
        unit = units.get(alert["kind"], "")
        rows.append(
            '<div class="rt-incident"><div>'
            f'<span class="rt-incident-title">{escape(alert["message"])}</span>'
            + _pill("Crítica" if critical else "Atención", "critical" if critical else "warning")
            + f'<div class="rt-incident-meta">{timestamp:%d/%m/%Y %H:%M:%S} UTC · Lectura #{escape(str(alert["measurement_id"]))}</div>'
            f'</div><div class="rt-incident-value">{alert["value"]:g} {unit}'
            f'<small>Umbral {alert["threshold"]:g} {unit}</small></div></div>'
        )
    st.markdown('<div class="rt-incident-list">' + "".join(rows) + "</div>", unsafe_allow_html=True)
    with st.expander(f"Ver todas las incidencias consultadas ({len(alerts)})"):
        frame = pd.DataFrame(alerts)
        st.dataframe(frame, hide_index=True, column_config={
            "created_at": "Fecha UTC", "message": "Incidencia", "severity": "Severidad",
            "value": "Valor", "threshold": "Umbral", "measurement_id": "Lectura",
            "kind": "Regla", "id": "ID",
        })


def _render_data(frame: pd.DataFrame) -> None:
    st.subheader("Datos y exportación")
    if frame.empty:
        st.info("La tabla y el CSV estarán disponibles cuando haya mediciones.")
        return
    summary, export = st.columns([3, 1], vertical_alignment="center")
    summary.caption(f"{len(frame)} mediciones · El CSV contiene las mismas lecturas que las gráficas.")
    with export:
        st.download_button("Descargar CSV", data=frame.to_csv(index=False).encode("utf-8-sig"),
                           file_name="robotelemetry-historico.csv", mime="text/csv")
    with st.expander("Explorar tabla de mediciones", expanded=False):
        st.dataframe(frame, hide_index=True, column_order=[
            "timestamp", "battery_pct", "temperature_c", "speed_m_s", "obstacle_distance_m",
            "scenario", "run_id", "sequence", "seed", "id",
        ], column_config={
            "timestamp": st.column_config.DatetimeColumn("Fecha UTC", format="DD/MM/YYYY HH:mm:ss"),
            "battery_pct": st.column_config.NumberColumn("Batería (%)", format="%.1f"),
            "temperature_c": st.column_config.NumberColumn("Temperatura (°C)", format="%.1f"),
            "speed_m_s": st.column_config.NumberColumn("Velocidad (m/s)", format="%.2f"),
            "obstacle_distance_m": st.column_config.NumberColumn("Obstáculo (m)", format="%.2f"),
            "scenario": "Escenario", "run_id": "Ejecución", "sequence": "Paso", "seed": "Semilla", "id": "ID",
        })


def main() -> None:
    st.set_page_config(page_title="RoboTelemetry Lite", page_icon="🤖", layout="wide")
    st.markdown(STYLES, unsafe_allow_html=True)
    base_url = os.getenv("ROBO_API_URL", "http://127.0.0.1:8000").rstrip("/")
    with st.sidebar:
        st.markdown('<div class="rt-brand"><span class="rt-brand-mark">RT</span>RoboTelemetry</div>', unsafe_allow_html=True)
        st.header("Tu vista")
        auto_refresh = st.toggle("Actualización automática (2 s)", value=True)
        limit = st.select_slider("Lecturas en el histórico", options=[60, 180, 300, 600, 1000], value=180)
        st.button("Actualizar ahora", help="Consulta de nuevo la API.")
        st.caption("La pausa afecta a esta vista. El simulador sigue funcionando por separado.")
        with st.expander("Conexión y ayuda"):
            st.caption(f"API: {base_url}")
            st.caption("Los umbrales se muestran en los detalles de la última lectura.")
        st.markdown('<div class="rt-footer">SIMULACIÓN LOCAL<br>Sin hardware conectado</div>', unsafe_allow_html=True)

    @st.fragment(run_every="2s" if auto_refresh else None)
    def live_panel() -> None:
        try:
            snapshot = fetch_snapshot(base_url, limit)
        except DashboardError as exc:
            _render_header(None)
            st.error(str(exc))
            return
        try:
            _render_header(snapshot)
            if snapshot.latest is None:
                st.subheader("Estado actual")
                st.info("Aún no hay telemetría. Inicia el simulador en otra terminal.")
                st.code(r".\.venv\Scripts\python.exe -m robotelemetry.simulator --scenario demo", language="powershell")
            else:
                _render_current(snapshot.latest, snapshot.config)
            _render_active_alerts(snapshot.latest, snapshot.config)
            frame = _render_history(snapshot.history)
            _render_alerts(snapshot.alerts)
            _render_data(frame)
        except (KeyError, TypeError, ValueError):
            st.error("No se puede mostrar la respuesta de la API: su formato no es válido.")

    live_panel()


if __name__ == "__main__":
    main()
