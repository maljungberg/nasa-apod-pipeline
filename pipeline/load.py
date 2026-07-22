"""
Módulo de carga para Firestore.
Maneja inserción de registros APOD y mantenimiento del documento de control.
"""
import os
import logging
from typing import List, Dict, Any, Optional

from google.cloud import firestore
from google.cloud.firestore_v1 import Client

logger = logging.getLogger(__name__)

# Colecciones en Firestore
COLLECTION_APOD = "apod"
COLLECTION_PIPELINE_STATE = "pipeline_state"
DOC_CONTROL = "apod_control"


def _get_client() -> Client:
    """
    Retorna un cliente de Firestore.
    En Cloud Run, usa la cuenta de servicio por defecto.
    En local, necesita GOOGLE_APPLICATION_CREDENTIALS o gcloud auth.
    """
    database_id = os.environ.get("FIRESTORE_DATABASE", "apod")
    return firestore.Client()


def load_records(records: List[Dict[str, Any]]) -> int:
    """
    Inserta una lista de registros limpios en la colección 'apod'.
    Usa la fecha como ID del documento (upsert natural).

    Args:
        records: Lista de diccionarios con los campos normalizados.

    Returns:
        Número de registros insertados/actualizados.
    """
    if not records:
        logger.info("No hay registros para cargar.")
        return 0

    db = _get_client()
    batch = db.batch()
    count = 0

    for rec in records:
        doc_id = rec.get("date")
        if not doc_id:
            logger.warning("Registro sin 'date', se omite: %s", rec)
            continue

        doc_ref = db.collection(COLLECTION_APOD).document(doc_id)
        # set() con merge=True hace upsert: crea si no existe, actualiza si existe
        batch.set(doc_ref, rec, merge=True)
        count += 1

        # Firestore acepta hasta 500 operaciones por batch
        if count % 500 == 0:
            batch.commit()
            logger.info("Commit de batch intermedio (%d documentos).", count)
            batch = db.batch()

    # Commit final para los restantes
    if count % 500 != 0:
        batch.commit()

    logger.info("Carga completada: %d registros insertados/actualizados en Firestore.", count)
    return count


def get_last_loaded_date() -> Optional[str]:
    """
    Lee la fecha del último APOD cargado desde el documento de control.

    Returns:
        String en formato YYYY-MM-DD o None si no existe el documento
        o el campo está vacío.
    """
    db = _get_client()
    doc_ref = db.collection(COLLECTION_PIPELINE_STATE).document(DOC_CONTROL)
    doc = doc_ref.get()

    if not doc.exists:
        logger.info("Documento de control no encontrado. Se asume primera ejecución (backfill).")
        return None

    last_date = doc.to_dict().get("last_loaded_date")
    logger.info("Última fecha cargada según control: %s", last_date)
    return last_date if last_date else None


def update_control_date(last_date: str) -> None:
    """
    Actualiza el documento de control con la nueva última fecha cargada.

    Args:
        last_date: Fecha en formato YYYY-MM-DD.
    """
    db = _get_client()
    doc_ref = db.collection(COLLECTION_PIPELINE_STATE).document(DOC_CONTROL)

    from datetime import datetime, timezone
    data = {
        "last_loaded_date": last_date,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    doc_ref.set(data, merge=True)
    logger.info("Documento de control actualizado: last_loaded_date=%s", last_date)