"""
Entry point for Cloud Run with Flask.
Orchestrates the weekly extraction or initial historical data backfill
of NASA's APOD.
"""

import os
import logging
from datetime import datetime, timedelta, timezone

from flask import Flask, request

from pipeline.extract import fetch_apod_range
from pipeline.transform import transform_all
from pipeline.load import load_records, get_last_loaded_date, update_control_date
from pipeline.utils import send_failure_email, setup_logging

# Configure Structured Logging
setup_logging()
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Start date for the historical backfill
BACKFILL_START_DATE = "2020-01-01"
# Size of block in days for backfill (respectful of the API)
BACKFILL_BLOCK_DAYS = 7


def run_backfill():
    """
    Executes the historical load from BACKFILL_START_DATE to yesterday,
    in blocks of BACKFILL_BLOCK_DAYS days.
    """
    logger.info("Starting backfill from %s", BACKFILL_START_DATE)
    today = datetime.now(timezone.utc).date()
    end_date = today - timedelta(days=1)  # until yesterday

    current_start = datetime.strptime(BACKFILL_START_DATE, "%Y-%m-%d").date()
    while current_start <= end_date:
        block_end = min(current_start + timedelta(days=BACKFILL_BLOCK_DAYS - 1), end_date)
        start_str = current_start.isoformat()
        end_str = block_end.isoformat()
        logger.info("Backfill block: %s -> %s", start_str, end_str)

        try:
            raw = fetch_apod_range(start_str, end_str)
            if raw:
                cleaned = transform_all(raw)
                loaded = load_records(cleaned)
                logger.info("Block loaded: %d records", loaded)
            # Update control with the final date of the block
            update_control_date(end_str)
        except Exception as e:
            logger.error("Error in backfill block %s-%s: %s", start_str, end_str, e)
            send_failure_email(f"Backfill failed in block {start_str}-{end_str}: {e}")
            raise  # stop backfill; the scheduler will retry later

        current_start = block_end + timedelta(days=1)

    logger.info("Backfill completed until %s", end_date.isoformat())


def run_incremental():
    """
    Executes the weekly load from the last loaded date until yesterday.
    """
    last_date = get_last_loaded_date()
    if not last_date:
        logger.info("Control empty, starting backfill instead.")
        run_backfill()
        return

    today = datetime.now(timezone.utc).date()
    start_date = last_date  # inclusive, solapamiento
    end_date = (today - timedelta(days=1)).isoformat()  # until yesterday inclusive

    logger.info("Incremental: %s -> %s", start_date, end_date)

    raw = fetch_apod_range(start_date, end_date)
    if not raw:
        logger.info("No new APOD found in the range.")
        return

    cleaned = transform_all(raw)
    loaded = load_records(cleaned)
    logger.info("Incremental loaded: %d records", loaded)

    # Update control to the final date of the range (the maximum loaded)
    if cleaned:
        max_date = max(r["date"] for r in cleaned)
        update_control_date(max_date)
    else:
        update_control_date(end_date)


@app.route("/", methods=["POST"])
def execute_pipeline():
    """Endpoint that Cloud Scheduler will invoke via POST."""
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


# For local development (optional)
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))