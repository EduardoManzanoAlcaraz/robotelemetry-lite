# Instrucciones para agentes — robotelemetry-lite

Se aplica a todo el repositorio. Codex debe leer este archivo; con Claude u otra herramienta, incluirlo explícitamente si no lo carga automáticamente.

## Antes de cambiar archivos

Lee `README.md`, `ARCHITECTURE.md`, `PROJECT_STATUS.md` y `docs/VERIFICACION.md`; después los módulos y pruebas del área afectada.

Comprueba `git status --short` y la rama. Conserva cambios ajenos y lee las instrucciones de cualquier subdirectorio afectado. Contrasta los documentos con el código: un plan o resultado antiguo no demuestra una función actual. Limita cada cambio al encargo recibido.

## Reglas del proyecto

- Mantén la separación simulador → servicio/alertas → SQLite → API → dashboard; no inicies procesos al importar la API.
- Conserva validación Pydantic, UTC, unidades y atomicidad de medición más alertas; no alteres un esquema existente sin plan de migración.
- No conectes tests o demos con la base del usuario: usa `tmp_path` y una ruta de demo nueva. Nunca borres una base para que un comando pase.
- En pruebas de API inyecta `Settings` mediante `create_app`; no dependas de variables de entorno de otra terminal.
- Mantén la identificación de datos simulados y las diferencias entre alerta, incidente y control robótico. AWS, ABB y FANUC son ideas futuras; no añadas servicios o credenciales por iniciativa propia.
- No cambies el tag/release v1.0.0 ni reutilices sus cifras para describir main.

## Validación y entrega

Instala con el Python 3.12+ de `.venv`: `python -m pip install -e '.[dev]'`. Para lógica, almacenamiento, API o interfaz: `python -m pytest --cov=robotelemetry --cov-report=term-missing`; para integración de procesos, `python scripts/smoke_check.py`; verifica además `python -m pip check`. Usa la ruta explícita de `.venv` del README en Windows. Inspecciona visualmente cambios de interfaz y CSV; no declares esa revisión cubierta por AppTest.

En cambios solo de documentación, comprueba rutas, enlaces relativos y comandos contra los archivos reales; no hace falta repetir toda la suite si no cambia el comportamiento. No inventes pruebas ausentes ni marques como aprobado un comando que no ejecutaste. Informa comando, resultado y alcance pendiente.

Revisa el diff antes de hacer commit. No incluyas dependencias instaladas, archivos generados, datos personales, credenciales, cookies, tokens ni archivos de entorno privados. Mantén los documentos útiles existentes y actualiza el estado si cambia una decisión o una limitación. Los commits deben explicar el resultado y su validación; separa documentación y cambios funcionales.
