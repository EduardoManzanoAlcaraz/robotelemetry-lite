# Historial de cambios

## 1.0.0 — 2026-10-31

Código de la versión publicado en [EduardoManzanoAlcaraz/robotelemetry-lite](https://github.com/EduardoManzanoAlcaraz/robotelemetry-lite), con `main` como rama principal.

### Incluido

- Simulación reproducible de cuatro magnitudes y escenarios normales o de anomalía.
- Persistencia transaccional de mediciones y ocurrencias de alerta en SQLite.
- API FastAPI de consulta con validación y errores controlados.
- Dashboard Streamlit con estado actual, alertas actuales separadas del histórico, cuatro gráficas UTC, tabla y CSV de la ventana visible.
- Herramienta de demo que crea una base nueva, exige una salida explícita y rechaza archivos y auxiliares existentes.
- Documentación de instalación y ejecución Windows PowerShell, arquitectura, demo y presentación del portfolio.
- Workflow para Windows y Ubuntu con Python 3.12 y 3.14, comprobación de dependencias, pytest con cobertura y smoke check.

### Corregido

- Offsets fuera del rango de SQLite rechazados con `422` antes del almacenamiento.
- Fechas futuras artificiales en adquisición acelerada: se conserva el reloj lógico y se registra UTC real cuando hay espera.
- Fechas ISO 8601 con precisiones y zonas mixtas normalizadas a UTC para conservar todas las mediciones en las gráficas.
- Actualización de la ventana de datos de las gráficas al refrescar la interfaz.
- Filtros de fecha que desbordan al normalizarse a UTC rechazados con `422`.
- Etiquetas ambiguas de ticks diarios: los ejes incluyen fecha y hora UTC para ventanas de al menos 24 horas.

### Verificación y alcance

Las correcciones disponen de regresiones automatizadas. Los resultados de pytest, cobertura, instalación limpia e integración realmente ejecutados se registran en [docs/VERIFICACION.md](docs/VERIFICACION.md).

La [primera ejecución de GitHub Actions](https://github.com/EduardoManzanoAlcaraz/robotelemetry-lite/actions/runs/41203513698) completó las cuatro combinaciones Windows/Ubuntu × Python 3.12/3.14: 161 pruebas, 94 % de cobertura, `pip check` y smoke check correctos en cada una.

Las capturas incluidas son reales, tomadas el 26 de octubre de 2026. La revisión visual final del caso de varios días sigue pendiente por indisponibilidad del navegador de automatización. No se implementa integración ABB ni AWS, ni se distribuyen bases de datos o históricos locales.
