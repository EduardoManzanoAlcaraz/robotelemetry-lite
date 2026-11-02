# Verificación de RoboTelemetry Lite v1.0.0

Este documento distingue el estado de `main` tras ampliar las pruebas y el registro histórico de la release `v1.0.0`. El tag y la release originales no se modifican: sus 161 pruebas y 94 % corresponden a la versión publicada el 31 de octubre de 2026.

## Main: ampliación de pruebas — 2 de noviembre de 2026

Se añadieron **26 casos netos**, hasta 187, en `test_simulator.py`, `test_dashboard.py` y `test_storage.py`. No cambian el código productivo, la configuración de cobertura ni las dependencias.

Últimas ejecuciones locales antes de publicar esta ampliación:

| Entorno Windows | Resultado real | Sentencias | Ramas | Cobertura combinada |
| --- | --- | --- | --- | --- |
| Python 3.14.7 | **187 passed in 13.51s**, salida 0, sin avisos | 485/487, 99,59 % | 84/86, 97,67 % | **99,30 %** |
| Python 3.12.10 | **187 passed in 23.80s**, salida 0, sin avisos | 497/499, 99,60 % | 84/86, 97,67 % | **99,32 %** |

Pytest-cov redondea ambos totales a **99 %**. Cada intérprete conserva su propio denominador; no se mezclan ni se suman sus coberturas. En Python 3.14 se mantuvieron las mismas 487 sentencias y 86 ramas medidas que en la auditoría inicial; en ambos entornos hay **cero líneas excluidas**. La mejora viene de ejecutar comportamientos antes sin instrumentar, no de omitir código.

| Módulo | Cobertura combinada actual, redondeada | Líneas sin cubrir |
| --- | --- | --- |
| `simulator.py` | 98 % | 140 |
| `dashboard.py` | 99 % | 313 |
| `storage.py` | 100 % | Ninguna |

Las dos líneas restantes invocan `main()` bajo `if __name__ == '__main__'` y siguen incluidas en la medición. Las funciones principales se prueban mediante los puntos de entrada documentados; el smoke check ejecuta el simulador en un subproceso, cuya cobertura no se añade a pytest. No se añaden casos exclusivamente para alcanzar el 100 %; una cobertura alta no demuestra que todos los fallos o cargas posibles estén probados.

Los casos nuevos cubren:

- CLI real con `argparse`, configuración y SQLite temporal; argumentos y entorno inválidos, errores reales de base y archivos, e interrupción controlada tras cuatro escrituras confirmadas.
- Fechas sin offset, rangos invertidos y límites UTC equivalentes con microsegundos; rollback y cierre de conexiones reales, retenidas para que la recolección de basura no oculte fugas.
- JSON válido con estructura incorrecta, campos o valores inválidos y error visible sin traceback ni exportación engañosa en AppTest.
- Cuatro gráficas con una o dos ejecuciones en ventanas de 59 segundos, seis horas, justo antes de 24 horas, exactamente 24 horas y cuatro días, verificando datos Arrow y escalas UTC.

La auditoría automatizada del 2 de noviembre también comprobó API real y AppTest con ventanas de seis horas y cuatro días, filtros, tres alertas activas, controles y contenido CSV de 60/180 filas. **No fue una inspección visual de Chrome ni una descarga de CSV en el navegador.** La inspección visual de horas/días, controles y descarga sigue pendiente hasta confirmación manual del propietario; los bloqueos de Computer Use no se presentan como una comprobación visual completada.

Estas cifras son locales. El [estado remoto actual de `main`](https://github.com/EduardoManzanoAlcaraz/robotelemetry-lite/actions/workflows/tests.yml?query=branch%3Amain) debe consultarse en la ejecución del commit correspondiente. La CI histórica de 161 pruebas registrada a continuación no acredita la ampliación de 187 antes de ejecutarla.

## Registro histórico de v1.0.0

Revisión de cierre realizada el **31 de octubre de 2026**. Los apartados siguientes conservan los resultados originales. El registro de pruebas locales en Windows se obtuvo antes de la publicación. La sección [Publicación y ejecución real de GitHub Actions](#publicación-y-ejecución-real-de-github-actions) documenta la publicación posterior del código y la CI remota de aquella versión, diferenciadas de esos resultados locales.

## Resultados ejecutados

| Comprobación | Entorno | Resultado real |
| --- | --- | --- |
| Suite completa con cobertura | Python 3.14.7, entorno habitual | **161 passed in 93.73s**, salida 0, sin avisos en pytest. |
| Suite completa con cobertura | Python 3.12.10, instalación limpia | **161 passed in 198.97s**, salida 0, sin avisos en pytest. |
| Cobertura global, con ramas | Ambos entornos | **94 %**, redondeado por pytest-cov. |
| `pip check` | Ambos entornos | `No broken requirements found.`, salida 0. |
| Smoke check completo | Ambos entornos | Salida 0; 80 lecturas, 34 incidencias, persistencia tras reiniciar API, cuatro métricas y cuatro gráficas. |
| Instalación editable limpia | Python 3.12.10 | Construcción e instalación de `robotelemetry-lite==1.0.0` correctas. |
| Versión en pyproject, módulo, API y distribución | Python 3.12.10 | Todas `1.0.0`; módulo, API y distribución también contrastados en 3.14.7. |
| Workflow con actionlint 1.7.12 | Windows local | Salida 0, sin errores. No es una ejecución de GitHub Actions. |
| Construcción wheel PEP 517 | Python 3.12.10, copia aislada de fuentes | Correcta; metadatos 1.0.0 e inspección del contenido sin bases, entornos ni secretos locales. |

Los tiempos incluyen la carga de las dependencias de cada ejecución; no son una prueba de rendimiento ni una garantía de latencia. Esta tabla corresponde a Windows local; Ubuntu y la matriz remota se verificaron después mediante GitHub Actions, como se recoge más abajo.

## Instalación limpia y versiones

El lanzador `py` del equipo solo tenía registrado Python 3.14. Para comprobar 3.12 sin cambiar instalaciones globales, se descargó **CPython 3.12.10 oficial desde NuGet**, se extrajo dentro de `.audit/` y se creó un entorno virtual nuevo. Este método está documentado por [Python para entornos de compilación y CI](https://docs.python.org/3.12/using/windows.html#the-nuget-org-packages); paquete [python 3.12.10](https://www.nuget.org/packages/python/3.12.10).

Se ejecutaron creación de venv, actualización de pip, instalación editable con el extra `dev`, `pip check`, pytest con cobertura y smoke check. Se usó la ruta explícita de ese intérprete y `.audit/venv312`, en lugar de ejecutar literalmente `py -3.12` o reemplazar `.venv`. El README presupone una versión ya instalada y registrada en `py`; ofrece 3.14 como alternativa.

| Dependencia | Entorno Python 3.14.7 | Entorno limpio Python 3.12.10 |
| --- | --- | --- |
| FastAPI | 0.162.0 | 0.162.0 |
| Uvicorn | 0.54.0 | 0.54.0 |
| Pydantic | 2.14.1 | 2.14.2 |
| Streamlit | 1.66.1 | 1.66.1 |
| pandas | 3.1.0 | 3.1.0 |
| httpx | 0.28.1 | 0.28.1 |
| httpx2, extra de pruebas | 2.16.0 | 2.16.0 |
| pytest | 9.1.1 | 9.2.0 |
| pytest-cov | 7.1.0 | 7.1.0 |

El entorno limpio resolvió versiones dentro de los rangos de `pyproject.toml`. Se verificó esa resolución concreta; no existe un bloqueo completo de dependencias transitivas ni se afirma que una instalación futura resuelva versiones idénticas. La instalación habitual solo se reinstaló con `--no-deps` para actualizar los metadatos del proyecto a 1.0.0.

## Pruebas y cobertura

Comandos públicos equivalentes desde la raíz, después de instalar `.[dev]`:

```powershell
.\.venv\Scripts\python.exe -m pytest --cov=robotelemetry --cov-report=term-missing
.\.venv\Scripts\python.exe scripts\smoke_check.py
.\.venv\Scripts\python.exe -m pip check
```

Para el registro final se desactivaron caché/bytecode y se añadieron informes XML o JSON dentro de `.audit/`. La cobertura se calculó por separado para cada intérprete, sin mezclar sus datos.

| Módulo | Cobertura con ramas, redondeada, en ambos entornos |
| --- | --- |
| `__init__.py`, `alerts.py`, `api.py`, `config.py` | 100 % |
| `models.py`, `service.py`, `dashboard_styles.py` | 100 % |
| `dashboard.py` | 97 % |
| `storage.py` | 95 % |
| `simulator.py` | 81 % |
| **Total** | **94 %** |

El informe de Python 3.14 contabilizó 487 sentencias y 86 ramas: 459 sentencias y 79 ramas cubiertas. El de Python 3.12 contabilizó 499 sentencias y 86 ramas, con 28 sentencias sin cubrir y 79 ramas cubiertas. Los informes de cada intérprete conservan sus propios totales. La cobertura mide el paquete `robotelemetry`; no añade los scripts de herramientas a su denominador.

Las 161 pruebas incluyen 21 del dashboard y seis de la herramienta de demo. Quedan sin cubrir, entre otras rutas, partes del tratamiento de errores/interrupciones de la CLI y algunas respuestas inválidas de la interfaz. La cobertura no demuestra ausencia de defectos ni mide la apariencia visual.

En una primera ejecución de cierre aparecieron tres `ResourceWarning` por conexiones abiertas en las pruebas nuevas de la demo. Se añadió cierre explícito con `contextlib.closing`; ambas suites finales indicadas arriba terminaron sin esos avisos. No era una fuga en el almacenamiento de la aplicación.

## Defectos de cierre: reproducción y regresión

### Fechas extremas en filtros HTTP

Antes de corregir, ocho casos nuevos produjeron **4 failed, 4 passed in 2.69s**. Los cuatro fallos reproducían HTTP 500 al convertir a UTC `since` o `until` con `0001-01-01T00:00:00+01:00` o `9999-12-31T23:59:59.999999-01:00`.

El validador Pydantic convierte el filtro a UTC y transforma el desbordamiento en un error de validación HTTP **422**, antes de acceder a SQLite. Los límites UTC representables, incluidas expresiones equivalentes con offsets, siguen admitidos. La selección posterior de API, almacenamiento y modelos obtuvo **82 passed in 9.38s**; los ocho casos están incluidos en ambas suites finales. También se comprobaron los cuatro rechazos mediante HTTP real en el recorrido del README.

### Ejes UTC y etiquetas de medianoche

El código ya enviaba timestamps normalizados y escalas `utc`. La inspección de una ventana local de 300 o más lecturas reveló ejecuciones separadas por más de cuatro días. En ese rango, los ticks diarios pueden caer a medianoche: formatearlos solo como `%H:%M:%S` repite `00:00:00` aunque las fechas sean diferentes.

Se añadieron cuatro casos: una o dos ejecuciones, en una ventana de 59 segundos o de cuatro días. Antes del cambio: **2 failed, 2 passed in 8.58s**; fallaban los casos de varios días porque no incluían la fecha. Después, el dashboard utiliza `%d/%m %H:%M:%S` para ventanas de al menos 24 horas y conserva `%H:%M:%S` para ventanas cortas. No cambia los datos, el reloj del simulador ni la zona horaria.

La suite del dashboard posterior obtuvo **21 passed in 22.13s**. Los tests decodifican los datos Arrow de las cuatro gráficas, contrastan timestamps, valores y ejecuciones, verifican la escala UTC y el formato del eje. Se mantienen las regresiones de fechas ISO mixtas, antigüedad, datos futuros, CSV, métricas, reglas y controles.

**Límite de esta evidencia:** son pruebas de datos y especificación Streamlit, no del dibujo final del navegador. Computer Use detuvo el acceso a Chrome al no poder determinar su URL con confianza suficiente para aplicar su política. No se continuó la automatización del navegador. La reproducción visual y la validación visual final de los ejes de varios días, con una y varias ejecuciones, quedan pendientes. Las capturas de `docs/assets/` son reales del 26 de octubre, anteriores a este ajuste; no se presentan como capturas nuevas de v1.0.0.

## Flujo real y recorrido del README

El smoke check se ejecutó íntegramente en ambos entornos con este resultado y salida 0:

```json
{
  "measurements": 80,
  "alerts": 34,
  "kinds": ["high_temperature", "low_battery", "near_obstacle"],
  "persisted_after_restart": true,
  "dashboard_metrics": 4,
  "dashboard_charts": 4,
  "streamlit_health": "HTTP 200 (server startup only; rendering checked separately with AppTest)"
}
```

Uvicorn y Streamlit arrancaron como procesos reales; el simulador escribió SQLite y las consultas se realizaron por HTTP. Se reinició la API sobre la misma base temporal. AppTest ejecutó el dashboard contra esa API sin sustituir sus respuestas. Se detuvieron exclusivamente los procesos creados por la comprobación y se eliminaron sus datos temporales. Puede aparecer el aviso de `ScriptRunContext` de AppTest en modo aislado; ambos smoke checks terminaron correctamente.

Además se recorrió el flujo documentado con Python 3.14.7, sustituyendo únicamente las rutas de la demo por una carpeta temporal y los puertos por puertos libres; se añadió `--samples 3` para limitar la simulación continua del README:

1. `prepare_demo.py --seed 42`: 140 lecturas, 34 incidencias y dos ejecuciones; la API devolvió esos recuentos y los umbrales esperados.
2. `/docs` y salud de Streamlit devolvieron HTTP 200; OpenAPI identificó la versión 1.0.0. Última lectura, historial y filtro de incidencias se consultaron por HTTP real.
3. Tres lecturas normales a intervalo predeterminado: los recuentos pasaron a **143 lecturas y 34 incidencias**, manteniendo los datos anteriores.
4. AppTest contra esa API mostró cuatro métricas y cuatro gráficas. Funcionaron pausa, selección de 60 lecturas y actualización manual; el estado normal actual quedó separado de las incidencias históricas.
5. Los cuatro filtros de fecha que antes daban 500 devolvieron **422 por HTTP real**.

Esto verifica los comandos y la conexión entre procesos; no afirma que se haya abierto visualmente ese recorrido en Chrome. También se revisaron los enlaces locales del README y la sintaxis PowerShell de sus bloques, sin necesidad de activar scripts ni cambiar `ExecutionPolicy`.

Después se ejecutaron literalmente las **seis consultas `Invoke-RestMethod` del README en PowerShell**, sustituyendo solo el puerto por uno libre y usando otra base temporal de demo: salida 0. Así se comprobó también el cliente PowerShell documentado, además de las consultas HTTP del recorrido anterior.

## Datos de demo y protección del histórico

`scripts/prepare_demo.py` exige una salida explícita nueva y reserva el archivo con creación exclusiva. Rechaza base o auxiliares existentes; no contiene borrados. Sus seis pruebas comprueban reproducibilidad de valores, tres reglas, dos ejecuciones y preservación de archivos existentes. Si una generación falla después de crear el archivo puede quedar una demo parcial: se debe elegir otra ruta, sin borrar automáticamente.

Se auditó el histórico local con SQLite URI `mode=ro`, `query_only` y una transacción de lectura. Los recuentos se correspondieron con reglas y umbrales; no aparecieron duplicados, referencias rotas ni discordancias entre alertas y mediciones, y `PRAGMA quick_check` devolvió `ok`. Los registros y el informe detallado de esa base permanecen privados dentro de rutas ignoradas; no se copiaron al contenido público.

## Preparación pública y CI

La versión 1.0.0 está en `pyproject.toml`, módulo y OpenAPI. Se construyó un wheel estándar PEP 517 desde una copia aislada de archivos públicos; se inspeccionaron sus diez módulos y cuatro archivos de metadatos. Este proyecto se ejecuta desde el checkout instalado según el README; el wheel no sustituye por sí solo al lanzador Streamlit de la raíz ni a las herramientas de demo.

Se probaron patrones de `.gitignore` con Git en un repositorio aislado, sin inicializar la raíz del proyecto. Bases, auxiliares SQLite, entornos, `.audit`, credenciales habituales, temporales y artefactos quedan excluidos. Un escaneo heurístico de los archivos publicables no detectó tokens, claves privadas ni secretos literales; no equivale a una garantía completa ni a un análisis de vulnerabilidades.

El workflow mantiene cuatro combinaciones Windows/Ubuntu × Python 3.12/3.14, permisos `contents: read`, caché de pip y timeout. Se añadieron `pip check` y smoke check a pytest con cobertura. En la preparación local se validó con [actionlint 1.7.12](https://github.com/rhysd/actionlint/releases/tag/v1.7.12), salida 0; en ese momento todavía no se había publicado el código ni ejecutado CI remota.

## Publicación y ejecución real de GitHub Actions

El **31 de octubre de 2026** se publicó el repositorio público [EduardoManzanoAlcaraz/robotelemetry-lite](https://github.com/EduardoManzanoAlcaraz/robotelemetry-lite), con `main` como rama principal. La [ejecución 41203513698](https://github.com/EduardoManzanoAlcaraz/robotelemetry-lite/actions/runs/41203513698) comprobó el commit [`c96bb3bd5e827978d5e55f9b7855a859d630924f`](https://github.com/EduardoManzanoAlcaraz/robotelemetry-lite/commit/c96bb3bd5e827978d5e55f9b7855a859d630924f) y terminó con las **cuatro combinaciones correctas**.

| Runner | Python observado en el log | pytest | Resultado de pytest | Cobertura con ramas |
| --- | --- | --- | --- | --- |
| Ubuntu | 3.12.15 | 9.2.0 | 161 passed in 6.83s | 94 % |
| Ubuntu | 3.14.9 | 9.2.0 | 161 passed in 6.16s | 94 % |
| Windows | 3.12.10 | 9.2.0 | 161 passed in 23.75s | 94 % |
| Windows | 3.14.9 | 9.2.0 | 161 passed in 36.38s | 94 % |

En los cuatro jobs, `pip check` indicó `No broken requirements found.` y el smoke check terminó correctamente: 80 lecturas, 34 incidencias de las tres reglas, persistencia tras reiniciar la API, cuatro métricas, cuatro gráficas y salud HTTP 200 de Streamlit. Son resultados remotos reales, contrastados con sus logs, distintos de las ejecuciones locales anteriores. Las versiones se resolvieron dentro de los rangos declarados; no se suman las coberturas de los cuatro jobs.

La CI ejecuta el dashboard mediante AppTest y no completa la inspección visual pendiente del eje de varios días en un navegador.

## Pendientes explícitos

- Inspección visual final de los ejes de varios días y controles en un navegador accesible. El cambio está probado a nivel de datos y especificación.
- No se ha realizado una auditoría específica de CVE, carga sostenida, dispositivos móviles ni producción.
- Continúan las limitaciones del README: autenticación ausente para exposición pública, ausencia de retención/migraciones/copias automáticas y consultas de un refresco sin instantánea transaccional compartida.

El código, la demo y la documentación están preparados para portfolio. La revisión visual de cierre no se declara completada. No se implementaron ABB, AWS ni cambios de esquema SQLite.
