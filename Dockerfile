FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# WeasyPrint (PDF) ve diğer sistem bağımlılıkları.
# WeasyPrint native Windows'ta sorunlu olduğundan tüm üretim/çalıştırma Docker içinde yapılır.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libcairo2 \
        libgdk-pixbuf-2.0-0 \
        libffi-dev \
        shared-mime-info \
        fonts-dejavu-core \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

EXPOSE 8000

# Varsayılan komut API; worker/flower servisleri docker-compose'da override edilir.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
