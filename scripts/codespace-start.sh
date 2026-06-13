#!/usr/bin/env bash
# Codespace test ortamını ayağa kaldırır:
#   1) Frontend (React/Vite) build  -> app/web
#   2) Postgres + Redis + MinIO
#   3) Şema (alembic upgrade head)
#   4) API (app/web'i /app/ altında sunar)
# Codespace açılışında devcontainer tarafından OTOMATİK çalışır; elle de: bash scripts/codespace-start.sh
set -e
cd "$(dirname "$0")/.."

[ -f .env ] || cp .env.example .env

echo ">>> [1/4] Frontend (SPA) build ediliyor -> app/web ..."
( cd frontend && npm install && npm run build ) || echo "UYARI: frontend build atlandi (node yok?). Arayuz olmadan devam."

echo ">>> [2/4] Servisler (postgres, redis, minio)..."
docker compose up -d postgres redis minio
sleep 6

echo ">>> [3/4] API imajı + şema (alembic upgrade head)..."
docker compose run --rm api alembic upgrade head

echo ">>> [4/4] API başlatılıyor (port 8000)..."
docker compose up -d api

cat <<'MSG'

============================================================
✅ TEST ORTAMI HAZIR
   1) PORTS sekmesinde 8000 -> sağ tık -> Port Visibility -> Public
   2) 8000 Forwarded Address URL'sini açın -> React arayüz (/app/)
      (Swagger: aynı URL + /docs)
============================================================
MSG
