# Estado de RoboTelemetry Lite

Revisión del 2026-11-19 sobre `faa90cf1ae01f525abf75afb7d45847a62d1eb09`. Las observaciones del código se distinguen de las pruebas ejecutadas y de los informes históricos. Esta revisión solo modifica documentación.

## Comprobado en esta revisión

Windows, Python 3.14.7. Entorno virtual nuevo con `pip install -e '.[dev]'`; las versiones se resuelven dentro de rangos, no hay lockfile Python.

| Comando desde la raíz, usando el Python de `.venv` | Resultado |
| --- | --- |
| `python -m pip check` | Sin requisitos incompatibles |
| `python -m pytest --cov=robotelemetry --cov-report=term-missing` | 187 aprobadas; cobertura redondeada 99 % |
| `python scripts/smoke_check.py` | Salida 0; 80 lecturas, 34 alertas; persistencia y dashboard AppTest |

La versión de paquete es 1.0.0. El README y `docs/VERIFICACION.md` distinguen el tag histórico v1.0.0 (161 pruebas) del main posterior (187). No se ha vuelto a ejecutar o consultar CI en esta revisión. AppTest y pruebas de navegador no son intercambiables.

## Límites y siguientes pasos propuestos

1. Completar la revisión visual de ejes de varios días, controles y descarga CSV en navegador; registrar tamaño, resultado y fecha.
2. Si se necesita reproducibilidad exacta del entorno, evaluar un bloqueo de dependencias sin cambiar los rangos a ciegas.
3. Antes de exposición pública: diseñar autenticación, retención, backups/restauración y migraciones, con pruebas propias. No se han probado carga ni operación de producción.
4. Definir por separado el alcance de RoboFleet Cloud antes de añadir AWS. Esta revisión no encontró un repositorio independiente con ese nombre entre los accesibles; eso no demuestra que no exista en otro lugar. No hay ingestión cloud implementada aquí.

Estas prioridades son propuestas de mantenimiento, no compromisos ni funciones terminadas. Se conservan `CHANGELOG.md`, `docs/DEMO.md`, `docs/PORTFOLIO.md` y el historial de verificación.
