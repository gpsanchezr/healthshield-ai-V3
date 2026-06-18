FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    postgresql-client libpq-dev gcc \
    pkg-config default-libmysqlclient-dev build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .

# 👇 ESTA ES LA LÍNEA NUEVA QUE SOLUCIONA EL ERROR DE WINDOWS 👇
RUN sed -i 's/\r$//' requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .
COPY datasets/ ./datasets/

RUN mkdir -p ml_models staticfiles media

EXPOSE 8000