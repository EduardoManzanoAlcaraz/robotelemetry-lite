"""Real local integration check, isolated from the development database.

Run from the installed project: python scripts/smoke_check.py
The Streamlit HTTP health check proves server startup. AppTest separately executes
the dashboard against the real API and checks four metrics and four charts.
"""

import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

import httpx


ROOT = Path(__file__).resolve().parents[1]


def free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def stop(process: subprocess.Popen) -> None:
    if process.poll() is None:
        if os.name == "nt":
            # El lanzador de un venv en Windows puede tener un intérprete hijo.
            # Limitar la limpieza al árbol del PID que creó este script.
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        else:
            process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def wait_ready(process: subprocess.Popen, url: str) -> None:
    deadline = time.monotonic() + 20
    with httpx.Client(timeout=0.5) as client:
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f"Server exited with code {process.returncode}: {url}")
            try:
                if client.get(url).status_code == 200:
                    return
            except httpx.RequestError:
                pass
            time.sleep(0.1)
    raise TimeoutError(f"Server did not become ready in 20 seconds: {url}")


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> dict:
    processes, logs = [], []
    succeeded = False
    with tempfile.TemporaryDirectory(prefix="robotelemetry-smoke-") as temporary:
        workspace = Path(temporary)
        environment = {
            **os.environ,
            "ROBO_DB_PATH": str(workspace / "telemetry.sqlite3"),
            "ROBO_BATTERY_LOW_PCT": "20",
            "ROBO_TEMPERATURE_HIGH_C": "65",
            "ROBO_OBSTACLE_NEAR_M": "0.5",
            "PYTHONUTF8": "1",
        }

        def launch(name: str, arguments: list[str]) -> subprocess.Popen:
            log = (workspace / f"{name}.log").open("w", encoding="utf-8")
            logs.append(log)
            process = subprocess.Popen(
                [sys.executable, *arguments], cwd=ROOT, env=environment,
                stdout=log, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            processes.append(process)
            return process

        try:
            api_port = free_port()
            api_url = f"http://127.0.0.1:{api_port}"
            api_args = ["-m", "uvicorn", "robotelemetry.api:app", "--host", "127.0.0.1", "--port", str(api_port)]
            api = launch("api-first", api_args)
            wait_ready(api, f"{api_url}/health")
            with (workspace / "simulator.log").open("w", encoding="utf-8") as log:
                subprocess.run(
                    [sys.executable, "-m", "robotelemetry.simulator", "--scenario", "demo", "--samples", "80", "--interval", "0"],
                    cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT,
                    check=True, timeout=30,
                )
            with httpx.Client(base_url=api_url, timeout=3) as client:
                health = client.get("/health").raise_for_status().json()
                kinds = sorted({row["kind"] for row in client.get("/alerts", params={"limit": 1000}).raise_for_status().json()})
            check(health["measurements"] == 80, f"Expected 80 measurements: {health}")
            check(kinds == ["high_temperature", "low_battery", "near_obstacle"], f"Missing anomaly types: {kinds}")

            stop(api)
            api = launch("api-restarted", api_args)
            wait_ready(api, f"{api_url}/health")
            persisted = httpx.get(f"{api_url}/health", timeout=3).raise_for_status().json()
            check(persisted == health, f"Counts changed after API restart: {persisted}")

            environment["ROBO_API_URL"] = api_url
            streamlit_url = f"http://127.0.0.1:{free_port()}"
            streamlit = launch("streamlit", [
                "-m", "streamlit", "run", "dashboard.py", "--server.address", "127.0.0.1",
                "--server.port", streamlit_url.rsplit(":", 1)[1], "--server.headless", "true",
                "--browser.gatherUsageStats", "false",
            ])
            wait_ready(streamlit, f"{streamlit_url}/_stcore/health")
            from streamlit.testing.v1 import AppTest

            previous_url = os.environ.get("ROBO_API_URL")
            try:
                os.environ["ROBO_API_URL"] = api_url
                app = AppTest.from_file(str(ROOT / "dashboard.py")).run(timeout=20)
                check(not app.exception, f"Dashboard render failed: {app.exception}")
                check(not app.error, f"Dashboard reported an error: {app.error}")
                check(len(app.metric) == 4, f"Expected four dashboard metrics: {len(app.metric)}")
                charts = list(app.get("vega_lite_chart")) or list(app.get("arrow_vega_lite_chart"))
                check(len(charts) == 4, f"Expected four dashboard charts: {len(charts)}")
            finally:
                if previous_url is None:
                    os.environ.pop("ROBO_API_URL", None)
                else:
                    os.environ["ROBO_API_URL"] = previous_url
            result = {
                "measurements": health["measurements"], "alerts": health["alerts"], "kinds": kinds,
                "persisted_after_restart": persisted == health, "dashboard_metrics": len(app.metric),
                "dashboard_charts": len(charts),
                "streamlit_health": "HTTP 200 (server startup only; rendering checked separately with AppTest)",
            }
            succeeded = True
        finally:
            for process in reversed(processes):
                stop(process)
            for log in logs:
                log.close()
            if not succeeded:
                for path in sorted(workspace.glob("*.log")):
                    print(f"\n{path.name}:\n{path.read_text(encoding='utf-8', errors='replace')}", file=sys.stderr)
    return result


if __name__ == "__main__":
    print(json.dumps(main(), ensure_ascii=False, indent=2))
