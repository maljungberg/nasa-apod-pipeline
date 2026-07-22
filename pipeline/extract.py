"""
Módulo de extracción para la API NASA APOD.
Implementa reintentos con backoff exponencial y manejo de errores.
"""

import os
import time
import logging
from typing import List, Dict, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

# Configuración por defecto
BASE_URL = "https://api.nasa.gov/planetary/apod"
MAX_RETRIES = 5
BACKOFF_FACTOR = 2  # segundos: 2, 4, 8, 16, 32
TIMEOUT = 15  # segundos para conectar y leer


def _get_api_key() -> str:
    """
    Recupera la API key de la variable de entorno.
    En local se carga desde .env; en Cloud Run se inyecta directamente.
    """
    key = os.environ.get("NASA_API_KEY")
    if not key:
        raise RuntimeError(
            "NASA_API_KEY no encontrada. Asegurate de definir la variable de entorno "
            "o cargarla desde un archivo .env."
        )
    return key


def _build_session() -> requests.Session:
    """
    Crea una sesión de requests con reintentos a nivel de conexión (urllib3).
    Esto cubre errores transitorios de red antes de llegar al backoff de aplicación.
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
    Obtiene los APOD entre start_date y end_date (inclusive).

    Args:
        start_date: Fecha inicio en formato 'YYYY-MM-DD'.
        end_date: Fecha fin en formato 'YYYY-MM-DD'.
        thumbs: Solicitar thumbnails para videos (siempre True en nuestro pipeline).

    Returns:
        Lista de diccionarios crudos tal como los devuelve la API.

    Raises:
        RuntimeError: Si se agotan los reintentos sin éxito.
        ValueError: Si la API responde con error de parámetros (400).
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
                "Llamada a NASA APOD: %s a %s (intento %d/%d)",
                start_date, end_date, attempt, MAX_RETRIES
            )
            response = session.get(BASE_URL, params=params, timeout=TIMEOUT)

            # Errores de cliente que no se reintentan
            if response.status_code == 400:
                raise ValueError(f"Parámetros inválidos: {response.text}")
            if response.status_code == 403:
                raise RuntimeError(f"API key inválida o sin permisos: {response.text}")

            # Errores de servidor que se reintentan
            if response.status_code >= 500:
                raise requests.exceptions.HTTPError(
                    f"Error de servidor {response.status_code}: {response.text}",
                    response=response
                )

            response.raise_for_status()

            data = response.json()
            # Si el rango devuelve un solo día, la API da un dict, no una lista
            if isinstance(data, dict):
                data = [data]

            logger.info("Obtenidos %d registros.", len(data))
            return data

        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.HTTPError) as e:
            last_exception = e
            if attempt < MAX_RETRIES:
                wait = BACKOFF_FACTOR ** attempt
                logger.warning(
                    "Error en intento %d: %s. Reintentando en %d segundos...",
                    attempt, e, wait
                )
                time.sleep(wait)
            else:
                logger.error("Agotados los %d reintentos.", MAX_RETRIES)

        except Exception as e:
            # Errores inesperados no se reintentan
            logger.error("Error inesperado: %s", e)
            raise

    raise RuntimeError(
        f"No se pudo obtener datos de la API después de {MAX_RETRIES} intentos. "
        f"Último error: {last_exception}"
    )