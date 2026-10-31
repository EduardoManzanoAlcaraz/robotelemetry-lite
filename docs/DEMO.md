# Demostración de RoboTelemetry Lite v1.0.0

Guion para enseñar el flujo **simulador → SQLite → FastAPI → Streamlit**. Los comandos completos de instalación y arranque están en el [README](../README.md), que permite ejecutar el proyecto sin consultar otros documentos. Los resultados de comprobaciones ya realizadas están en [VERIFICACION.md](VERIFICACION.md); este guion describe pasos para una nueva demostración.

## 1. Preparar datos limpios sin borrar el histórico

Desde la raíz, con el entorno instalado:

```powershell
.\.venv\Scripts\python.exe scripts\prepare_demo.py --output data/demo-v1.sqlite3 --seed 42
```

Resultado esperado: **140 lecturas**, **34 incidencias**, **2 ejecuciones**. Incluye 60 lecturas normales y 80 del escenario demo; las incidencias se distribuyen en 17 de temperatura, 5 de batería y 12 de obstáculos. Usa umbrales 20 %, 65 °C y 0,5 m.

El archivo debe ser nuevo. Si ya existe, el comando termina con error y no cambia sus datos. Elige otro nombre y cambia también `ROBO_DB_PATH` en las terminales de API y simulador. No necesitas borrar archivos para repetir la demo. La herramienta no utiliza el `ROBO_DB_PATH` del entorno: exige la ruta de salida explícita.

La semilla repite valores; fechas e identificadores son nuevos. Los lotes sin espera representan historial sintético que termina al iniciar cada ejecución, por lo que la vista puede avisar después de que los datos ya no se actualizan.

## 2. Arrancar API y dashboard

En una terminal PowerShell situada en la raíz:

```powershell
$env:ROBO_DB_PATH = 'data/demo-v1.sqlite3'
$env:ROBO_BATTERY_LOW_PCT = '20'
$env:ROBO_TEMPERATURE_HIGH_C = '65'
$env:ROBO_OBSTACLE_NEAR_M = '0.5'
.\.venv\Scripts\python.exe -m uvicorn robotelemetry.api:app --host 127.0.0.1 --port 8000
```

En otra terminal, desde la misma raíz:

```powershell
$env:ROBO_API_URL = 'http://127.0.0.1:8000'
.\.venv\Scripts\python.exe -m streamlit run dashboard.py --server.address 127.0.0.1 --server.port 8501 --browser.gatherUsageStats false
```

Abre [el dashboard](http://127.0.0.1:8501) y [OpenAPI](http://127.0.0.1:8000/docs). Identifica el aviso **SENSORES SIMULADOS**. Explica las cuatro métricas y las unidades, las alertas de la última lectura y la diferencia con las incidencias guardadas.

## 3. Relacionar las consultas con la interfaz

En una tercera terminal:

```powershell
Invoke-RestMethod 'http://127.0.0.1:8000/health'
Invoke-RestMethod 'http://127.0.0.1:8000/config'
Invoke-RestMethod 'http://127.0.0.1:8000/telemetry/latest'
Invoke-RestMethod 'http://127.0.0.1:8000/telemetry/history?limit=5'
Invoke-RestMethod 'http://127.0.0.1:8000/alerts?limit=5'
```

Comprueba los contadores iniciales antes de iniciar generación en directo. Relaciona `run_id`, secuencia y valores de la respuesta con los detalles de la lectura en el dashboard. Señala que `/health` comprueba SQLite, no que el simulador siga activo.

Selecciona 180 lecturas para ver ambas ejecuciones de la demo. Después selecciona 60 para reducir la ventana. Los dos lotes sintéticos pueden solaparse en el tiempo, por lo que esa ventana reducida también puede incluir ambas ejecuciones. Comprueba las cuatro gráficas, sus horas UTC y sus leyendas. La separación se realiza por ejecución, no por una línea artificial entre runs.

Descarga el CSV y abre la tabla: contienen la misma ventana seleccionada, no toda la base de datos. Las incidencias muestran las últimas 30 ocurrencias.

## 4. Añadir lecturas en directo

En esa tercera terminal, desde la raíz:

```powershell
$env:ROBO_DB_PATH = 'data/demo-v1.sqlite3'
$env:ROBO_BATTERY_LOW_PCT = '20'
$env:ROBO_TEMPERATURE_HIGH_C = '65'
$env:ROBO_OBSTACLE_NEAR_M = '0.5'
.\.venv\Scripts\python.exe -m robotelemetry.simulator --seed 42 --scenario normal
```

Observa valores actuales normales mientras siguen presentes las incidencias históricas. Desactiva la actualización automática y pulsa «Actualizar ahora». La pausa detiene el refresco de la vista; el simulador sigue escribiendo.

Detén el simulador con `Ctrl+C`. Si quieres mostrar anomalías en directo, ejecuta:

```powershell
.\.venv\Scripts\python.exe -m robotelemetry.simulator --seed 42 --scenario demo --samples 80
```

El escenario recorre fases de normalidad, proximidad de obstáculos, calentamiento y descarga de batería. Una alerta mantenida genera una ocurrencia por medición, no un incidente único.

## 5. Enseñar persistencia y validación

Detén y reinicia la API con el mismo archivo y umbrales. Comprueba `/health`: los contadores permanecen. El dashboard puede mostrar temporalmente un error de conexión y recuperarse al actualizar.

En `/docs`, prueba `limit=0`, `offset=9223372036854775808` y un filtro temporal sin zona horaria: deben devolver `422`. Los filtros extremos que desbordan al convertirse a UTC también se rechazan con `422`. La última lectura de una base vacía devuelve `404`.

## 6. Ejecutar la evidencia automatizada

```powershell
.\.venv\Scripts\python.exe -m pytest --cov=robotelemetry --cov-report=term-missing
.\.venv\Scripts\python.exe scripts\smoke_check.py
.\.venv\Scripts\python.exe -m pip check
```

El smoke check crea otra base temporal y sus propios servidores; no utiliza la demo ni el histórico habitual. Comprueba el flujo HTTP, la persistencia tras reiniciar la API y el dashboard con AppTest. No es una inspección visual de navegador.

Para una presentación, conserva la salida y cita el entorno y la fecha. El informe de verificación diferencia resultados locales de la [matriz de GitHub Actions ejecutada correctamente](https://github.com/EduardoManzanoAlcaraz/robotelemetry-lite/actions/runs/41203513698): Windows y Ubuntu con Python 3.12 y 3.14.

## Revisión visual pendiente de varios días

Cuando el navegador vuelva a estar disponible, comprobar ventanas con una y varias ejecuciones, y una ventana que abarque al menos 24 horas. En ese caso los cuatro ejes deben incluir **fecha y hora UTC**: un tick diario a medianoche es válido, pero la fecha debe distinguirlo del siguiente día. En ventanas cortas deben mostrar horas UTC legibles.

Las pruebas automatizadas comprueban las especificaciones y los datos conservados de las cuatro gráficas, incluidos formatos ISO mixtos y ventanas de varios días. La revisión visual final de ese caso no se ha realizado; las capturas de `assets/` documentan el frontend real observado el 26 de octubre de 2026, antes del ajuste del eje de varios días, y no validan ese nuevo formato.
