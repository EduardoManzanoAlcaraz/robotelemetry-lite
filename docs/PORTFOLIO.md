# Presentación del proyecto v1.0.0

## Descripción para GitHub

> Telemetría simulada de un robot móvil en Python: escenarios reproducibles, persistencia transaccional SQLite, API FastAPI, dashboard Streamlit y pruebas automatizadas. Ejecución local sin hardware ni servicios de pago.

El código de la versión 1.0.0 está publicado en [EduardoManzanoAlcaraz/robotelemetry-lite](https://github.com/EduardoManzanoAlcaraz/robotelemetry-lite). Los archivos publicados se revisaron para excluir bases de datos locales, entornos virtuales, exportaciones personales y credenciales.

## Afirmaciones verificables

| Afirmación defendible | Evidencia |
| --- | --- |
| Separé generación, modelos, reglas, persistencia, API y presentación. | Módulos de `src/robotelemetry/` y arquitectura del README. |
| Implementé un generador con estado, semilla y escenarios de anomalía. | `simulator.py` y pruebas de reproducibilidad, frenado y límites. |
| Distinguí el tiempo lógico del modelo de la hora UTC de adquisición. | Ejecución acelerada y pruebas para intervalos inferiores a un segundo. |
| Guardé cada lectura y sus alertas en una transacción SQLite. | `storage.py`, claves foráneas y prueba de rollback. |
| Validé contratos y parámetros HTTP, incluidos casos extremos. | Modelos y regresiones de offsets y filtros de fecha que devuelven `422`. |
| Construí un dashboard que consulta una API y presenta estados de error. | Cliente HTTP, AppTest y capturas reales del frontend. |
| Normalicé fechas ISO con distintas precisiones y zonas horarias. | Regresiones que verifican datos de las cuatro gráficas en UTC. |
| Preparé una demo que rechaza bases existentes en lugar de sobrescribirlas. | `scripts/prepare_demo.py`, creación exclusiva y pruebas de protección. |
| Probé el flujo completo con procesos locales y HTTP reales. | `scripts/smoke_check.py` y resultados en `VERIFICACION.md`. |
| Ejecuté CI para Windows y Ubuntu con Python 3.12 y 3.14. | [Cuatro combinaciones correctas en GitHub Actions](https://github.com/EduardoManzanoAlcaraz/robotelemetry-lite/actions/runs/41203513698), con pytest, cobertura, `pip check` y smoke check. |

Las cifras de pruebas, cobertura y versiones deben proceder de [VERIFICACION.md](VERIFICACION.md). Indica su entorno y fecha; no conviertas un resultado local en una afirmación de CI, producción o uso real.

## Texto breve para LinkedIn

> He publicado el código de RoboTelemetry Lite v1.0.0 como proyecto de portfolio en Python. Simula batería, temperatura, velocidad y distancia a obstáculos de un robot móvil, guarda las lecturas y alertas en SQLite y las presenta mediante FastAPI y Streamlit.
>
> Me he centrado en separar responsabilidades, validar los datos y comprobar el flujo completo. Durante la revisión corregí casos de paginación, tiempos de adquisición acelerada y tratamiento de fechas, añadiendo pruebas de regresión.
>
> También preparé una demostración reproducible que crea una base nueva sin sobrescribir el histórico. Los sensores son simulados y la ejecución es local: no hay conexión con hardware ni despliegue cloud.
>
> El repositorio documenta la instalación, las decisiones técnicas, las pruebas realmente ejecutadas y sus limitaciones.

Repositorio: [EduardoManzanoAlcaraz/robotelemetry-lite](https://github.com/EduardoManzanoAlcaraz/robotelemetry-lite). Si incluyes métricas, toma las cifras finales del informe de verificación y distingue resultados locales de CI. No atribuyas al proyecto experiencia con ABB, AWS, usuarios reales o garantías de producción.

## Explicación para una entrevista

**¿Qué problema resuelve?** Permite observar el estado y las tendencias de un robot móvil simulado sin depender de hardware, practicando un flujo de datos completo y verificable.

**¿Por qué tres procesos?** La generación sigue funcionando aunque cierre la interfaz. La API sirve consultas y el dashboard consume HTTP; los refrescos de la vista no generan lecturas ni reinician el almacenamiento.

**¿Qué hace cada módulo?** `config.py` centraliza rutas y umbrales; `models.py` define contratos; `simulator.py` genera y programa la adquisición; `alerts.py` evalúa reglas; `service.py` coordina el caso de uso; `storage.py` contiene SQL y transacciones; `api.py` valida y expone consultas; `dashboard.py` presenta las respuestas; `dashboard_styles.py` contiene los estilos.

**¿Dónde se demuestra Python?** En clases con estado y generador aleatorio privado, funciones puras, modelos tipados, enumeraciones, dataclasses, manejo de excepciones, context managers para conexiones, fechas conscientes de zona horaria y una CLI con `argparse`. Las pruebas usan fixtures, parametrización y sustitución controlada del reloj.

**¿Dónde se demuestra desarrollo de software?** En contratos de datos, separación de responsabilidades, transacciones, consultas parametrizadas, errores HTTP controlados, regresiones que reproducen defectos y herramientas de integración aisladas del histórico local. La documentación distingue lo ejecutado de lo pendiente.

**¿Por qué SQLite?** Ofrece persistencia y transacciones sin desplegar un servicio adicional. El modo WAL y conexiones cortas sirven para este MVP local. No afirmo que la arquitectura escale a múltiples productores sin medirla.

**¿Qué garantiza una transacción aquí?** Que la medición y las alertas de esa medición se confirman juntas. Un fallo revierte la escritura y evita una medición parcialmente registrada respecto a sus alertas.

**¿Qué significa reproducible?** La misma semilla y escenario repiten valores. Cada ejecución tiene fechas e identificadores nuevos y comienza otro estado; no reanuda el generador de una ejecución detenida.

**¿Qué diferencia hay entre tiempo simulado y real?** El modelo avanza un segundo por paso. Un intervalo de 0,1 segundos acelera la adquisición, cuya fecha es UTC real. El lote sin espera crea historial sintético anclado al pasado.

**¿Por qué puede haber más incidencias que lecturas?** Cada lectura evalúa tres reglas independientes. Una condición mantenida genera ocurrencias sucesivas. Deduplicar, reconocer o cerrar un incidente requiere otro modelo que este MVP no implementa.

**¿Qué enseña el caso de los ejes temporales?** Que fechas válidas pueden producir una etiqueta ambigua: los ticks diarios aparecen a medianoche y mostrar solo la hora repite `00:00:00`. Para ventanas de al menos 24 horas se incluye también la fecha. Se comprobaron especificaciones y datos mediante regresiones; la última revisión visual de ese caso sigue pendiente.

**¿Qué queda antes de producción?** Autenticación, autorización, observabilidad, migraciones, retención y copias de seguridad; además de probar carga y fallos y decidir el despliegue según requisitos reales. No están implementados ABB ni AWS.

## Material para enseñar

1. El diagrama y los comandos autocontenidos del README.
2. Las capturas reales de `docs/assets/` y el aviso de sensores simulados.
3. Una demo nueva con 140 lecturas y 34 incidencias, seguida de una ejecución normal en directo.
4. La misma lectura en el dashboard y en `/telemetry/latest`.
5. Una prueba de transacción y una regresión de parámetros HTTP.
6. La salida real de pytest, cobertura y smoke check, con sus límites documentados.
