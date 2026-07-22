"""
Punto de entrada para Cloud Run con Flask.
Orquesta la extracción semanal o la carga histórica inicial (backfill)
de APOD de la NASA.
"""

import os
import logging
from datetime import datetime, timedelta, timezone

from flask import Flask, request

from pipeline.extract import fetch_apod_range
from pipeline.transform import transform_all
from pipeline.load import load_records, get_last_loaded_date, update_control_date
from pipeline.utils import send_failure_email, setup_logging

# Configurar logging estructurado
setup_logging()
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Fecha de inicio para el backfill histórico
BACKFILL_START_DATE = "2020-01-01"
# Tamaño de bloque en días para backfill (respetuoso con la API)
BACKFILL_BLOCK_DAYS = 7


def run_backfill():
    """
    Ejecuta la carga histórica desde BACKFILL_START_DATE hasta ayer,
    en bloques de BACKFILL_BLOCK_DAYS días.
    """
    logger.info("Iniciando backfill desde %s", BACKFILL_START_DATE)
    today = datetime.now(timezone.utc).date()
    end_date = today - timedelta(days=1)  # hasta ayer

    current_start = datetime.strptime(BACKFILL_START_DATE, "%Y-%m-%d").date()
    while current_start <= end_date:
        block_end = min(current_start + timedelta(days=BACKFILL_BLOCK_DAYS - 1), end_date)
        start_str = current_start.isoformat()
        end_str = block_end.isoformat()
        logger.info("Backfill bloque: %s -> %s", start_str, end_str)

        try:
            raw = fetch_apod_range(start_str, end_str)
            if raw:
                cleaned = transform_all(raw)
                loaded = load_records(cleaned)
                logger.info("Bloque cargado: %d registros", loaded)
            # Actualizar control con la fecha final del bloque
            update_control_date(end_str)
        except Exception as e:
            logger.error("Error en backfill bloque %s-%s: %s", start_str, end_str, e)
            send_failure_email(f"Backfill falló en bloque {start_str}-{end_str}: {e}")
            raise  # detener backfill; el scheduler reintentará luego

        current_start = block_end + timedelta(days=1)

    logger.info("Backfill completado hasta %s", end_date.isoformat())


def run_incremental():
    """
    Ejecuta la carga semanal desde la última fecha cargada hasta ayer.
    """
    last_date = get_last_loaded_date()
    if not last_date:
        logger.info("Control vacío, se inicia backfill en su lugar.")
        run_backfill()
        return

    today = datetime.now(timezone.utc).date()
    start_date = last_date  # inclusive, solapamiento
    end_date = (today - timedelta(days=1)).isoformat()  # hasta ayer inclusive

    logger.info("Incremental: %s -> %s", start_date, end_date)

    raw = fetch_apod_range(start_date, end_date)
    if not raw:
        logger.info("No se encontraron nuevos APOD en el rango.")
        return

    cleaned = transform_all(raw)
    loaded = load_records(cleaned)
    logger.info("Incremental cargados: %d registros", loaded)

    # Actualizar control a la fecha final del rango (la máxima cargada)
    if cleaned:
        max_date = max(r["date"] for r in cleaned)
        update_control_date(max_date)
    else:
        update_control_date(end_date)


@app.route("/", methods=["POST"])
def execute_pipeline():
    """Endpoint que Cloud Scheduler invocará vía POST."""
    try:
        last_date = get_last_loaded_date()
        if not last_date:
            run_backfill()
        else:
            run_incremental()
        return "OK", 200
    except Exception as e:
        logger.exception("Fallo en el pipeline: %s", e)
        send_failure_email(str(e))
        return "Error", 500


# Para desarrollo local (opcional)
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))