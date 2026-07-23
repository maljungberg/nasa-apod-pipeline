FROM python:3.11-slim

WORKDIR /app

# Copy requirements.txt from pipeline/
COPY pipeline/requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy all content from pipeline/ to /app (but respecting the structure)
# We want the files to be in /app/pipeline/ and also main.py to be in pipeline/
COPY pipeline/ pipeline/

# Set PYTHONPATH so that /app is recognised as a package directory
ENV PYTHONPATH=/app

# Port
ENV PORT=8080

# Entry point: Gunicorn looks for the `pipeline.main` module and, within it, the 'app' variable
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 pipeline.main:app