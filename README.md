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

## Gerçek LLM üretimi (Aşama 6+)

Bölüm üretimi gerçek **Anthropic Claude** (streaming) ve embedding için **OpenAI/Voyage** kullanır.
CI testleri bu istemcileri **mock'lar** (gerçek API çağrısı/maliyet yok). Gerçek üretim için `.env`'e
anahtarları girip worker'ı çalıştırın:

    ANTHROPIC_API_KEY=sk-ant-...
    OPENAI_API_KEY=sk-...            # EMBEDDING_PROVIDER=openai için
    CELERY_TASK_ALWAYS_EAGER=false

    docker compose up -d postgres redis minio api worker_gen
    # POST /api/v1/projects/{id}/chapters/{ch_id}/generate ile üret
    # ws://localhost:8000/api/v1/ws/projects/{id}?token=... ile ilerlemeyi izle

Anthropic anahtarı yoksa üretim görevi hata verip dead-letter'a düşer; embedding anahtarı yoksa
semantik hafıza zarifçe devre dışı kalır (order_index fallback'i).

## Notlar

- Şemanın tek doğruluk kaynağı Alembic'tir; `migration.sql` `scripts/dump_schema.sh` ile üretilir.
- Worker/Flower servisleri Aşama 5'te (Celery) devreye girer; Aşama 1-3 için `postgres` + `api` yeterlidir.
