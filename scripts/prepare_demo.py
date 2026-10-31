"""Crear datos simulados en una base nueva; nunca reutilizar ni borrar un archivo."""

import argparse
import json
from pathlib import Path
import sqlite3

from robotelemetry.config import AlertThresholds
from robotelemetry.simulator import run_simulation
from robotelemetry.storage import SQLiteStore


def prepare_demo(output: Path, *, seed: int = 42) -> dict[str, object]:
    """Generar 60 lecturas normales y 80 de anomalías con umbrales predeterminados.

    Los valores son reproducibles para la misma semilla; las fechas UTC y los
    identificadores de ejecución corresponden a cada generación. Los dos lotes
    representan historial sintético que termina al comenzar cada ejecución.
    """
    if not -(2**63) <= seed <= 2**63 - 1:
        raise ValueError("seed debe ser un entero de 64 bits con signo.")
    target = Path(output).resolve()
    for path in (target, *(Path(f"{target}{suffix}") for suffix in ("-wal", "-shm", "-journal"))):
        if path.exists():
            raise FileExistsError(f"La demo requiere una ruta nueva; ya existe: {path}")
    target.parent.mkdir(parents=True, exist_ok=True)
    # Creación exclusiva: también protege frente a otro proceso que intente
    # reservar el mismo nombre tras la comprobación anterior.
    with target.open("xb"):
        pass
    store = SQLiteStore(target)
    thresholds = AlertThresholds()
    run_simulation(store, thresholds, seed=seed, scenario="normal", samples=60, interval=0)
    run_simulation(store, thresholds, seed=seed, scenario="demo", samples=80, interval=0)
    return {"database": str(target), "seed": seed, "runs": 2,
            **store.counts(), "thresholds": thresholds.model_dump()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True,
                        help="Archivo SQLite NUEVO (obligatorio); una ruta relativa parte del directorio actual.")
    parser.add_argument("--seed", type=int, default=42, help="Semilla de ambos escenarios (42).")
    args = parser.parse_args()
    try:
        result = prepare_demo(args.output, seed=args.seed)
    except (ValueError, OSError, sqlite3.Error) as exc:
        parser.exit(1, f"No se pudo preparar la demo: {exc}\nNo se ha borrado ningún archivo. Usa una ruta nueva.\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
