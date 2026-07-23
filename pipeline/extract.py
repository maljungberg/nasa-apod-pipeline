"""
Extraction module for the NASA APOD API.
Implements retries with exponential backoff and error handling.
"""

import os
import time
import logging
from typing import List, Dict, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

# Default configuration
BASE_URL = "https://api.nasa.gov/planetary/apod"
MAX_RETRIES = 5
BACKOFF_FACTOR = 2  # segundos: 2, 4, 8, 16, 32
TIMEOUT = 15  # segundos para conectar y leer


def _get_api_key() -> str:
    """
    Retrieve the API key from the environment variable.
    On a local machine, it is loaded from .env; on Cloud Run, it is injected directly.
    """
    key = os.environ.get("NASA_API_KEY")
    if not key:
        raise RuntimeError(
            "NASA_API_KEY not found. Make sure to define the environment variable "
            "or load it from a .env file."
        )
    return key


def _build_session() -> requests.Session:
    """
    Create a requests session with retries at the connection level (urllib3).
    This covers transient network errors before reaching the application backoff.
    """
    session = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def fetch_apod_range(
    start_date: str,
    end_date: str,
    thumbs: bool = True
) -> List[Dict]:
    """
    Fetches APOD images between start_date and end_date (inclusive).

    Args:
        start_date: Start date in 'YYYY-MM-DD' format.
        end_date: End date in 'YYYY-MM-DD' format.
        thumbs: Request thumbnails for videos (always True in our pipeline).

    Returns:
        List of raw dictionaries as returned by the API.

    Raises:
        RuntimeError: If all retries are exhausted without success.
        ValueError: If the API responds with a parameter error (400).
    """
    api_key = _get_api_key()
    params = {
        "api_key": api_key,
        "start_date": start_date,
        "end_date": end_date,
        "thumbs": str(thumbs).lower()
    }

    session = _build_session()

    last_exception: Optional[Exception] = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(
                "Calling NASA APOD: %s to %s (attempt %d/%d)",
                start_date, end_date, attempt, MAX_RETRIES
            )
            response = session.get(BASE_URL, params=params, timeout=TIMEOUT)

            # Client errors that are not retried
            if response.status_code == 400:
                raise ValueError(f"Invalid parameters: {response.text}")
            if response.status_code == 403:
                raise RuntimeError(f"Invalid API key or API key without permissions: {response.text}")

            # Server errors that are retried
            if response.status_code >= 500:
                raise requests.exceptions.HTTPError(
                    f"Server error {response.status_code}: {response.text}",
                    response=response
                )

            response.raise_for_status()

            data = response.json()
            # If the range returns a single day, the API returns a dict, not a list
            if isinstance(data, dict):
                data = [data]

            logger.info("Fetched %d records.", len(data))
            return data

        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.HTTPError) as e:
            last_exception = e
            if attempt < MAX_RETRIES:
                wait = BACKOFF_FACTOR ** attempt
                logger.warning(
                    "Error in attempt %d: %s. Retrying in %d seconds...",
                    attempt, e, wait
                )
                time.sleep(wait)
            else:
                logger.error("We have used up all %d retry attempts.", MAX_RETRIES)

        except Exception as e:
            # Unexpected errors are not retried
            logger.error("Unexpected error: %s", e)
            raise

    raise RuntimeError(
        f"Data could not be retrieved from the API after {MAX_RETRIES} attempts. "
        f"Last error: {last_exception}"
    )