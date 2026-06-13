# Kitap Yazma Yazılımı — Tam Proje Spesifikasyonu

> **Sürüm: 2.1** — Bu doküman Claude Code ile geliştirme yapılacak projenin tüm özelliklerini, mimarisini, veritabanı şemasını, API endpoint'lerini, Celery görev akışını ve geliştirme sırasını kapsar.
>
> 📌 **Sürüm geçmişi ve değişiklikler dokümanın sonundaki [Bölüm 22 — Revizyon Notları](#22-revizyon-notları)'nda listelenmiştir.** v2.0'da embedding sağlayıcısı, EPUB, WebSocket auth, refresh token iptali ve dead-letter yönetimi eklendi; **v2.1'de iç tutarlılık taramasıyla** versiyonlama, plan enforcement, LLM ayar önceliği, pause/resume ve birkaç şema uyumsuzluğu giderildi.

---

## 1. Proje Özeti

Amazon KDP (Kindle Direct Publishing) standartlarında çıktı üreten, yapay zeka destekli, 7/24 çalışan akademik kitap yazma yazılımı.

**Temel özellikler:**
- Kullanıcı içindekiler tablosunu yükler → sistem her bölümü otomatik yazar
- Tam akademik yazar profili: atıflar, dipnotlar, tablolar, görseller
- KDP uyumlu DOCX, PDF ve EPUB çıktısı (6×9, 5×8, 7×10, 8.5×11 sayfa boyutları)
- Bölümler arası tutarlılık için semantik hafıza (pgvector)
- Celery ile asenkron görev kuyruğu, exponential backoff retry
- WebSocket ile gerçek zamanlı ilerleme bildirimleri

---

## 2. Teknoloji Yığını

| Katman | Teknoloji |
|---|---|
| Backend API | FastAPI (async) |
| Veritabanı | PostgreSQL 15+ + pgvector extension |
| ORM | SQLAlchemy 2.0 async |
| Migration | Alembic (**tek doğruluk kaynağı** — bkz. Bölüm 5.5) |
| Görev kuyruğu | Celery 5 + Redis 7 |
| Üretim LLM'i | Anthropic Claude API (claude-sonnet-4-6) |
| **Embedding** | **OpenAI `text-embedding-3-small` (1536) veya Voyage AI `voyage-3` (1024) — yapılandırılabilir** |
| Dosya depolama | MinIO (S3-uyumlu) |
| Kimlik doğrulama | JWT (python-jose + bcrypt) |
| DOCX üretimi | python-docx |
| PDF üretimi | WeasyPrint |
| **EPUB üretimi** | **ebooklib** (+ `markdown` HTML dönüşümü için) |
| WebSocket | FastAPI WebSocket + Redis pub/sub |
| Konteyner | Docker + Docker Compose |
| Test | pytest + pytest-asyncio + httpx |

> **Not (LLM sağlayıcı ayrımı):** Bölüm *üretimi* Anthropic Claude ile yapılır; ancak Claude'un embedding API'si yoktur. Bu nedenle **semantik hafıza için ayrı bir embedding sağlayıcısı** (OpenAI veya Voyage AI) gerekir. İki ayrı API anahtarı (`ANTHROPIC_API_KEY` + embedding sağlayıcı anahtarı) konfigüre edilmelidir.

---

## 3. Proje Dizin Yapısı

```
kitap_yazilimi/
├── app/
│   ├── __init__.py
│   ├── main.py                        # FastAPI app, lifespan, router kayıtları, CORS
│   ├── api/
│   │   └── v1/
│   │       └── endpoints/
│   │           ├── auth.py            # register/login/refresh/logout, /me, /api-keys
│   │           ├── projects.py        # CRUD /projects + /settings + /progress + /pause + /resume
│   │           ├── chapters.py        # POST /toc, /generate, /generate-all, PATCH (+versiyon)
│   │           ├── exports.py         # POST /exports (docx/pdf/epub)
│   │           ├── admin.py           # dead-letter listeleme/yeniden tetikleme (admin)
│   │           └── ws.py              # WebSocket /api/v1/ws/projects/{id}
│   ├── core/
│   │   ├── config.py                  # pydantic-settings, .env okuma (CORS, Sentry dahil)
│   │   ├── security.py                # JWT oluştur/doğrula, bcrypt, API key
│   │   └── limits.py                  # plan kotaları: require_plan() / enforce_quota() dependency'leri
│   ├── db/
│   │   └── session.py                 # async engine, AsyncSessionLocal, get_db
│   ├── models/
│   │   └── models.py                  # SQLAlchemy ORM (10 tablo)
│   ├── schemas/
│   │   └── schemas.py                 # Pydantic request/response şemaları
│   ├── services/
│   │   ├── formatter.py               # KDP DOCX/PDF/EPUB üretimi
│   │   ├── versioning.py              # user_edit / regenerate için chapter_versions oluşturma
│   │   ├── embedding_service.py       # Embedding sağlayıcı soyutlaması (OpenAI/Voyage)
│   │   ├── citation_service.py        # CrossRef DOI doğrulama
│   │   └── media_service.py           # Matplotlib grafik üretimi
│   └── tasks/
│       └── celery_app.py              # generate_chapter_task, export_project_task
├── alembic/
│   ├── env.py
│   └── versions/
│       └── 001_initial_schema.py
├── tests/
│   └── test_api.py
├── scripts/
│   └── dump_schema.sh                 # Alembic → migration.sql otomatik dökümü
├── migration.sql                      # OTOMATİK ÜRETİLEN şema dökümü (elle düzenlenmez)
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── alembic.ini
└── .env.example
```

---

## 4. Ortam Değişkenleri (.env)

```env
# Veritabanı
DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/kitap_db
ASYNC_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/kitap_db

# Redis / Celery
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# JWT
SECRET_KEY=<openssl rand -hex 32 ile üret>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# Üretim LLM (Anthropic) — bunlar GLOBAL VARSAYILAN; proje bazında
# project_settings.llm_config bu değerleri EZER (bkz. Bölüm 8.4).
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-sonnet-4-6
ANTHROPIC_MAX_TOKENS=8000
ANTHROPIC_TEMPERATURE=0.5            # Akademik olgu tutarlılığı için düşük; bkz. Bölüm 8.4

# Embedding (semantik hafıza) — bkz. Bölüm 10
SEMANTIC_MEMORY_ENABLED=true         # false → vektör arama yerine order_index fallback
EMBEDDING_PROVIDER=openai            # openai | voyage
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSIONS=1536            # openai:1536 | voyage-3:1024 (DB sütunuyla EŞLEŞMELİ)
OPENAI_API_KEY=sk-...                # EMBEDDING_PROVIDER=openai ise zorunlu
VOYAGE_API_KEY=                      # EMBEDDING_PROVIDER=voyage ise zorunlu (Anthropic önerisi)

# MinIO / S3
S3_ENDPOINT=http://localhost:9000
S3_BUCKET=kitap-yazilimi
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
PRESIGNED_URL_EXPIRE_HOURS=24

# App
APP_ENV=development
DEBUG=true
LOG_LEVEL=INFO
CORS_ORIGINS=http://localhost:3000,http://localhost:5173   # virgülle ayrılmış izinli origin'ler
SENTRY_DSN=                          # boşsa Sentry devre dışı
```

> ⚠️ **`EMBEDDING_DIMENSIONS` ile `chapters.embedding` sütununun boyutu birebir aynı olmalıdır.** Sağlayıcı değiştirilirse (örn. OpenAI 1536 → Voyage 1024) ayrı bir Alembic migration ile sütun boyutu güncellenmeli ve mevcut embedding'ler yeniden hesaplanmalıdır.

---

## 5. Veritabanı Şeması

> **Tablo sayısı: 10** (v1.0'daki 9 tabloya `refresh_tokens` eklendi; `users` tablosuna `role` ve API anahtarı meta sütunları eklendi.)

### 5.1 Tablolar

#### `users`
```sql
id                 UUID PK DEFAULT gen_random_uuid()
email              VARCHAR(255) NOT NULL UNIQUE
password_hash      VARCHAR(255) NOT NULL
full_name          VARCHAR(200) NOT NULL
role               VARCHAR(20)  DEFAULT 'user'   -- user | admin (admin: dead-letter yönetimi)
plan               VARCHAR(20)  DEFAULT 'free'   -- free | pro | enterprise
api_key_hash       VARCHAR(255) UNIQUE           -- programatik erişim için (opsiyonel)
api_key_prefix     VARCHAR(12)                   -- gösterim için (örn. "kp_a1b2...")
api_key_created_at TIMESTAMPTZ
is_active          BOOLEAN DEFAULT true
email_verified     BOOLEAN DEFAULT false
created_at         TIMESTAMPTZ DEFAULT now()
updated_at         TIMESTAMPTZ DEFAULT now()
last_login_at      TIMESTAMPTZ
```

#### `refresh_tokens` *(token iptali/çıkış için)*
```sql
id           UUID PK DEFAULT gen_random_uuid()
user_id      UUID FK → users(id) ON DELETE CASCADE
jti          VARCHAR(64) NOT NULL UNIQUE   -- refresh JWT'nin "jti" claim'i
expires_at   TIMESTAMPTZ NOT NULL
revoked      BOOLEAN DEFAULT false
created_at   TIMESTAMPTZ DEFAULT now()
revoked_at   TIMESTAMPTZ
user_agent   VARCHAR(300)                  -- oturum izleme (opsiyonel)
```
> Refresh token *stateless* JWT olarak üretilir ama `jti` bu tabloda tutulur. `/auth/refresh` çağrısında `jti` aranır; `revoked=true` veya kayıt yoksa **401** döner. `/auth/logout` ilgili `jti`'yi (veya tüm oturumları) `revoked=true` yapar.

#### `projects`
```sql
id                  UUID PK DEFAULT gen_random_uuid()
user_id             UUID FK → users(id) ON DELETE CASCADE
title               VARCHAR(500) NOT NULL
subtitle            VARCHAR(500)
genre               VARCHAR(100)
kdp_format          VARCHAR(20) DEFAULT '6x9'   -- 5x8 | 6x9 | 7x10 | 8.5x11
citation_style      VARCHAR(20) DEFAULT 'APA'   -- APA | Chicago | MLA | Vancouver | Harvard
language            VARCHAR(10) DEFAULT 'tr'
status              VARCHAR(20) DEFAULT 'draft' -- draft | generating | paused | done | error
target_word_count   INTEGER DEFAULT 50000
total_word_count    INTEGER DEFAULT 0            -- trigger ile otomatik güncellenir
chapter_count       SMALLINT DEFAULT 0           -- trigger ile otomatik güncellenir
created_at          TIMESTAMPTZ DEFAULT now()
updated_at          TIMESTAMPTZ DEFAULT now()
```
> `status` geçişleri: `draft → generating` (generate-all), `generating → paused` (POST /pause), `paused → generating` (POST /resume), `generating → done` (tüm bölümler done), `* → error`. Pause/resume endpoint'leri Bölüm 6.2'de tanımlıdır.

#### `project_settings`
```sql
id                  UUID PK DEFAULT gen_random_uuid()
project_id          UUID FK → projects(id) ON DELETE CASCADE UNIQUE  -- 1-1 ilişki
tone_profile        VARCHAR(50) DEFAULT 'academic'  -- academic | formal | narrative | technical | popular
audience_level      VARCHAR(50) DEFAULT 'graduate'  -- undergraduate | graduate | expert | general
academic_field      VARCHAR(100)                    -- Mühendislik, Tıp, Hukuk...
human_writing_mode  BOOLEAN DEFAULT true            -- doğal/insansı düzyazı stili (bkz. Bölüm 8.3 + sorumlu kullanım notu)
style_overrides     JSONB DEFAULT '{}'
llm_config          JSONB DEFAULT '{"model":"claude-sonnet-4-6","temperature":0.5,"max_tokens":8000}'  -- .env varsayılanlarını EZER
created_at          TIMESTAMPTZ DEFAULT now()
updated_at          TIMESTAMPTZ DEFAULT now()
```

#### `chapters`
```sql
id                  UUID PK DEFAULT gen_random_uuid()
project_id          UUID FK → projects(id) ON DELETE CASCADE
order_index         SMALLINT NOT NULL              -- bölüm sırası (1'den başlar)
title               VARCHAR(500) NOT NULL
description         TEXT                           -- içindekiler yüklenirken girilen özet
content             TEXT                           -- üretilen tam markdown içerik
content_summary     TEXT                           -- bağlam hafızası için ~200 kelimelik özet
embedding           VECTOR(1536)                   -- pgvector; boyut EMBEDDING_DIMENSIONS ile eşleşmeli
word_count          INTEGER DEFAULT 0
target_word_count   INTEGER                        -- NULL ise project.target / chapter_count ile hesaplanır
status              VARCHAR(20) DEFAULT 'pending'  -- pending | queued | generating | done | error | skipped
retry_count         SMALLINT DEFAULT 0
generated_at        TIMESTAMPTZ
updated_at          TIMESTAMPTZ DEFAULT now()
UNIQUE(project_id, order_index)
```

#### `chapter_versions`
```sql
id              UUID PK DEFAULT gen_random_uuid()
chapter_id      UUID FK → chapters(id) ON DELETE CASCADE
version_number  SMALLINT NOT NULL                  -- trigger ile otomatik artar
content         TEXT NOT NULL                      -- tam içerik snapshot
change_reason   VARCHAR(50) DEFAULT 'ai_generation' -- ai_generation (trigger) | user_edit (app) | regenerate (app)
token_cost      INTEGER DEFAULT 0
created_at      TIMESTAMPTZ DEFAULT now()
UNIQUE(chapter_id, version_number)
```
> **Versiyon kaynakları (v2.1'de netleşti):** `ai_generation` kayıtları `fn_snapshot_on_done` trigger'ı ile otomatik oluşur. `user_edit` (manuel PATCH) ve `regenerate` (force=true) kayıtları ise **uygulama tarafında** `services/versioning.py` ile oluşturulur (trigger tek başına bu iki durumu yakalayamaz). Detay: Bölüm 5.3 ve Bölüm 7.1.

#### `citations`
```sql
id                  UUID PK DEFAULT gen_random_uuid()
chapter_id          UUID FK → chapters(id) ON DELETE CASCADE
marker              VARCHAR(20) NOT NULL               -- [1], [2], (Smith, 2020)...
doi                 VARCHAR(200)
raw_title           TEXT NOT NULL
authors             TEXT
journal             VARCHAR(300)
pub_year            SMALLINT
publisher           VARCHAR(300)
citation_format     VARCHAR(20) DEFAULT 'APA'
formatted_text      TEXT                               -- hazır kaynakça metni
doi_verified        BOOLEAN DEFAULT false              -- CrossRef ile doğrulandı mı (bkz. Bölüm 9.4)
verification_status VARCHAR(20) DEFAULT 'unverified'   -- unverified | verified | not_found | mismatch
crossref_data       JSONB                              -- CrossRef API ham yanıtı
created_at          TIMESTAMPTZ DEFAULT now()
```

#### `media_assets`
```sql
id              UUID PK DEFAULT gen_random_uuid()
chapter_id      UUID FK → chapters(id) ON DELETE CASCADE
asset_type      VARCHAR(30) NOT NULL               -- image | table | chart | diagram | infographic
s3_path         TEXT NOT NULL
caption         TEXT
alt_text        TEXT
position_index  SMALLINT DEFAULT 0                 -- bölüm içi sıra
width_px        SMALLINT
height_px       SMALLINT
file_size_bytes INTEGER
dpi             SMALLINT DEFAULT 300               -- KDP minimum 300 DPI
created_at      TIMESTAMPTZ DEFAULT now()
```

#### `task_logs`
```sql
id              UUID PK DEFAULT gen_random_uuid()
chapter_id      UUID FK → chapters(id) ON DELETE CASCADE
celery_task_id  VARCHAR(200) NOT NULL UNIQUE
worker_name     VARCHAR(100)
status          VARCHAR(20) DEFAULT 'queued'       -- queued | started | success | failure | retry | revoked
tokens_input    INTEGER DEFAULT 0
tokens_output   INTEGER DEFAULT 0
duration_ms     INTEGER
error_message   TEXT
started_at      TIMESTAMPTZ
finished_at     TIMESTAMPTZ
```

#### `export_jobs`
```sql
id              UUID PK DEFAULT gen_random_uuid()
project_id      UUID FK → projects(id) ON DELETE CASCADE
format          VARCHAR(10) NOT NULL               -- docx | pdf | epub
status          VARCHAR(20) DEFAULT 'pending'      -- pending | processing | done | error
s3_path         TEXT
presigned_url   TEXT
url_expires_at  TIMESTAMPTZ                        -- PRESIGNED_URL_EXPIRE_HOURS kadar geçerli
file_size_bytes INTEGER
error_message   TEXT
created_at      TIMESTAMPTZ DEFAULT now()
finished_at     TIMESTAMPTZ
```

### 5.2 Kritik Indexler

```sql
-- Semantik arama (pgvector HNSW)
CREATE INDEX idx_chapters_embedding_hnsw ON chapters
  USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);

-- Bölüm durumu (partial index — sadece aktif görevler)
CREATE INDEX idx_chapters_status_active ON chapters (status)
  WHERE status NOT IN ('done', 'skipped');

-- Celery idempotency
CREATE UNIQUE INDEX idx_tl_celery_id ON task_logs (celery_task_id);

-- DOI tekrar kontrolü
CREATE INDEX idx_citations_doi ON citations (doi)
  WHERE doi IS NOT NULL;

-- Süresi dolmuş URL temizliği
CREATE INDEX idx_ej_expired_urls ON export_jobs (url_expires_at)
  WHERE presigned_url IS NOT NULL AND url_expires_at IS NOT NULL;

-- Refresh token arama + süresi dolmuş kayıt temizliği
CREATE UNIQUE INDEX idx_rt_jti ON refresh_tokens (jti);
CREATE INDEX idx_rt_expired ON refresh_tokens (expires_at)
  WHERE revoked = false;
```

### 5.3 Triggerlar

```sql
-- 1. updated_at otomatik güncelleme (users, projects, project_settings, chapters)
fn_update_updated_at()

-- 2. projects.total_word_count ve chapter_count otomatik senkron
fn_sync_project_stats()
-- Tetikleyen: chapters INSERT/UPDATE(word_count)/DELETE

-- 3. chapter_versions otomatik version_number artırma
fn_auto_version_number()
-- Tetikleyen: chapter_versions BEFORE INSERT
-- Not: Bu trigger version_number'ı atar; INSERT'i hem trigger hem de uygulama (versioning.py) yapabilir.

-- 4. chapter 'done' olunca otomatik snapshot (SADECE ai_generation)
fn_snapshot_on_done()
-- Tetikleyen: chapters AFTER UPDATE OF status
-- Koşul: NEW.status = 'done' AND OLD.status != 'done' AND content IS NOT NULL
-- change_reason = 'ai_generation' (default)
```

> **Versiyonlama sorumluluk dağılımı (v2.1):**
> - **`ai_generation`** → `fn_snapshot_on_done` trigger'ı otomatik üretir (LLM üretimi tamamlanıp status `done` olunca).
> - **`user_edit`** → Kullanıcı `PATCH /chapters/{id}` ile `content` güncellediğinde status değişmez, trigger tetiklenmez. Bu nedenle `services/versioning.py` PATCH öncesi mevcut içeriğin snapshot'ını `change_reason='user_edit'` ile **uygulama tarafında** kaydeder.
> - **`regenerate`** → `force=true` yeniden üretimde, görev mevcut içeriği `change_reason='regenerate'` ile snapshot'ladıktan sonra yeni üretime başlar.
> Böylece `version_number` her durumda `fn_auto_version_number` ile tutarlı artar; çift kayıt olmaması için trigger ve uygulama aynı bölümde aynı status geçişinde **birlikte** snapshot almaz (regenerate'te app kaydı eski içerik için, trigger kaydı yeni `done` içerik için oluşur — ikisi farklı versiyonlardır).

### 5.4 View'lar

```sql
-- Proje ilerleme özeti (dashboard için)
v_project_progress:
  project_id, title, project_status, chapter_count,
  total_word_count, target_word_count, word_pct,
  chapters_done, chapters_generating, chapters_error, chapters_pending, chapter_pct

-- Token maliyet izleme
v_token_costs:
  project_id, title, user_id,
  total_tokens_input, total_tokens_output, total_tokens,
  successful_tasks, failed_tasks, avg_duration_ms
```

### 5.5 Şema Doğruluk Kaynağı

- **Alembic, şemanın tek doğruluk kaynağıdır.** Tüm DDL (tablolar, pgvector extension, indexler, triggerlar, view'lar) `001_initial_schema.py` içinde tanımlanır. pgvector/trigger/view gibi Alembic'in otomatik üretemediği nesneler migration içinde `op.execute("""...""")` ile ham SQL olarak yazılır.
- **`migration.sql` artık elle yazılmaz; otomatik üretilir.** `scripts/dump_schema.sh` migration uygulanmış bir test veritabanından `pg_dump --schema-only` ile dökümü alır. Bu dosya yalnızca referans/bootstrap amaçlıdır, asla elle düzenlenmez. Böylece iki ayrı şema kaynağının uyumsuzlaşması (drift) riski ortadan kalkar.

---

## 6. API Endpoint'leri

Tüm endpoint'ler `/api/v1` prefix'i alır. Auth gerektiren **HTTP** endpoint'lerde `Authorization: Bearer <token>` header'ı **veya** `X-API-Key: <key>` header'ı gerekir. (WebSocket auth ayrıdır — bkz. Bölüm 6.5.)

### 6.1 Auth

| Method | Path | Auth | Açıklama |
|---|---|---|---|
| POST | `/auth/register` | — | Yeni kullanıcı kaydı |
| POST | `/auth/login` | — | JWT access + refresh token al |
| POST | `/auth/refresh` | — | Refresh token ile yeni access token (jti iptal kontrolü yapılır) |
| POST | `/auth/logout` | ✓ | Refresh token'ı (veya tüm oturumları) iptal et |
| GET | `/auth/me` | ✓ | Oturum açık kullanıcı bilgisi |
| POST | `/auth/api-keys` | ✓ (pro+) | Programatik erişim için API anahtarı üret (tam anahtar **yalnızca bir kez** yanıtta döner) |
| GET | `/auth/api-keys` | ✓ | API anahtarı meta bilgisi (`has_api_key`, `api_key_prefix`, `created_at`) |
| DELETE | `/auth/api-keys` | ✓ | Mevcut API anahtarını iptal et |

**POST /auth/register body:**
```json
{ "email": "yazar@example.com", "password": "sifre1234", "full_name": "Ali Yazar" }
```

**POST /auth/login yanıtı:**
```json
{ "access_token": "...", "refresh_token": "...", "token_type": "bearer", "expires_in": 900 }
```

**POST /auth/logout body:**
```json
{ "refresh_token": "...", "all_sessions": false }
```
- `all_sessions=false`: yalnızca verilen refresh token'ın `jti`'si iptal edilir
- `all_sessions=true`: kullanıcının tüm aktif refresh token'ları iptal edilir (`refresh_token` opsiyonel olur)

**POST /auth/api-keys yanıtı (anahtar yalnızca burada görünür):**
```json
{ "api_key": "kp_a1b2c3d4e5f6...", "api_key_prefix": "kp_a1b2c3d4", "created_at": "2026-06-13T08:00:00Z" }
```

> **Plan kapısı:** `POST /auth/api-keys` yalnızca `pro`/`enterprise` planlarda erişilebilir; `free` planda **402** döner (bkz. Bölüm 20).
> **bcrypt notu:** bcrypt parolayı 72 byte ile sınırlar. `security.py` içinde parola, hash'lemeden önce SHA-256 ile ön-özetlenir (base64) veya ≤72 byte garanti edilir; aksi halde uzun parolalar sessizce kırpılır.

### 6.2 Projects

| Method | Path | Açıklama |
|---|---|---|
| POST | `/projects` | Yeni proje oluştur (settings otomatik eklenir) — plan: aktif proje limiti |
| GET | `/projects` | Kullanıcının projelerini listele (sayfalama, status filtresi) |
| GET | `/projects/{id}` | Tekil proje detayı |
| PATCH | `/projects/{id}` | Proje güncelle (title, format, vb.) |
| DELETE | `/projects/{id}` | Projeyi ve tüm alt kayıtları sil |
| GET | `/projects/{id}/progress` | İlerleme istatistikleri (v_project_progress) |
| GET | `/projects/{id}/settings` | AI ayarlarını getir |
| PATCH | `/projects/{id}/settings` | AI ayarlarını güncelle |
| POST | `/projects/{id}/pause` | Üretimi duraklat: `status=paused`, yeni bölüm kuyruğa **alınmaz** |
| POST | `/projects/{id}/resume` | Duraklatılmış projeyi sürdür: `status=generating`, pending bölümler yeniden kuyruğa alınır |

> **Pause/resume davranışı:** `pause` yalnızca **yeni** kuyruğa almayı durdurur; o an `generating` olan (uçuştaki Celery) bölümler tamamlanır. `generate`/`generate-all`, proje `paused` iken **409** döner. `resume` projeyi `generating`'e çeker ve `pending` bölümleri tekrar kuyruğa ekler.

**POST /projects body:**
```json
{
  "title": "Yapay Zeka ve Toplum",
  "genre": "Teknoloji",
  "kdp_format": "6x9",
  "citation_style": "APA",
  "language": "tr",
  "target_word_count": 60000
}
```

**PATCH /projects/{id}/settings body:**
```json
{
  "tone_profile": "academic",
  "audience_level": "graduate",
  "academic_field": "Bilgisayar Mühendisliği",
  "human_writing_mode": true,
  "llm_config": { "model": "claude-sonnet-4-6", "temperature": 0.5, "max_tokens": 8000 }
}
```

### 6.3 Chapters

| Method | Path | Açıklama |
|---|---|---|
| POST | `/projects/{id}/chapters/toc` | İçindekiler yükle (pending bölümleri temizler) |
| GET | `/projects/{id}/chapters` | Bölümleri listele (status filtresi) |
| GET | `/projects/{id}/chapters/{ch_id}` | Tekil bölüm detayı |
| PATCH | `/projects/{id}/chapters/{ch_id}` | Bölüm güncelle (manuel düzenleme → `user_edit` versiyonu oluşturur) |
| POST | `/projects/{id}/chapters/{ch_id}/generate` | Tek bölümü kuyruğa ekle |
| POST | `/projects/{id}/chapters/generate-all` | Tüm pending bölümleri kuyruğa ekle |
| GET | `/projects/{id}/chapters/{ch_id}/tasks` | Bölüm görev geçmişi |

**POST /toc body:**
```json
{
  "chapters": [
    { "order_index": 1, "title": "Giriş", "description": "Kitabın kapsamı ve amacı" },
    { "order_index": 2, "title": "Temel Kavramlar", "target_word_count": 8000 },
    { "order_index": 3, "title": "Sonuç" }
  ]
}
```
> `target_word_count` verilmeyen bölümler için değer, üretim sırasında `project.target_word_count / chapter_count` ile hesaplanır.

**PATCH /chapters/{ch_id} davranışı:** `content` alanı değişiyorsa, güncellemeden **önce** mevcut içerik `versioning.py` ile `change_reason='user_edit'` olarak snapshot'lanır; sonra yeni içerik yazılır ve `word_count` otomatik hesaplanır.

**POST /generate body:**
```json
{ "force": false }
```
- `force=false`: done bölümü yeniden üretmez, 409 döner
- `force=true`: done bölümü yeniden üretir; üretim öncesi mevcut içerik `change_reason='regenerate'` ile snapshot'lanır
- `generating` durumundaki bölüm için her zaman 409 döner
- Proje `paused` ise 409 döner

**POST /generate-all davranışı:**
- Sadece `pending` bölümleri kuyruğa ekler
- Bölümler arasına `order_index × 2 saniye` countdown — LLM rate limit koruması
- Plan: eşzamanlı `generate-all` limiti aşılırsa **429** döner (bkz. Bölüm 20)
- 202 Accepted döner

### 6.4 Exports

| Method | Path | Açıklama |
|---|---|---|
| POST | `/projects/{id}/exports` | Export isteği oluştur |
| GET | `/projects/{id}/exports` | Export geçmişi |
| GET | `/projects/{id}/exports/{job_id}` | Export durumu + indirme URL'i |

**POST /exports body:**
```json
{ "format": "docx" }
```
- Format değerleri: `docx`, `pdf`, `epub`
- En az bir `done` bölüm yoksa **422** döner
- `pdf`/`epub` formatları yalnızca `pro`/`enterprise` planlarda; `free` planda **402** döner (bkz. Bölüm 20)

### 6.5 WebSocket

```
WS /api/v1/ws/projects/{project_id}?token=<access_token>
```

**Kimlik doğrulama:**
- Tarayıcılar WebSocket el sıkışmasında özel header gönderemediği için JWT **query parametresi** (`?token=`) olarak iletilir.
- Sunucu `connect` anında token'ı doğrular:
  - Geçersiz/süresi dolmuş token → **close code 4401** (Unauthorized)
  - Kullanıcı bu projenin sahibi değilse → **close code 4403** (Forbidden)
- Access token süresi dolduğunda istemci yeni token ile yeniden bağlanır (reconnect).

**Sunucudan gelen event yapısı:**
```json
{
  "event": "chapter_update",
  "chapter_id": "uuid",
  "project_id": "uuid",
  "status": "done",
  "data": { "word_count": 4200, "duration_ms": 18400 }
}
```

**Event tipleri:**
- `chapter_update` — bölüm durum değişimi (queued → generating → done/error)
- `export_done` — export tamamlandı
- `ping` — 30 saniyede bir heartbeat (yalnızca `{"event":"ping"}` taşır; `status` içermez)

### 6.6 Admin (dead-letter yönetimi)

`role = 'admin'` gerektirir. Normal kullanıcı için **403** döner.

| Method | Path | Açıklama |
|---|---|---|
| GET | `/admin/dead-letter` | `dead_letter:generation` Redis listesindeki başarısız görevleri listele |
| POST | `/admin/dead-letter/{chapter_id}/requeue` | Bölümü `pending`'e çekip `generation` kuyruğuna yeniden ekle |
| DELETE | `/admin/dead-letter/{chapter_id}` | Görevi dead-letter listesinden kaldır (vazgeç) |

### 6.7 System

| Method | Path | Açıklama |
|---|---|---|
| GET | `/health` | Uygulama sağlık kontrolü |
| GET | `/health/db` | PostgreSQL bağlantı testi |
| GET | `/health/redis` | Redis bağlantı testi |

---

## 7. Celery Görev Akışı

### 7.1 `generate_chapter_task`

**Kuyruk:** `generation`
**Konfigürasyon:**
```python
max_retries=3
default_retry_delay=30        # saniye
retry_backoff=True            # her denemede 2 katına çıkar
retry_backoff_max=600         # maksimum 10 dakika bekleme
retry_jitter=True             # ±rastgele jitter (thundering herd önleme)
acks_late=True                # worker crash'te görev kaybolmaz
reject_on_worker_lost=True
time_limit=600                # 10 dakika hard limit
soft_time_limit=540           # 9 dakikada SoftTimeLimitExceeded
```

**9 adımlı akış:**
1. DB'den bölüm + proje ayarlarını yükle. **`force=true` ise** ve mevcut `content` varsa, `versioning.py` ile `change_reason='regenerate'` snapshot al. `chapter.status = 'generating'`
2. `task_log.status = 'started'` olarak güncelle
3. **Bağlam topla** (bkz. Bölüm 10):
   - `SEMANTIC_MEMORY_ENABLED=true` → bölümün `title + description`'ını embed et, bu sorgu vektörüyle aynı projedeki **`done`** bölümler arasından cosine similarity ile en benzer 3 bölümün `content_summary`'sini al
   - `false` → bir önceki 3 bölümü `order_index` sırasına göre al (vektörsüz fallback)
4. Prompt oluştur (tone_profile, audience_level, citation_style, target_word_count, human_writing_mode). **LLM ayarları:** `project_settings.llm_config` → yoksa `.env` `ANTHROPIC_*` fallback (bkz. Bölüm 8.4)
5. Anthropic API streaming çağrısı; token sayacını tut (usage `message_delta`'dan okunur)
6. `chapter.content`, `word_count`, `status='done'`, `generated_at` kaydet
   - `fn_snapshot_on_done` trigger'ı otomatik `change_reason='ai_generation'` versiyonu oluşturur
7. `content_summary` üret (LLM), `embedding` hesapla (embedding_service), `chapters.embedding`'e kaydet
8. `task_log` tamamla (status, tokens, duration_ms)
9. Redis pub/sub'a `chapter_update` eventi gönder → WebSocket istemciye iletir

**Hata yönetimi:**
- Her exception'da `chapter.retry_count += 1`
- `retry_count < 3`: `chapter.status = 'queued'`, Celery retry tetikler
- `retry_count >= 3`: `chapter.status = 'error'`, **`dead_letter:generation`** Redis listesine ekle, kullanıcıya WebSocket ile `error` eventi gönder
- `RateLimitError` için özel `countdown` (`Retry-After` başlığından okunur)

### 7.2 `export_project_task`

**Kuyruk:** `export`
**Konfigürasyon:** `max_retries=2`, `default_retry_delay=60`

**Akış:**
1. `export_job.status = 'processing'`
2. `done` durumdaki bölümleri `order_index` sırasına göre al
3. Format'a göre dağıt:
   - `docx` → `generate_docx()`
   - `pdf`  → `generate_pdf()`
   - `epub` → `generate_epub()` (ebooklib + markdown→HTML)
4. Dosyayı MinIO'ya yükle, `presigned_url` üret (`PRESIGNED_URL_EXPIRE_HOURS` kadar geçerli)
5. `export_job.status = 'done'`, `s3_path`, `file_size_bytes`, `url_expires_at`, `finished_at` kaydet
6. Redis pub/sub'a `export_done` eventi gönder

### 7.3 Worker Konfigürasyonu

```
worker_generation: --queues=generation --concurrency=2
worker_export:     --queues=export --concurrency=1
worker_prefetch_multiplier=1    # adil dağılım, bellek kontrolü
```

---

## 8. Prompt Sistemi

### 8.1 Sistem Promptu Yapısı

```
Sen deneyimli bir akademik yazarsın.
Yazı tonu: {tone_profile} | Hedef kitle: {audience_level} | Atıf formatı: {citation_style}
Hedef kelime sayısı: {target_word_count} kelime (±%15 sapma kabul edilir)

[human_writing_mode=True ise ek kurallar:]
- Cümle uzunluklarını çeşitlendir
- Her paragrafı benzer uzunlukta bitirme
- Akademisyenlerin kullandığı bağlaçları kullan
- Kişisel gözlem veya soru formları ekle

KESİNLİKLE UYULACAK KURALLAR:
- Her iddiayı kaynakla destekle, atıf işaretçisi [1], [2]... kullan
- Uydurma DOI/atıf ÜRETME; emin değilsen atıfı işaretçisiz bırak (doğrulama Bölüm 9.4'te yapılır)
- Tablolar için Markdown tablo söz dizimi kullan
- Görsel önerileri <!-- GÖRSEL: açıklama --> olarak işaretle
- Başlığı tekrar etme, direkt içeriğe gir
```

### 8.2 Kullanıcı Promptu Yapısı

```
[Bağlam: önceki ilgili bölümlerin content_summary'si — Bölüm 7.1 adım 3'e göre]

Bölüm {order_index}: {title}
Açıklama: {description}

Yukarıdaki başlık için akademik bölüm yaz.
```

### 8.3 İnsan Yazısı Simülasyonu (`human_writing_mode`)

Bu mod, metni daha **doğal/insansı bir düzyazı stiline** yaklaştırır:
- **Burstiness** kontrolü: kısa ve uzun cümleler dönüşümlü
- **Perplexity** artırma: beklenmedik ama yerinde kelime seçimleri
- Aynı paragraf yapı kalıplarından kaçınma
- Zaman zaman birinci çoğul kişi: "Bu çalışmada inceledik..."
- Soru formları ve düşünce yönlendirmeleri

> ⚖️ **Sorumlu kullanım notu:** Bu mod metin kalitesini ve okunabilirliğini artırmak içindir. Yapay zeka ile üretilmiş akademik/yayın içeriğinin kullanımı; akademik dürüstlük kuralları ve KDP dahil yayın platformlarının **AI içerik politikalarına** tabidir. Üretilen içeriğin ilgili kurumun/platformun kurallarına uygunluğunu sağlamak **kullanıcının sorumluluğundadır.** Mod, "AI tespitini atlatma" garantisi değildir.

### 8.4 LLM Ayarları ve Sıcaklık (temperature) Politikası

- **Ayar önceliği (v2.1'de netleşti):** `project_settings.llm_config` içindeki `model`/`temperature`/`max_tokens` değerleri, `.env`'deki `ANTHROPIC_MODEL`/`ANTHROPIC_TEMPERATURE`/`ANTHROPIC_MAX_TOKENS` **varsayılanlarını ezer.** `.env` değerleri yalnızca `llm_config`'te ilgili alan yoksa fallback olarak kullanılır.
- **Varsayılan `temperature = 0.5`** (v1.0'da 0.8 idi). Akademik içerikte olgu tutarlılığı ve atıf doğruluğu kritik olduğundan daha düşük sıcaklık tercih edilir.
- Kullanıcı `llm_config.temperature` ile bunu değiştirebilir (örn. `popular`/`narrative` türler için 0.7'ye çıkarılabilir).
- `human_writing_mode` stil çeşitliliğini esas olarak **prompt yönlendirmesiyle** sağlar; sıcaklığı tek başına yükseltmek hedef değildir.

---

## 9. KDP Çıktı Standardı

### 9.1 DOCX Şablonu (python-docx)

```python
# Sayfa boyutları (inç → cm)
KDP_FORMATS = {
    "6x9":    {"width": 15.24, "height": 22.86},
    "5x8":    {"width": 12.70, "height": 20.32},
    "7x10":   {"width": 17.78, "height": 25.40},
    "8.5x11": {"width": 21.59, "height": 27.94},
}

# Kenar boşlukları (KDP standardı)
MARGINS = {
    "top":     2.54,   # cm
    "bottom":  2.54,
    "inside":  1.91,   # iç kenar (cilt payı)
    "outside": 1.27,
}

# Yazı tipleri
BODY_FONT = "Times New Roman"   # veya Georgia
HEADING_FONT = "Arial"          # veya Calibri
BODY_SIZE = 11                  # punto
HEADING_SIZES = {1: 18, 2: 14, 3: 12}

# Satır aralığı
LINE_SPACING = 1.15             # çok satırlı
```

**DOCX yapısı:**
1. Kapak sayfası (başlık, yazar, yayın bilgisi)
2. Telif sayfası
3. Teşekkür (opsiyonel)
4. İçindekiler (otomatik sayfa numaralı — `TOC` alanı)
5. Bölümler (her bölüm yeni sayfa, Roman → Arabic sayfa numarası geçişi)
6. Kaynakça (atıf formatına göre APA/Chicago/MLA)
7. Dizin (opsiyonel)

> ⚠️ **Sayfa numarası formatı geçişi (Roman → Arabic) teknik notu:** python-docx, bölüm (section) bazlı sayfa numarası format değişimini *native* desteklemez. Ön matter'da Roman (i, ii, iii), gövdede Arabic (1, 2, 3) için **section break** eklenip `w:pgNumType` ve `PAGE` alan kodları **doğrudan OOXML (XML) manipülasyonu** ile yazılmalıdır. Bu, `formatter.py`'de ayrı bir yardımcı fonksiyon gerektirir; eforu hesaba katın.

### 9.2 PDF Üretimi (WeasyPrint)

- **Renk:** RGB/sRGB çıktı. **KDP, RGB PDF kabul eder** ve çoğu kitap için yeterlidir.
  - *(Not: WeasyPrint pratikte gerçek CMYK üretmez. Gerçek CMYK gerekiyorsa, üretilen PDF opsiyonel bir **Ghostscript post-process** adımıyla CMYK'ye dönüştürülür — ileri aşama, zorunlu değil.)*
- **Bleed (taşma payı):** `3.175mm` (0.125 inç) — KDP standardı
- Gömülü font (font embedding) — tüm fontlar PDF'e gömülür
- Sayfa numaraları: ön matter Roman (i, ii, iii...), gövde Arabic (1, 2, 3...) — WeasyPrint'te CSS `@page` ve `counter` ile kolayca yapılır
- KDP preflight: font gömme + minimum 300 DPI görsel kontrolü (media_assets.dpi)

### 9.3 EPUB Üretimi (ebooklib)

- Her `done` bölüm bir `EpubHtml` öğesi olur; Markdown → HTML dönüşümü (`markdown` kütüphanesi) yapılır
- `toc` (içindekiler) ve `spine` (okuma sırası) `order_index`'e göre kurulur
- Metadata: başlık, yazar, dil (`project.language`), yayın tarihi
- Görseller `EpubImage` olarak gömülür; kaynakça ayrı bir bölüm dosyası olur
- Çıktı reflowable EPUB 3 (Kindle/KDP EPUB yükleme ile uyumlu)

### 9.4 Atıf Doğrulama Politikası (DOI halüsinasyonu)

- LLM'in ürettiği her atıf için `citation_service.verify()` CrossRef'e sorar.
- `citations.verification_status` durumları:
  - `unverified` — **başlangıç durumu** (kayıt oluşturuldu, henüz doğrulanmadı)
  - `verified` — DOI bulundu ve başlık/yazar eşleşti → `doi_verified=true`
  - `not_found` — DOI/başlık CrossRef'te yok → kaynakçada **"⚠ doğrulanamadı"** etiketiyle tutulur
  - `mismatch` — DOI var ama meta veriler tutmuyor → CrossRef verisiyle düzeltme önerilir
- Doğrulanamayan atıflar **silinmez** ama çıktı kaynakçasında işaretlenir; kullanıcı düzenleyebilir.

### 9.5 Atıf Formatları

**APA 7:**
```
Yazar, A. A., & Yazar, B. B. (Yıl). Başlık. Dergi, Cilt(Sayı), sayfa-sayfa. https://doi.org/...
```

**Chicago:**
```
Soyadı, Ad. "Makale Başlığı." Dergi Adı Cilt, sayı (Yıl): sayfa-sayfa.
```

**MLA:**
```
Yazar Soyadı, Ad. "Başlık." Dergi, cilt sayı, yıl, ss. sayfa-sayfa.
```

---

## 10. Semantik Hafıza (pgvector)

**Amaç:** Bölümler arası terminoloji tutarlılığı ve argüman sürekliliği

**Embedding sağlayıcısı (yapılandırılabilir — bkz. Bölüm 4):**
- `EMBEDDING_PROVIDER=openai` → `text-embedding-3-small`, **1536** boyut (varsayılan)
- `EMBEDDING_PROVIDER=voyage` → `voyage-3`, **1024** boyut (Anthropic'in önerdiği sağlayıcı)
- `embedding_service.py` sağlayıcıyı soyutlar; `chapters.embedding` boyutu `EMBEDDING_DIMENSIONS` ile **eşleşmek zorundadır.**

**Akış:**
1. Bölüm tamamlanınca `content_summary` (~200 kelime özet) üret
2. Özeti embedding'e çevir
3. `chapters.embedding` sütununa kaydet (HNSW index ile)
4. **Yeni bölüm üretiminde sorgu vektörü:** Yeni bölümün henüz içeriği yoktur; bu nedenle **bölümün `title + description`'ı embed edilir** ve sorgu vektörü olarak kullanılır:
   ```sql
   SELECT content_summary FROM chapters
   WHERE project_id = :pid AND status = 'done' AND embedding IS NOT NULL
   ORDER BY embedding <=> :query_embedding
   LIMIT 3;
   ```
5. En benzer 3 bölümün özetini yeni bölüm promptuna ekle

**Devre dışı modu (`SEMANTIC_MEMORY_ENABLED=false`):**
- Embedding sağlayıcı anahtarı yoksa veya özellik kapatılırsa, vektör arama yerine **bir önceki 3 bölüm `order_index` sırasına göre** alınır. Sistem embedding olmadan da çalışmaya devam eder (graceful degradation).

**HNSW parametreleri:**
- `m = 16` — bağlantı sayısı (doğruluk/hız dengesi)
- `ef_construction = 64` — inşa sırasında komşu sayısı

---

## 11. WebSocket Protokolü

**Bağlantı:** `ws://host/api/v1/ws/projects/{project_id}?token=<access_token>`
**Kimlik doğrulama:** bkz. Bölüm 6.5 (query param token, 4401/4403 close kodları, proje sahipliği kontrolü)

**Mimari:** Celery worker → Redis pub/sub → FastAPI WS sunucusu → İstemci

**Redis kanalı:** `project:{project_id}`

**Sunucu tarafı eşzamanlılık:** WS handler `asyncio.gather` ile (a) Redis pub/sub dinleyici coroutine ve (b) 30 sn'lik heartbeat coroutine'ini paralel çalıştırır; biri biterse diğeri iptal edilir ve bağlantı kapatılır.

**Sunucudan istemciye eventler:**

```json
// Bölüm üretim başladı
{ "event": "chapter_update", "chapter_id": "uuid", "status": "generating" }

// Bölüm tamamlandı
{
  "event": "chapter_update",
  "chapter_id": "uuid",
  "status": "done",
  "data": { "word_count": 4200, "duration_ms": 18400 }
}

// Bölüm hata aldı
{
  "event": "chapter_update",
  "chapter_id": "uuid",
  "status": "error",
  "data": { "error": "LLM API timeout", "retry_count": 3 }
}

// Export tamamlandı
{
  "event": "export_done",
  "project_id": "uuid",
  "status": "done",
  "data": { "format": "docx", "export_job_id": "uuid" }
}

// Heartbeat (30 saniyede bir) — status taşımaz
{ "event": "ping" }
```

---

## 12. Retry Stratejisi

| Deneme | Temel bekleme | Backoff çarpanı | Örnek bekleme (jitter öncesi) |
|---|---|---|---|
| 1. retry | 30s | 2× | ~30s |
| 2. retry | 30s | 2× | ~60s |
| 3. retry | 30s | 2× | ~120s |
| Dead-letter | — | — | Kullanıcı bildirimi + admin requeue |

**Jitter:** Celery `retry_jitter=True` ile kendi jitter mekanizmasını uygular (elle eklemeye gerek yok)
**Rate limit özel davranış:** `Retry-After` header değeri `countdown` olarak kullanılır
**Dead-letter:** Redis listesi `dead_letter:generation`. **Bölüm 6.6'daki admin endpoint'leri** ile listelenir ve yeniden tetiklenir.

---

## 13. Docker Compose Servisleri

```
postgres        pgvector/pgvector:pg15   port 5432
redis           redis:7-alpine           port 6379
minio           minio/minio:latest       port 9000, 9001 (console)
api             ./Dockerfile             port 8000  (uvicorn --reload)
worker_gen      ./Dockerfile             celery --queues=generation --concurrency=2
worker_exp      ./Dockerfile             celery --queues=export --concurrency=1
flower          ./Dockerfile             celery flower  port 5555
```

**Başlangıç sırası:** postgres → redis → minio → api → worker_gen → worker_exp → flower

> **Not (env anahtarları):** LLM ve embedding çağrılarını **işlevsel olarak yalnızca `worker_gen`** yapar; dolayısıyla `ANTHROPIC_API_KEY` ve embedding anahtarı (`OPENAI_API_KEY`/`VOYAGE_API_KEY`) asıl bu servis için zorunludur. Pratiklik için `.env` tüm servislere `env_file` ile verilebilir, ama `api` ve `worker_exp` bu anahtarları çalışma zamanında kullanmaz. `flower` production'da basic-auth ile korunmalıdır (bkz. Bölüm 21).

---

## 14. Pydantic Şemalar (Özet)

### İstek şemaları
- `UserRegister`: email, password (min 8), full_name
- `LogoutRequest`: refresh_token?, all_sessions (bool, default false)
- `ApiKeyCreate`: (gövdesiz) → yeni anahtar üretir
- `ProjectCreate`: title, subtitle?, genre?, kdp_format, citation_style, language, target_word_count
- `ProjectUpdate`: Tüm alanlar opsiyonel
- `ProjectSettingsUpdate`: tone_profile, audience_level, academic_field, human_writing_mode, style_overrides, llm_config
- `TocItem`: order_index (1-200), title, description?, target_word_count?
- `TocImport`: chapters listesi — order_index benzersizlik validasyonu + sıralama
- `ChapterUpdate`: title?, description?, content? (kelime sayısı otomatik hesaplanır; content değişiminde user_edit versiyonu)
- `GenerateRequest`: force (bool, default false)
- `ExportRequest`: format (docx|pdf|epub)

### Yanıt şemaları
- `UserOut`: id, email, full_name, role, plan, created_at
- `TokenResponse`: access_token, refresh_token, token_type, expires_in
- `ApiKeyOut`: api_key (yalnız oluşturmada), api_key_prefix, created_at
- `ApiKeyInfo`: has_api_key (bool), api_key_prefix?, created_at?   ← GET /auth/api-keys yanıtı
- `ProjectOut`: tüm proje alanları + settings (nested)
- `ProjectProgress`: word_pct, chapter_pct, chapters_done/generating/error/pending
- `ChapterOut`: tüm bölüm alanları (content dahil)
- `GenerateResponse`: chapter_id, celery_task_id, status, message
- `ExportJobOut`: id, format, status, presigned_url, url_expires_at, file_size_bytes
- `CitationOut`: marker, doi, formatted_text, doi_verified, verification_status
- `TaskLogOut`: celery_task_id, status, tokens_input/output, duration_ms, error_message
- `WsEvent`: event, chapter_id?, project_id?, status?, progress?, message?, data?
- `PaginatedResponse`: items, total, page, page_size, pages

---

## 15. Test Kapsamı

**tests/test_api.py içerikleri:**

*Auth*
- `test_register` — 201 döner, email + id içerir
- `test_register_duplicate_email` — 409 döner
- `test_login` — access_token + token_type döner
- `test_login_wrong_password` — 401 döner
- `test_refresh_token` — yeni access_token döner
- `test_refresh_after_logout` — logout sonrası refresh 401 döner
- `test_api_key_create_and_auth` — anahtar üretilir, X-API-Key ile /me erişilir (pro plan)
- `test_api_key_free_plan_forbidden` — free planda /auth/api-keys 402 döner

*Projects*
- `test_create_project` — 201, status='draft', settings!=null
- `test_project_not_found` — 404 döner
- `test_update_project_settings` — 200, güncel alan değerleri
- `test_project_progress` — word_pct/chapter_pct alanları döner
- `test_pause_blocks_generate` — paused projede generate 409 döner

*Chapters*
- `test_import_toc` — 201, 3 bölüm, status='pending'
- `test_toc_duplicate_order_index` — 422 döner
- `test_generate_done_without_force` — 409 döner
- `test_patch_content_creates_version` — PATCH content sonrası user_edit versiyonu oluşur
- `test_generate_all_queues_pending` — 202, pending bölümler kuyruğa girer (Celery mock)

*Exports*
- `test_export_without_done_chapter` — 422 döner
- `test_export_invalid_format` — 422 döner
- `test_export_pdf_free_plan` — free planda pdf export 402 döner

*System*
- `test_health` — 200, status='ok'

**Test altyapısı:**
- Test veritabanı: `kitap_test` (ayrı, production'dan izole, pgvector extension kurulu)
- `get_db` dependency override ile test session enjeksiyonu
- LLM, embedding ve Celery çağrıları **mock**'lanır (gerçek API çağrısı yapılmaz)
- Her test sonunda `session.rollback()` ile temizlik

---

## 16. Geliştirme Sırası (Claude Code için)

Aşağıdaki sırayla geliştirme yapılması önerilir. Her adım bir öncekine bağımlıdır.

### Aşama 1 — Temel Altyapı
1. `requirements.txt` (ebooklib, **markdown**, openai/voyageai dahil) ve `Dockerfile` oluştur
2. `docker-compose.yml` — postgres, redis, minio servisleri
3. `app/core/config.py` — pydantic-settings (embedding + JWT + S3 + CORS + Sentry ayarları)
4. `app/db/session.py` — async engine + `get_db`
5. `app/models/models.py` — tüm ORM modelleri (**10 tablo**, `refresh_tokens` dahil)
6. `alembic/` yapısını kur, `001_initial_schema.py` migration'ı yaz (pgvector, indexler, triggerlar, view'lar — **tek kaynak**)
7. `scripts/dump_schema.sh` — migration uygulanmış DB'den `migration.sql` otomatik dökümü

### Aşama 2 — Auth
8. `app/core/security.py` — JWT (jti'li refresh), bcrypt (72-byte guard), API key üret/doğrula
9. `app/schemas/schemas.py` — UserRegister, LogoutRequest, TokenResponse, UserOut, ApiKey*
10. `app/api/v1/endpoints/auth.py` — register, login, refresh (jti iptal kontrolü), logout, /me, /api-keys
11. `app/main.py` — temel FastAPI app, CORS middleware (CORS_ORIGINS), auth router'ı ekle
12. Auth testlerini yaz ve geç (refresh/logout/api-key/plan dahil)

### Aşama 3 — Proje Yönetimi + Plan Limitleri
13. Proje şemalarını schemas.py'ye ekle
14. `app/core/limits.py` — `require_plan(feature)` ve `enforce_quota()` dependency'leri (bkz. Bölüm 20)
15. `app/api/v1/endpoints/projects.py` — CRUD + settings + progress + pause/resume (limit kontrolleriyle)
16. Proje testlerini yaz ve geç (pause/limit dahil)

### Aşama 4 — İçindekiler ve Bölümler
17. Chapter şemalarını schemas.py'ye ekle
18. `app/services/versioning.py` — user_edit/regenerate için chapter_versions oluşturma
19. `app/api/v1/endpoints/chapters.py` — TOC import, listeleme, PATCH (user_edit versiyonu)
20. `/generate` ve `/generate-all` endpoint'leri (Celery çağrısı mock ile; paused/limit kontrolü)
21. Bölüm testlerini yaz ve geç (versiyon oluşturma dahil)

### Aşama 5 — Celery + Realtime
22. `app/tasks/celery_app.py` — celery_app konfigürasyonu (iki kuyruk)
23. `generate_chapter_task` — tüm 9 adım (LLM + embedding mock ile başla; regenerate snapshot dahil)
24. `export_project_task` iskelet (docx/pdf/epub dağıtımı)
25. Redis pub/sub bağlantısı + `dead_letter:generation` listesi
26. `app/api/v1/endpoints/ws.py` — WebSocket (query-param token auth) + pub/sub dinleyici + heartbeat

### Aşama 6 — LLM + Embedding Entegrasyonu
27. `_build_prompt()` — sistem + kullanıcı promptu, human_writing_mode, llm_config>env önceliği
28. `_call_llm()` — Anthropic API httpx çağrısı, streaming, token sayımı, retry
29. `app/services/embedding_service.py` — OpenAI/Voyage soyutlaması, `EMBEDDING_PROVIDER`'a göre seçim
30. `_get_context_summary()` — title+description embed → pgvector cosine similarity; `SEMANTIC_MEMORY_ENABLED=false` fallback
31. `_generate_summary()` — LLM ile ~200 kelimelik content_summary üretimi

### Aşama 7 — Çıktı Üretimi
32. `app/services/formatter.py` — `generate_docx()`, KDP şablonu, python-docx (Roman→Arabic XML yardımcısı)
33. `generate_pdf()` — WeasyPrint pipeline (RGB, bleed 3.175mm, font embedding)
34. `generate_epub()` — ebooklib + markdown→HTML pipeline
35. Atıf formatlaması (APA, Chicago, MLA) + doğrulama durumu işaretleme
36. Tablo ve görsel yerleştirme
37. `app/api/v1/endpoints/exports.py` (format plan kontrolü ile)

### Aşama 8 — İzleme ve Üretim Hazırlığı
38. `app/services/citation_service.py` — CrossRef DOI doğrulama (unverified/verified/not_found/mismatch)
39. `app/services/media_service.py` — Matplotlib grafik üretimi (300 DPI)
40. MinIO upload / presigned URL üretimi (24 saat, url_expires_at takibi)
41. `app/api/v1/endpoints/admin.py` — dead-letter listele/requeue (role=admin)
42. Flower monitoring docker servisini ekle (basic-auth ile)
43. Loglama (structlog), Sentry entegrasyonu (SENTRY_DSN)
44. `worker_prefetch_multiplier`, `acks_late`, dead-letter kuyruk testleri

---

## 17. Servislerin Sağlık Adresleri

| Servis | URL | Not |
|---|---|---|
| FastAPI Swagger | http://localhost:8000/docs | DEBUG=true olmalı |
| FastAPI ReDoc | http://localhost:8000/redoc | DEBUG=true olmalı |
| Flower | http://localhost:5555 | Celery görev monitörü — production'da basic-auth |
| MinIO Console | http://localhost:9001 | minioadmin/minioadmin |
| PostgreSQL | localhost:5432/kitap_db | |
| Redis | localhost:6379 | |

---

## 18. Hızlı Başlangıç

```bash
# 1. Ortam hazırlığı
cp .env.example .env
# .env içinde ANTHROPIC_API_KEY ve embedding anahtarını (OPENAI_API_KEY veya VOYAGE_API_KEY) doldur

# 2. Servisleri başlat
docker compose up -d

# 3. Migration uygula
docker compose exec api alembic upgrade head

# 4. API'yi test et
curl http://localhost:8000/health

# 5. Swagger UI
open http://localhost:8000/docs
```

---

## 19. Önemli Notlar (Claude Code için)

- `embedding` sütunu için `pgvector.sqlalchemy.Vector` import'u gerekir; boyut `EMBEDDING_DIMENSIONS` ile eşleşmeli
- `AsyncSession` ile `db.execute(select(...))` kullanılmalı, `db.query(...)` async değil
- Celery worker'lar senkron çalışır — `_get_sync_db()` ile psycopg2 bağlantısı açılır
- **Versiyonlama:** `ai_generation` kayıtları `fn_snapshot_on_done` trigger'ı ile **otomatik** oluşur (kod yazmaya gerek yok). Ancak **`user_edit` ve `regenerate`** kayıtları trigger'la yakalanamaz; bunları `services/versioning.py` uygulama tarafında oluşturur (bkz. Bölüm 5.3)
- `chapters.status = 'generating'` → `'done'` geçişinde `projects.total_word_count` trigger ile otomatik güncellenir
- WebSocket bağlantısı `asyncio.gather` ile Redis pub/sub dinleyici + heartbeat coroutine'lerini paralel çalıştırır
- `retry_jitter=True` — Celery kendi jitter mekanizmasını uygular, elle eklemeye gerek yok
- `acks_late=True` + `reject_on_worker_lost=True` ikilisi 7/24 güvenilir çalışmanın temelidir
- Dead-letter kuyruğu `dead_letter:generation` Redis listesidir; **admin endpoint'lerinden** (Bölüm 6.6) yeniden tetiklenir
- MinIO presigned URL `PRESIGNED_URL_EXPIRE_HOURS` (vars. 24 saat) geçerli, `export_jobs.url_expires_at` alanında izlenir ve index var
- **LLM ayar önceliği:** `project_settings.llm_config` > `.env` `ANTHROPIC_*` varsayılanları (bkz. Bölüm 8.4)
- **Plan kotaları** `app/core/limits.py` dependency'leri ile uçlarda zorlanır (bkz. Bölüm 20)
- **Anthropic'in embedding API'si yoktur** — semantik hafıza için ayrı sağlayıcı (`embedding_service.py`) kullanılır
- **EPUB** için `ebooklib` + `markdown` (Markdown → HTML dönüşümü) gerekir
- python-docx'te **Roman→Arabic sayfa numarası** geçişi OOXML manipülasyonu ister (Bölüm 9.1 notu)

---

## 20. Plan Limitleri ve Kota Yönetimi

`users.plan` alanı (`free | pro | enterprise`) için kota uygulaması.

**Enforcement mekanizması (v2.1):** Limitler `app/core/config.py`'de sabit tablo olarak tanımlanır ve `app/core/limits.py`'deki FastAPI dependency'leri ile uçlarda kontrol edilir:
- `require_plan("pdf_export")` / `require_plan("api_key")` — özellik plan kapısı; başarısızsa **402 Payment Required**
- `enforce_quota("active_projects")` / `enforce_quota("monthly_chapters")` — sayısal kota; aşımda **402** veya **429 Too Many Requests**
- **Eşzamanlı `generate-all`** kontrolü: kullanıcı başına `generating` durumdaki proje sayısı bir Redis sayacı (`quota:concurrent_genall:{user_id}`) ile tutulur; `generate-all` başında `INCR`, proje `done`/`paused`/`error` olunca `DECR`. Limit aşılırsa **429**.

| Limit | free | pro | enterprise |
|---|---|---|---|
| Maksimum aktif proje | 1 | 10 | sınırsız |
| Proje başı maksimum bölüm | 10 | 100 | sınırsız |
| Aylık üretim (bölüm) kotası | 20 | 500 | sınırsız |
| PDF / EPUB export | ✗ (yalnız DOCX) | ✓ | ✓ |
| API anahtarı ile erişim | ✗ | ✓ | ✓ |
| Eşzamanlı `generate-all` | 1 | 3 | 10 |

> Bu tablo başlangıç önerisidir; iş modeline göre güncellenebilir. Aylık kota takibi için `task_logs` üzerinden ay bazlı `success` sayımı kullanılabilir veya ayrı bir `usage_counters` tablosu eklenebilir (gelecek sürüm adayı). **Not:** `free` plan yalnızca **DOCX** export edebilir; `pdf`/`epub` için 402 döner.

---

## 21. Güvenlik Kontrol Listesi

- [ ] `SECRET_KEY` production'da güçlü ve gizli (env'den, repoda değil)
- [ ] Refresh token `jti` iptali çalışıyor (`/auth/logout` + `refresh_tokens.revoked`)
- [ ] WebSocket token doğrulaması + proje sahipliği kontrolü (4401/4403)
- [ ] API key hash'li saklanıyor, tam anahtar yalnız üretimde dönüyor
- [ ] CORS yalnız `CORS_ORIGINS`'teki origin'lere açık (production)
- [ ] Tüm proje/bölüm endpoint'lerinde `user_id` sahiplik kontrolü (IDOR önleme)
- [ ] Presigned URL süresi sınırlı (24 saat) ve süresi dolanlar temizleniyor
- [ ] LLM çıktısındaki DOI'ler doğrulanmadan "doğrulanmış" gösterilmiyor
- [ ] Rate limit / plan kotası enforcement aktif (`limits.py`)
- [ ] Flower (:5555) basic-auth ile korunuyor (production)
- [ ] DEBUG=false production'da (Swagger/ReDoc kapalı veya korumalı)

---

## 22. Revizyon Notları

### v2.1 — İç tutarlılık taraması

Dokümanın bölümler arası çapraz kontrolünde bulunan tutarsızlıklar giderildi:

**Mantıksal tutarsızlıklar (A)**
- **A1 — Versiyonlama:** `chapter_versions.change_reason`'ın `user_edit`/`regenerate` değerleri trigger'la üretilemiyordu. Çözüm: trigger `ai_generation`'ı üretmeye devam eder; `user_edit` (PATCH) ve `regenerate` (force=true) için `services/versioning.py` uygulama tarafında snapshot alır. Bölüm 5.1, 5.3, 6.3, 7.1, 19 ve 16 güncellendi.
- **A2 — Plan enforcement:** Bölüm 20'deki kotalar endpoint davranışlarına bağlı değildi. Çözüm: `app/core/limits.py` dependency katmanı (402/429), export ve api-keys uçlarına plan kapıları eklendi. Bölüm 3, 6.1, 6.4, 16, 20.
- **A3 — LLM ayar önceliği:** `.env` `ANTHROPIC_*` ile `project_settings.llm_config` arasındaki öncelik tanımsızdı. Çözüm: `llm_config` `.env`'i ezer kuralı netleştirildi. Bölüm 4, 5.1, 7.1, 8.4, 19.
- **A4 — `paused` durumu:** Enum'da vardı ama endpoint yoktu. Çözüm: `POST /projects/{id}/pause` ve `/resume` eklendi. Bölüm 5.1, 6.2.
- **A5 — `/auth/logout` mekanizması:** Hangi token'ın iptal edileceği belirsizdi. Çözüm: `LogoutRequest` (refresh_token + all_sessions) tanımlandı. Bölüm 6.1, 14.
- **A6 — `GET /auth/api-keys` şeması:** Yanıt `has_api_key` döndürüyordu ama şema yoktu. Çözüm: `ApiKeyInfo` şeması eklendi. Bölüm 14.

**Küçük tutarsızlıklar (B)**
- **B1 — Docker env notu:** LLM/embedding anahtarlarını işlevsel olarak yalnızca `worker_gen`'in kullandığı belirtildi. Bölüm 13.
- **B2 — `markdown` kütüphanesi** requirements'a eklendi. Bölüm 2, 16.
- **B3 — `WsEvent.status`** opsiyonel yapıldı (`ping` status taşımaz). Bölüm 14.
- **B4 — `ws.py` yorumu** `/api/v1/ws/...` olarak düzeltildi. Bölüm 3.
- **B5 — `unverified`** başlangıç durumu Bölüm 9.4'e eklendi.

**Eksikler (C)**
- **C1 — CORS:** `CORS_ORIGINS` env'e ve main.py middleware'ine eklendi.
- **C2 — Sentry:** `SENTRY_DSN` env'e eklendi.
- **C3 — Eşzamanlı generate-all:** Redis sayacı ile enforcement tanımlandı. Bölüm 20.
- **C4 — Flower auth:** basic-auth notu eklendi. Bölüm 13, 17, 21.

### v2.0 — İlk büyük revizyon (v1.0 incelemesi)

- **Embedding sağlayıcısı** netleştirildi (OpenAI/Voyage); `.env` anahtarları + `embedding_service.py` + fallback modu.
- **EPUB üretimi** (ebooklib) baştan sona işlendi.
- **Semantik sorgu** (title+description embed) netleştirildi.
- **WebSocket auth** (query-param token, 4401/4403) eklendi.
- **Şema çift kaynağı** çözüldü (Alembic tek kaynak, migration.sql otomatik döküm).
- **CMYK→RGB** düzeltmesi, bleed 3mm→3.175mm.
- **DOCX Roman→Arabic** sayfa numarası karmaşıklığı not edildi.
- **Refresh token iptali** (`refresh_tokens`, /logout), **API anahtarı yönetimi**, **dead-letter admin endpoint'leri** (+`users.role`).
- **Varsayılan temperature** 0.8→0.5.
- **"7 adım"→"9 adım"** düzeltmesi, **plan limitleri**, **genişletilmiş testler**, **DOI doğrulama politikası**, **bcrypt 72-byte notu**, **güvenlik kontrol listesi**, **sorumlu kullanım notu**.
