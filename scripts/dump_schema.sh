#!/usr/bin/env bash
# Alembic migration uygulanmış bir veritabanından şema dökümü üretir.
# Tek doğruluk kaynağı Alembic'tir; migration.sql elle DÜZENLENMEZ (Spec Bölüm 5.5).
set -euo pipefail

: "${PGHOST:=localhost}"
: "${PGUSER:=postgres}"
: "${PGDATABASE:=kitap_db}"

pg_dump --schema-only --no-owner --no-privileges \
    -h "$PGHOST" -U "$PGUSER" "$PGDATABASE" > migration.sql

echo "migration.sql guncellendi ($PGDATABASE)."
