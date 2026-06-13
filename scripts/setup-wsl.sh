#!/usr/bin/env bash
# Ubuntu (WSL) içinde çalıştırın:
#   bash "/mnt/c/Users/bilgin.cavus/OneDrive - Sanko Holding/Desktop/CLAUDE CODE PROJECT/Kitap Yazma/scripts/setup-wsl.sh"
# Docker Engine kurar, projeyi başlatır, migration + testleri çalıştırır.
# sudo parolanızı bir kez soracaktır.
set -e

PROJ="/mnt/c/Users/bilgin.cavus/OneDrive - Sanko Holding/Desktop/CLAUDE CODE PROJECT/Kitap Yazma"

echo ">>> [1/6] Docker Engine kuruluyor (get.docker.com)..."
if ! command -v docker >/dev/null 2>&1; then
    curl -fsSL https://get.docker.com | sudo sh
fi
sudo usermod -aG docker "$USER" || true

echo ">>> [2/6] Docker servisi başlatılıyor..."
sudo service docker start 2>/dev/null || sudo systemctl start docker 2>/dev/null || true
sudo docker version

echo ">>> [3/6] Projeye geçiliyor: $PROJ"
cd "$PROJ"
[ -f .env ] || cp .env.example .env

echo ">>> [4/6] PostgreSQL (pgvector) başlatılıyor..."
sudo docker compose up -d postgres
sleep 5

echo ">>> [5/6] API imajı kuruluyor + migration (kitap_db)..."
sudo docker compose build api
sudo docker compose run --rm api alembic upgrade head

echo ">>> [6/6] Testler (kitap_test) çalıştırılıyor..."
sudo docker compose run --rm api pytest

echo ">>> BİTTİ. API'yi açmak için: sudo docker compose up -d api && curl http://localhost:8000/health"
