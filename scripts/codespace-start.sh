#!/usr/bin/env bash
# Codespace test ortamını ayağa kaldırır: Postgres + Redis + MinIO + şema + API.
# Codespace açılışında devcontainer tarafından OTOMATİK çalışır; gerekirse elle de çalıştırılır:
#   bash scripts/codespace-start.sh
set -e
cd "$(dirname "$0")/.."

[ -f .env ] || cp .env.example .env

echo ">>> [1/3] Servisler başlatılıyor (postgres, redis, minio)..."
docker compose up -d postgres redis minio
sleep 6

echo ">>> [2/3] API imajı kuruluyor + şema uygulanıyor (alembic upgrade head)..."
docker compose run --rm api alembic upgrade head

echo ">>> [3/3] API başlatılıyor (port 8000)..."
docker compose up -d api

cat <<'MSG'

============================================================
✅ TEST ORTAMI HAZIR
   1) Alttaki "PORTS" sekmesinde 8000 satırına sağ tık
      -> Port Visibility -> Public
   2) 8000'in "Forwarded Address" URL'sine /docs ekleyip açın
      (örn. https://....-8000.app.github.dev/docs)  -> Swagger
   3) O URL'yi Claude'a yapıştırın; gerisini o test eder.
============================================================
MSG
