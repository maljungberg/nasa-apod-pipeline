"""
Features: logging, sending error emails.
"""

import logging
import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail


def setup_logging():
    """Configures structured logging for Cloud Logging."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )


def send_failure_email(error_message: str):
    """
    Sends a failure alert email using SendGrid.
    The environment variables SENDGRID_API_KEY, TO_EMAIL and FROM_EMAIL must be defined.
    """
    api_key = os.environ.get("SENDGRID_API_KEY")
    to_email = os.environ.get("TO_EMAIL")
    from_email = os.environ.get("FROM_EMAIL", "apod-pipeline@example.com")

    if not api_key or not to_email:
        logging.warning("SendGrid not configured. Skipping email sending.")
        return

    message = Mail(
        from_email=from_email,
        to_emails=to_email,
        subject="Failure in NASA APOD pipeline",
        plain_text_content=f"The pipeline failed with the following error:\n\n{error_message}",
    )
    try:
        sg = SendGridAPIClient(api_key)
        sg.send(message)
        logging.info("Failure email sent to %s", to_email)
    except Exception as e:
        logging.error("Error sending email: %s", e)
