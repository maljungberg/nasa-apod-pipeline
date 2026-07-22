"""
Utilidades: logging, envío de emails de fallo.
"""

import logging
import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail


def setup_logging():
    """Configura logging estructurado para Cloud Logging."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )


def send_failure_email(error_message: str):
    """
    Envía un email de alerta usando SendGrid.
    Las variables de entorno SENDGRID_API_KEY, TO_EMAIL y FROM_EMAIL deben estar definidas.
    """
    api_key = os.environ.get("SENDGRID_API_KEY")
    to_email = os.environ.get("TO_EMAIL")
    from_email = os.environ.get("FROM_EMAIL", "apod-pipeline@example.com")

    if not api_key or not to_email:
        logging.warning("SendGrid no configurado. Se omite envío de email.")
        return

    message = Mail(
        from_email=from_email,
        to_emails=to_email,
        subject="Fallo en pipeline NASA APOD",
        plain_text_content=f"El pipeline falló con el siguiente error:\n\n{error_message}",
    )
    try:
        sg = SendGridAPIClient(api_key)
        sg.send(message)
        logging.info("Email de fallo enviado a %s", to_email)
    except Exception as e:
        logging.error("Error enviando email: %s", e)