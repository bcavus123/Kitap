# Kitap Yazma Yazılımı

Yapay zeka destekli, Amazon KDP uyumlu akademik kitap yazma backend'i.
Tam spesifikasyon: [`PROJE_SPEC.md`](PROJE_SPEC.md) (v2.1).

## Durum

| Aşama | Kapsam | Durum |
|---|---|---|
| 1 | Altyapı (config, modeller, migration, Docker) | ✅ kod |
| 2 | Auth (JWT, refresh+jti, API key, plan limitleri) | ✅ kod |
| 3 | Projects (CRUD, settings, progress, pause/resume) | ✅ kod |
| 4 | Chapters (TOC, generate, versioning) | ⏳ sırada |
| 5–8 | Celery/WS, LLM, çıktı (DOCX/PDF/EPUB), izleme | ⏳ |

Geliştirme sırası: `PROJE_SPEC.md` Bölüm 16.

## Teknoloji

FastAPI (async) · SQLAlchemy 2.0 · PostgreSQL + pgvector · Alembic · Celery/Redis · MinIO · JWT · WeasyPrint/python-docx/ebooklib

## Test — GitHub Actions

Her push'ta [`.github/workflows/ci.yml`](.github/workflows/ci.yml) test paketini (auth + projects, 20 test) `pgvector/pgvector:pg15` servis konteyneriyle bulutta çalıştırır. Yerel kurulum gerekmez.

## Docker ile çalıştırma (Codespaces veya Docker olan herhangi bir Linux)

```bash
cp .env.example .env
docker compose up -d postgres
docker compose run --rm api alembic upgrade head   # şema + trigger + view
docker compose run --rm api pytest                 # testler
docker compose up -d api                            # http://localhost:8000/docs
```

**GitHub Codespaces:** Depoyu Codespace olarak açın (`.devcontainer` Docker'ı sağlar), ardından yukarıdaki komutları terminalde çalıştırın.

## Notlar

- Şemanın tek doğruluk kaynağı Alembic'tir; `migration.sql` `scripts/dump_schema.sh` ile üretilir.
- Worker/Flower servisleri Aşama 5'te (Celery) devreye girer; Aşama 1-3 için `postgres` + `api` yeterlidir.
