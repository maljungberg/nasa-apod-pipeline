# NASA APOD Data Pipeline

Pipeline automatizado que extrae, normaliza y almacena la **Astronomy Picture of the Day** (APOD) de la NASA, y la expone en una galería web accesible desde cualquier dispositivo.

Construido íntegramente sobre la capa gratuita de Google Cloud, este proyecto demuestra un flujo de trabajo profesional de ingeniería de datos: extracción con tolerancia a fallos, limpieza avanzada, carga idempotente en Firestore, orquestación con Cloud Run + Cloud Scheduler, secretos gestionados con Secret Manager y un frontend mínimo alojado en Firebase Hosting.

---

## 🏗️ Arquitectura

[GCP] Cloud Scheduler (cada lunes 6 AM UTC)
       │
       ▼
[GCP] Cloud Run (Flask + gunicorn)
       │
       ├─ Extrae (NASA API con backoff)
       ├─ Transforma y normaliza
       ├─ Carga en Firestore (upsert)
       ├─ Actualiza documento de control
       └─ Envía alerta por email si falla (SendGrid)
       │
       ▼
[GCP] Firestore (colección `apod`)
       │
       ▼
[Firebase Hosting] Frontend vanilla JS (lectura directa)

## 🛠️ Stack tecnológico

| Categoría        | Tecnología                        |
|------------------|-----------------------------------|
| Orquestación     | Cloud Scheduler + Cloud Run       |
| Base de datos    | Firestore (modo nativo)           |
| Secretos         | Secret Manager                    |
| Notificaciones   | SendGrid                          |
| Frontend         | Firebase Hosting + SDK Firestore  |
| Testing          | Pytest                            |
| Contenedores     | Docker                            |
| CI/CD            | Cloud Build                       |

### Estructura del repositorio
```text
nasa-apod-pipeline/
├── .github/workflows/ci.yml       # Integración continua
├── pipeline/                      # Código del pipeline
│   ├── main.py                    # Entrypoint de Cloud Run
│   ├── extract.py                 # Llamada a API con reintentos
│   ├── transform.py               # Limpieza y normalización
│   ├── load.py                    # Carga en Firestore
│   ├── utils.py                   # Logging y envío de emails
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/index.html            # Galería web (HTML+JS vanilla)
├── config/
│   ├── .env.example               # Variables de entorno necesarias
│   └── firestore.rules            # Reglas de seguridad
├── docs/design.md                 # Documento de diseño detallado
├── tests/test_transform.py        # Tests unitarios
├── scripts/deploy.sh              # Comandos de despliegue
└── README.md
```
---

## 🚀 Despliegue desde cero

### 1. Clonar e instalar dependencias locales

```bash
git clone https://github.com/Mauriljb/nasa-apod-pipeline.git
cd nasa-apod-pipeline
python -m venv env && source env/bin/activate
pip install -r pipeline/requirements.txt
```
### 2. Configurar variables de entorno

Copiá `.env.example` a `.env` y completá:
```env
NASA_API_KEY=tu-api-key
GOOGLE_CLOUD_PROJECT=primer-proyecto-103
SENDGRID_API_KEY=tu-sendgrid-key
TO_EMAIL=tu@email.com
FROM_EMAIL=pipeline@example.com
```
### 3. Ejecutar tests localmente
```bash
pytest tests/ -v
```
### 4. Construir imagen con Cloud Build
```bash
gcloud builds submit --tag gcr.io/primer-proyecto-103/apod-pipeline --region=global
```
### 5. Almacenar secretos
```bash
echo -n "TU_API_KEY" | gcloud secrets create nasa-api-key --data-file=-
gcloud secrets add-iam-policy-binding nasa-api-key \
  --member="serviceAccount:apod-pipeline-sa@..." \
  --role="roles/secretmanager.secretAccessor"
```
### 6. Desplegar en Cloud Run
```bash
gcloud run deploy apod-pipeline \
  --image gcr.io/primer-proyecto-103/apod-pipeline \
  --region us-central1 \
  --allow-unauthenticated \
  --set-secrets="NASA_API_KEY=nasa-api-key:latest" \
  --service-account=apod-pipeline-sa@...
```
### 7. Configurar Cloud Scheduler
```bash
gcloud scheduler jobs create http apod-weekly \
  --schedule "0 6 * * 1" \
  --uri "URL_DE_CLOUD_RUN" \
  --http-method POST
```
### 8. Desplegar frontend
```bash
firebase init hosting   # carpeta pública: frontend
firebase deploy --only hosting
```
## 🧪 Backfill e incremental

* Primera ejecución: el pipeline detecta ausencia del documento de control y ejecuta un backfill completo desde 2020-01-01 hasta ayer, en bloques de 7 días.

* Ejecuciones semanales: carga solo los 7 días anteriores con solapamiento de 1 día.
* Idempotencia: la clave natural date (YYYY-MM-DD) garantiza que los registros no se dupliquen.

## 📊 Normalización aplicada
* Decodificación de entidades HTML (`&amp;`, `&lt;`, etc.)
* Eliminación de tags `<br>`, `<p>` y otros residuos HTML
* Limpieza de saltos de línea y colapso de espacios
* Estandarización del campo copyright
* Gestión de valores nulos y diferencias entre imágenes/videos

Ver `docs/design.md` para todos los detalles.
## 🔐 Seguridad

* API key de NASA en Secret Manager
* Cuenta de servicio con privilegios mínimos (datastore.user)
* Reglas de Firestore: solo lectura pública en la colección apod
* .env nunca versionado

## 📈 Monitoreo

* Logs centralizados en Cloud Logging
* Alertas por email vía SendGrid ante fallos (configuración pendiente de activación final)
* Reintentos con backoff exponencial (doble capa: urllib3 + aplicación)

## 📸 Captura del frontend

https://docs/screenshot.png
## 📄 Licencia

MIT © Mauricio L. J. B. (2026)

¿Querés ejecutarlo en tu propio proyecto?
Seguí los pasos de despliegue y reemplazá primer-proyecto-103 por tu ID de proyecto GCP.