FROM python:3.11-slim

WORKDIR /app

# Copiar requirements.txt desde pipeline/
COPY pipeline/requirements.txt .

# Instalar dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Copiar todo el contenido de pipeline/ a /app (pero respetando la estructura)
# Queremos que los archivos queden en /app/pipeline/ y también que main.py esté en pipeline/
COPY pipeline/ pipeline/

# Ajustar PYTHONPATH para que /app sea reconocido como directorio de paquetes
ENV PYTHONPATH=/app

# Puerto
ENV PORT=8080

# Entrypoint: gunicorn busca el módulo pipeline.main y dentro de él la variable 'app'
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 pipeline.main:app