"""
Módulo de transformación para datos NASA APOD.
Normaliza registros crudos de la API al esquema de Firestore.
"""

import re
import html
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

def clean_copyright(raw: Optional[str]) -> str:
    """
    Limpia el campo copyright.

    Reglas:
    - Si es None o vacío, devuelve "".
    - Si contiene '\n\nText:', corta antes de esa cadena (prioriza el nombre del artista).
    - Elimina saltos de línea y unifica espacios.
    - Si después de limpiar queda "Public Domain", se conserva.
    """
    if not raw:
        return ""

    text_split = raw.split("\n\nText:")
    # Si no hay nada antes de "Text:", tomamos lo que sigue
    if len(text_split) > 1 and not text_split[0].strip():
        cleaned = text_split[1]
    else:
        cleaned = text_split[0]

    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def clean_explanation(raw: str) -> str:
    """
    Limpia el campo explanation.

    Reglas:
    - Decodifica entidades HTML (&amp;, &lt;, etc.).
    - Reemplaza tags <br> y <p> por saltos de línea.
    - Normaliza espacios múltiples y saltos de línea redundantes.
    """
    # Decodificar entidades HTML
    text = html.unescape(raw)

    # Reemplazar <br> y <br/> por \n
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)

    # Reemplazar <p> y </p> por \n
    text = re.sub(r"</?p[^>]*>", "\n", text, flags=re.IGNORECASE)

    # Eliminar cualquier otro tag HTML residual
    text = re.sub(r"<[^>]+>", "", text)

    # Normalizar espacios: no colapsar saltos de línea entre párrafos
    # Primero unificamos espacios dentro de cada línea
    lines = text.split("\n")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in lines]
    # Eliminar líneas vacías múltiples (dejar máximo una línea vacía entre párrafos)
    clean_lines = []
    prev_empty = False
    for line in lines:
        if line == "":
            if not prev_empty:
                clean_lines.append(line)
            prev_empty = True
        else:
            clean_lines.append(line)
            prev_empty = False

    return "\n".join(clean_lines).strip()


def clean_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Toma un diccionario crudo de la API y devuelve un diccionario limpio
    listo para insertar en Firestore.

    Args:
        record: Diccionario con los campos de la API.

    Returns:
        Diccionario con los campos normalizados: date, title, explanation,
        url, hdurl, media_type, copyright, thumbnail_url, load_timestamp.
    """
    # Campos obligatorios
    date = record.get("date", "")
    title = record.get("title", "").strip()
    media_type = record.get("media_type", "image")

    # Campos opcionales con limpieza
    explanation = clean_explanation(record.get("explanation", ""))
    url = record.get("url", "")
    hdurl = record.get("hdurl", "") or ""  # si es None, ponemos ""
    copyright_raw = record.get("copyright")  # puede no existir
    copyright_clean = clean_copyright(copyright_raw)

    # Thumbnail: solo presente si thumbs=True y el día es video
    thumbnail_url = record.get("thumbnail_url", "") or ""
    # Timestamp de carga en UTC
    load_timestamp = datetime.now(timezone.utc).isoformat()

    cleaned = {
        "date": date,
        "title": title,
        "explanation": explanation,
        "url": url,
        "hdurl": hdurl,
        "media_type": media_type,
        "copyright": copyright_clean,
        "thumbnail_url": thumbnail_url,
        "load_timestamp": load_timestamp,
    }

    return cleaned


def transform_all(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Aplica clean_record a una lista de registros crudos.
    Filtra registros que no tengan 'date' (caso extremo).
    """
    cleaned = []
    for rec in records:
        if not rec.get("date"):
            logger.warning("Registro sin fecha encontrado, se omite: %s", rec)
            continue
        cleaned.append(clean_record(rec))
    logger.info("Transformados %d registros exitosamente.", len(cleaned))
    return cleaned