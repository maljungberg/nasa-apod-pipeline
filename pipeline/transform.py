"""
Transformation module for NASA APOD data.
Maps raw API records to the Firestore schema.
"""

import re
import html
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


def clean_copyright(raw: Optional[str]) -> str:
    """
    Cleans the copyright field.

    Rules:
    - If it is None or empty, returns "".
    - If it contains '\n\nText:', cuts before that string (prioritizes the artist's name).
    - Removes line breaks and unifies spaces.
    - If after cleaning it remains "Public Domain", it is preserved.
    """
    if not raw:
        return ""

    text_split = raw.split("\n\nText:")
    # If there is nothing before "Text:", we take what follows
    if len(text_split) > 1 and not text_split[0].strip():
        cleaned = text_split[1]
    else:
        cleaned = text_split[0]

    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def clean_explanation(raw: str) -> str:
    """
    Cleans the explanation field.

    Rules:
    - Decodes HTML entities (&amp;, &lt;, etc.).
    - Replaces <br> and <p> tags with line breaks.
    - Normalizes multiple spaces and redundant line breaks.
    """
    # Decode HTML entities
    text = html.unescape(raw)

    # Replace <br> and <br/> with \n
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)

    # Replace <p> and </p> with \n
    text = re.sub(r"</?p[^>]*>", "\n", text, flags=re.IGNORECASE)

    # Remove any other residual HTML tags
    text = re.sub(r"<[^>]+>", "", text)

    # Normalize spaces: don't collapse line breaks between paragraphs
    # First we unify spaces within each line
    lines = text.split("\n")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in lines]
    # Eliminate multiple empty lines (leave at most one empty line between paragraphs)
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
    Takes a raw API dictionary and returns a cleaned-up dictionary
    ready to be inserted into Firestore.

    Args:
        record: Dictionary containing the API fields.

    Returns:
        Dictionary with the normalized fields: date, title, explanation,
        url, hdurl, media_type, copyright, thumbnail_url, load_timestamp.
    """
    # Required fields
    date = record.get("date", "")
    title = record.get("title", "").strip()
    media_type = record.get("media_type", "image")

    # Optional fields with cleaning
    explanation = clean_explanation(record.get("explanation", ""))
    url = record.get("url", "")
    hdurl = record.get("hdurl", "") or ""  # if it's None, we put an empty string
    copyright_raw = record.get("copyright")  # might not exist
    copyright_clean = clean_copyright(copyright_raw)

    # Required fields: Thumbnail—only required if `thumbs=True` and the day is a video
    thumbnail_url = record.get("thumbnail_url", "") or ""
    # Upload timestamp in UTC
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
    Applies clean_record to a list of raw records.
    Filters out records that don't have a 'date' (extreme case).
    """
    cleaned = []
    for rec in records:
        if not rec.get("date"):
            logger.warning("Record without date found, skipping: %s", rec)
            continue
        cleaned.append(clean_record(rec))
    logger.info("Transformed %d records successfully.", len(cleaned))
    return cleaned
