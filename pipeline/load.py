"""
Loading module for Firestore.
Handles the insertion of APOD records and the maintenance of the control document.
"""
import logging
from typing import List, Dict, Any, Optional

from google.cloud import firestore
from google.cloud.firestore_v1 import Client

logger = logging.getLogger(__name__)

# Collections in Firestore
COLLECTION_APOD = "apod"
COLLECTION_PIPELINE_STATE = "pipeline_state"
DOC_CONTROL = "apod_control"


def _get_client() -> Client:
    """
    Returns a Firestore client.
    In Cloud Run, it uses the default service account.
    In local development, it needs GOOGLE_APPLICATION_CREDENTIALS or gcloud auth.
    """
    return firestore.Client()


def load_records(records: List[Dict[str, Any]]) -> int:
    """
    Inserts a list of cleaned records into the 'apod' collection.
    Uses the date as the document ID (natural upsert).

    Args:
        records: List of dictionaries with the normalized fields.

    Returns:
        Number of records inserted/updated.
    """
    if not records:
        logger.info("No records to load.")
        return 0

    db = _get_client()
    batch = db.batch()
    count = 0

    for rec in records:
        doc_id = rec.get("date")
        if not doc_id:
            logger.warning("Record without 'date', skipping: %s", rec)
            continue

        doc_ref = db.collection(COLLECTION_APOD).document(doc_id)
        # set() with merge=True performs an upsert: it creates the record if it doesn't exist, and updates it if it does
        batch.set(doc_ref, rec, merge=True)
        count += 1

        # Firestore accepts up to 500 operations per batch
        if count % 500 == 0:
            batch.commit()
            logger.info("Commit de batch intermedio (%d documentos).", count)
            batch = db.batch()

    # Final commit for the rest
    if count % 500 != 0:
        batch.commit()

    logger.info("Carga completada: %d registros insertados/actualizados en Firestore.", count)
    return count


def get_last_loaded_date() -> Optional[str]:
    """
    Reads the date of the last loaded APOD from the control document.

    Returns:
        String in YYYY-MM-DD format or None if the document does not exist
        or the field is empty.
    """
    db = _get_client()
    doc_ref = db.collection(COLLECTION_PIPELINE_STATE).document(DOC_CONTROL)
    doc = doc_ref.get()

    if not doc.exists:
        logger.info("Control document not found. Assuming first execution (backfill).")
        return None

    last_date = doc.to_dict().get("last_loaded_date")
    logger.info("Last loaded date according to control: %s", last_date)
    return last_date if last_date else None


def update_control_date(last_date: str) -> None:
    """
    Updates the control document with the new last loaded date.

    Args:
        last_date: Date in YYYY-MM-DD format.
    """
    db = _get_client()
    doc_ref = db.collection(COLLECTION_PIPELINE_STATE).document(DOC_CONTROL)

    from datetime import datetime, timezone
    data = {
        "last_loaded_date": last_date,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    doc_ref.set(data, merge=True)
    logger.info("Control document updated: last_loaded_date=%s", last_date)
