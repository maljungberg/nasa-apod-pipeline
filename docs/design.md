# Proyecto: NASA APOD Data Pipeline

**Versión:** 1.0  
**Autor:** Mauri   
**Fecha:** 2026-06-28  
**Estado:** Diseño aprobado – listo para implementación  

---

## 1. Resumen ejecutivo

Construcción de un pipeline automatizado que extrae semanalmente la foto astronómica del día (APOD) de la API pública de la NASA, normaliza los datos, los almacena en una base de datos NoSQL en la nube y expone una galería web accesible desde cualquier dispositivo. El proyecto está diseñado íntegramente sobre la capa gratuita de Google Cloud, sin coste operativo, y sigue prácticas profesionales de ingeniería de datos (secretos seguros, idempotencia, reintentos, notificaciones).

---

## 2. Requisitos funcionales

- **RF1 – Carga histórica (backfill):** La primera ejecución del pipeline debe recuperar todos los APOD desde el 2020‑01‑01 hasta el día actual.
- **RF2 – Carga incremental semanal:** Una vez completada la carga histórica, el sistema ejecutará automáticamente una extracción semanal cada lunes a las 06:00 UTC, obteniendo los APOD de los últimos 7 días (con solapamiento de 1 día para asegurar cobertura).
- **RF3 – Normalización:** Los datos crudos se limpiarán y normalizarán (detalle en sección 4).
- **RF4 – Idempotencia:** La clave natural `date` (YYYY‑MM‑DD) garantiza que ningún registro se duplique. Operación de inserción/actualización (upsert).
- **RF5 – Acceso remoto:** Los datos estarán disponibles mediante una galería web de fotos con posibilidad de ver la metadata de cada imagen.
- **RF6 – Notificaciones:** Se enviará un correo electrónico si la extracción falla tras agotar los reintentos.
- **RF7 – Seguridad:** La API key de la NASA se almacenará en Secret Manager y nunca estará presente en el código fuente.

---

## 3. Stack tecnológico

| Componente        | Tecnología                  | Justificación                                                                 |
| ----------------- | --------------------------- | ----------------------------------------------------------------------------- |
| Orquestación      | Cloud Scheduler + Cloud Run | Serverless, capa gratuita generosa, escalable a cero.                         |
| Base de datos     | Firestore (modo nativo)     | Modelo de documentos ideal para APOD; SDK web directo; sin necesidad de API intermedia. |
| Almacenamiento de secretos | Secret Manager       | Gestión profesional de secretos, rotación, auditoría.                         |
| Notificaciones    | SendGrid                    | 100 correos/día gratis, fácil integración vía REST.                           |
| Frontend          | Firebase Hosting + HTML/JS  | Hospedaje gratuito con SSL; consumo directo de Firestore desde el navegador.   |
| Lenguaje          | Python 3.10+                | Robusto, excelente soporte para GCP y manejo de JSON.                         |

---

## 4. Esquema de datos en Firestore

**Colección:** `apod`  
**ID del documento:** fecha en formato `YYYY-MM-DD` (string)

| Campo            | Tipo      | Descripción                                                                 |
| ---------------- | --------- | --------------------------------------------------------------------------- |
| `date`           | string    | Fecha del APOD (mismo que el ID).                                           |
| `title`          | string    | Título de la imagen/video.                                                  |
| `explanation`    | string    | Texto explicativo (limpio de entidades HTML).                               |
| `url`            | string    | URL de la imagen en calidad estándar.                                       |
| `hdurl`          | string    | URL de la imagen en HD (puede estar vacío).                                 |
| `media_type`     | string    | "image" o "video".                                                          |
| `copyright`      | string    | Nombre del autor o "Public Domain".                                         |
| `thumbnail_url`  | string    | Solo para videos: URL del thumbnail de YouTube.                             |
| `load_timestamp` | timestamp | Marca de tiempo UTC en que el registro fue insertado/actualizado.           |

**Colección de control:** `pipeline_state`  
**ID del documento:** `apod_control`

| Campo              | Tipo   | Descripción                                      |
| ------------------ | ------ | ------------------------------------------------ |
| `last_loaded_date` | string | Última fecha (YYYY‑MM‑DD) cargada exitosamente.  |
| `updated_at`       | timestamp | Momento de la última actualización del control. |

---

## 5. Estrategia de carga (backfill e incremental)

### 5.1 Carga histórica inicial (backfill)
- Se detecta que el documento `pipeline_state/apod_control` no existe o `last_loaded_date` es nulo.
- El pipeline solicita los APOD en bloques de 7 días consecutivos, comenzando el 2020‑01‑01.
- Por cada bloque:
  1. Llama a la API con `start_date` y `end_date`.
  2. Normaliza los registros obtenidos.
  3. Los inserta en Firestore usando `set()` con `merge=True` (upsert).
  4. Actualiza el documento de control con la nueva `last_loaded_date`.
- Se respeta un retardo de 200 ms entre llamadas para mantenerse muy por debajo del rate limit (1000 req/hora).

### 5.2 Carga semanal incremental
- Se ejecuta cada lunes a las 06:00 UTC.
- Lee `last_loaded_date` del documento de control.
- Define la ventana de extracción: desde `last_loaded_date` (inclusive) hasta el día anterior a la ejecución (inclusive).  
  Esto garantiza el solapamiento y la cobertura total.
- Realiza una única llamada a la API con `start_date` y `end_date`.
- Si la respuesta es exitosa, normaliza y almacena los registros de igual forma que el backfill.
- Actualiza `last_loaded_date` a la fecha máxima de los registros cargados.

---

## 6. Manejo de errores y reintentos

- El endpoint de Cloud Run implementa **5 reintentos con backoff exponencial** (2, 4, 8, 16, 32 segundos) dentro de la misma ejecución.
- Si todos los intentos fallan:
  - Se registra el error en Cloud Logging.
  - Se envía un correo electrónico al responsable mediante SendGrid.
  - El servicio termina con código de error, lo que permite que Cloud Scheduler lo vuelva a intentar el próximo lunes (o manualmente).
- Los errores contemplados incluyen: timeout de conexión, HTTP 503, HTTP 403 (API key inválida), errores de parseo del JSON.
- En ningún caso se pierden datos ya almacenados; la idempotencia garantiza la coherencia.

---

## 7. Seguridad

- **API key de NASA:** almacenada en Secret Manager. Cloud Run la recupera en tiempo de ejecución mediante la biblioteca cliente de GCP. El secreto se monta como variable de entorno en el contenedor.
- **Acceso a Firestore:**  
  - El servicio Cloud Run usa una cuenta de servicio con rol `roles/datastore.user` (escritura).  
  - El frontend web usa Firebase Authentication anónima + reglas de seguridad de Firestore que permiten solo lectura pública de la colección `apod`.  
- **Cloud Scheduler:** usa una cuenta de servicio con permiso `roles/run.invoker` para llamar al Cloud Run.

---

## 8. Visualización (galería web)

- Aplicación web estática alojada en Firebase Hosting (dominio público `*.web.app`).
- Implementación: HTML5, CSS3 y JavaScript vanilla (o un framework ligero como Alpine.js).
- Al cargar la página, el cliente Firestore realiza una consulta a la colección `apod` ordenada por `date` descendente y limitada a 50 documentos (paginación bajo demanda).
- Vista de grilla: miniaturas de las imágenes (`url`) con el título superpuesto.
- Al hacer clic en una imagen: se muestra una ventana modal con la metadata completa (`explanation`, `copyright`, `hdurl`, etc.).
- Diseño responsive, apto para móviles.

---

## 9. Monitoreo y logging

- Todos los logs de Cloud Run se envían a Cloud Logging de forma automática.
- Se registran al menos:
  - Inicio y fin de cada extracción.
  - Cantidad de registros obtenidos y almacenados.
  - Errores y reintentos.
  - Actualización del documento de control.
- El correo electrónico de fallo incluye el mensaje de error y un enlace a los logs.

---

## 10. Entregables del proyecto

1. Código fuente del pipeline Python (desplegable en Cloud Run).
2. Script de despliegue o comando `gcloud` para crear los recursos.
3. Configuración de Secret Manager y Cloud Scheduler.
4. Reglas de seguridad de Firestore (`firestore.rules`).
5. Frontend web (HTML/JS) listo para desplegar en Firebase Hosting.
6. Documentación de uso y mantenimiento.

---

**Próximo paso:** Implementación incremental, comenzando por la función de extracción y normalización en local, luego despliegue en Cloud Run y finalmente integración con Firestore y el frontend.