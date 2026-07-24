"""
Features: logging, sending error emails.
"""

import logging
import os
import requests


logger = logging.getLogger(__name__)


def send_failure_notification(error_message: str):
    """
    Send a notification to Slack when the pipeline fails.
    The webhook URL is retrieved from the SLACK_WEBHOOK_URL environment variable
    (provided by Secret Manager).
    """
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook_url:
        logger.warning("SLACK_WEBHOOK_URL not configured. Notification omitted.")
        return

    payload = {
        "text": f"❌ *Failure in the NASA APOD Pipeline*\n\n```{error_message}```"
    }

    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        response.raise_for_status()
        logger.info("Failure notification sent to Slack.")
    except Exception as e:
        logger.error("Error sending notification to Slack: %s", e)
