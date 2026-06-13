"""initial schema — 10 tablo, indexler, triggerlar, view'lar (Spec Bölüm 5)

Revision ID: 001
Revises:
Create Date: 2026-06-13

Şemanın tek doğruluk kaynağı bu migration'dır (Bölüm 5.5). pgvector, HNSW index,
trigger ve view gibi nesneler ham SQL ile oluşturulur.
"""
from alembic import op

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------ #
    # 0) Extension
    # ------------------------------------------------------------------ #
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # ------------------------------------------------------------------ #
    # 1) Tablolar
    # ------------------------------------------------------------------ #
    op.execute(
        """
        CREATE TABLE users (
            id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email              VARCHAR(255) NOT NULL UNIQUE,
            password_hash      VARCHAR(255) NOT NULL,
            full_name          VARCHAR(200) NOT NULL,
            role               VARCHAR(20)  DEFAULT 'user',
            plan               VARCHAR(20)  DEFAULT 'free',
            api_key_hash       VARCHAR(255) UNIQUE,
            api_key_prefix     VARCHAR(12),
            api_key_created_at TIMESTAMPTZ,
            is_active          BOOLEAN DEFAULT true,
            email_verified     BOOLEAN DEFAULT false,
            created_at         TIMESTAMPTZ DEFAULT now(),
            updated_at         TIMESTAMPTZ DEFAULT now(),
            last_login_at      TIMESTAMPTZ
        );
        """
    )

    op.execute(
        """
        CREATE TABLE refresh_tokens (
            id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            jti        VARCHAR(64) NOT NULL UNIQUE,
            expires_at TIMESTAMPTZ NOT NULL,
            revoked    BOOLEAN DEFAULT false,
            created_at TIMESTAMPTZ DEFAULT now(),
            revoked_at TIMESTAMPTZ,
            user_agent VARCHAR(300)
        );
        """
    )

    op.execute(
        """
        CREATE TABLE projects (
            id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id           UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title             VARCHAR(500) NOT NULL,
            subtitle          VARCHAR(500),
            genre             VARCHAR(100),
            kdp_format        VARCHAR(20) DEFAULT '6x9',
            citation_style    VARCHAR(20) DEFAULT 'APA',
            language          VARCHAR(10) DEFAULT 'tr',
            status            VARCHAR(20) DEFAULT 'draft',
            target_word_count INTEGER DEFAULT 50000,
            total_word_count  INTEGER DEFAULT 0,
            chapter_count     SMALLINT DEFAULT 0,
            created_at        TIMESTAMPTZ DEFAULT now(),
            updated_at        TIMESTAMPTZ DEFAULT now()
        );
        """
    )

    op.execute(
        """
        CREATE TABLE project_settings (
            id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id         UUID NOT NULL UNIQUE REFERENCES projects(id) ON DELETE CASCADE,
            tone_profile       VARCHAR(50) DEFAULT 'academic',
            audience_level     VARCHAR(50) DEFAULT 'graduate',
            academic_field     VARCHAR(100),
            human_writing_mode BOOLEAN DEFAULT true,
            style_overrides    JSONB DEFAULT '{}'::jsonb,
            llm_config         JSONB DEFAULT '{"model":"claude-sonnet-4-6","temperature":0.5,"max_tokens":8000}'::jsonb,
            created_at         TIMESTAMPTZ DEFAULT now(),
            updated_at         TIMESTAMPTZ DEFAULT now()
        );
        """
    )

    op.execute(
        """
        CREATE TABLE chapters (
            id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id        UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            order_index       SMALLINT NOT NULL,
            title             VARCHAR(500) NOT NULL,
            description       TEXT,
            content           TEXT,
            content_summary   TEXT,
            embedding         VECTOR(1536),
            word_count        INTEGER DEFAULT 0,
            target_word_count INTEGER,
            status            VARCHAR(20) DEFAULT 'pending',
            retry_count       SMALLINT DEFAULT 0,
            generated_at      TIMESTAMPTZ,
            updated_at        TIMESTAMPTZ DEFAULT now(),
            CONSTRAINT uq_chapters_project_order UNIQUE (project_id, order_index)
        );
        """
    )

    op.execute(
        """
        CREATE TABLE chapter_versions (
            id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            chapter_id     UUID NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
            version_number SMALLINT NOT NULL,
            content        TEXT NOT NULL,
            change_reason  VARCHAR(50) DEFAULT 'ai_generation',
            token_cost     INTEGER DEFAULT 0,
            created_at     TIMESTAMPTZ DEFAULT now(),
            CONSTRAINT uq_chversions_chapter_version UNIQUE (chapter_id, version_number)
        );
        """
    )

    op.execute(
        """
        CREATE TABLE citations (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            chapter_id          UUID NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
            marker              VARCHAR(20) NOT NULL,
            doi                 VARCHAR(200),
            raw_title           TEXT NOT NULL,
            authors             TEXT,
            journal             VARCHAR(300),
            pub_year            SMALLINT,
            publisher           VARCHAR(300),
            citation_format     VARCHAR(20) DEFAULT 'APA',
            formatted_text      TEXT,
            doi_verified        BOOLEAN DEFAULT false,
            verification_status VARCHAR(20) DEFAULT 'unverified',
            crossref_data       JSONB,
            created_at          TIMESTAMPTZ DEFAULT now()
        );
        """
    )

    op.execute(
        """
        CREATE TABLE media_assets (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            chapter_id      UUID NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
            asset_type      VARCHAR(30) NOT NULL,
            s3_path         TEXT NOT NULL,
            caption         TEXT,
            alt_text        TEXT,
            position_index  SMALLINT DEFAULT 0,
            width_px        SMALLINT,
            height_px       SMALLINT,
            file_size_bytes INTEGER,
            dpi             SMALLINT DEFAULT 300,
            created_at      TIMESTAMPTZ DEFAULT now()
        );
        """
    )

    op.execute(
        """
        CREATE TABLE task_logs (
            id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            chapter_id     UUID NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
            celery_task_id VARCHAR(200) NOT NULL UNIQUE,
            worker_name    VARCHAR(100),
            status         VARCHAR(20) DEFAULT 'queued',
            tokens_input   INTEGER DEFAULT 0,
            tokens_output  INTEGER DEFAULT 0,
            duration_ms    INTEGER,
            error_message  TEXT,
            started_at     TIMESTAMPTZ,
            finished_at    TIMESTAMPTZ
        );
        """
    )

    op.execute(
        """
        CREATE TABLE export_jobs (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            format          VARCHAR(10) NOT NULL,
            status          VARCHAR(20) DEFAULT 'pending',
            s3_path         TEXT,
            presigned_url   TEXT,
            url_expires_at  TIMESTAMPTZ,
            file_size_bytes INTEGER,
            error_message   TEXT,
            created_at      TIMESTAMPTZ DEFAULT now(),
            finished_at     TIMESTAMPTZ
        );
        """
    )

    # ------------------------------------------------------------------ #
    # 2) Indexler (Bölüm 5.2)
    # ------------------------------------------------------------------ #
    op.execute(
        """
        CREATE INDEX idx_chapters_embedding_hnsw ON chapters
          USING hnsw (embedding vector_cosine_ops)
          WITH (m = 16, ef_construction = 64);
        """
    )
    op.execute(
        """
        CREATE INDEX idx_chapters_status_active ON chapters (status)
          WHERE status NOT IN ('done', 'skipped');
        """
    )
    op.execute(
        """
        CREATE INDEX idx_citations_doi ON citations (doi)
          WHERE doi IS NOT NULL;
        """
    )
    op.execute(
        """
        CREATE INDEX idx_ej_expired_urls ON export_jobs (url_expires_at)
          WHERE presigned_url IS NOT NULL AND url_expires_at IS NOT NULL;
        """
    )
    op.execute(
        """
        CREATE INDEX idx_rt_expired ON refresh_tokens (expires_at)
          WHERE revoked = false;
        """
    )
    # Performans yardımcı indexleri (FK kolonları)
    op.execute("CREATE INDEX idx_projects_user ON projects (user_id);")
    op.execute("CREATE INDEX idx_chapters_project ON chapters (project_id);")
    op.execute("CREATE INDEX idx_citations_chapter ON citations (chapter_id);")
    op.execute("CREATE INDEX idx_tl_chapter ON task_logs (chapter_id);")
    op.execute("CREATE INDEX idx_ej_project ON export_jobs (project_id);")

    # ------------------------------------------------------------------ #
    # 3) Trigger fonksiyonları + triggerlar (Bölüm 5.3)
    # ------------------------------------------------------------------ #
    op.execute(
        """
        CREATE OR REPLACE FUNCTION fn_update_updated_at() RETURNS trigger AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    for tbl in ("users", "projects", "project_settings", "chapters"):
        op.execute(
            f"""
            CREATE TRIGGER trg_{tbl}_updated_at
              BEFORE UPDATE ON {tbl}
              FOR EACH ROW EXECUTE FUNCTION fn_update_updated_at();
            """
        )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION fn_sync_project_stats() RETURNS trigger AS $$
        DECLARE
            pid UUID;
        BEGIN
            IF (TG_OP = 'DELETE') THEN
                pid := OLD.project_id;
            ELSE
                pid := NEW.project_id;
            END IF;
            UPDATE projects p SET
                total_word_count = COALESCE(
                    (SELECT SUM(word_count) FROM chapters WHERE project_id = pid), 0),
                chapter_count = (SELECT COUNT(*) FROM chapters WHERE project_id = pid)
            WHERE p.id = pid;
            IF (TG_OP = 'DELETE') THEN
                RETURN OLD;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_chapters_sync_stats
          AFTER INSERT OR DELETE OR UPDATE OF word_count ON chapters
          FOR EACH ROW EXECUTE FUNCTION fn_sync_project_stats();
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION fn_auto_version_number() RETURNS trigger AS $$
        BEGIN
            IF NEW.version_number IS NULL OR NEW.version_number = 0 THEN
                SELECT COALESCE(MAX(version_number), 0) + 1
                  INTO NEW.version_number
                  FROM chapter_versions
                 WHERE chapter_id = NEW.chapter_id;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_chversions_auto_number
          BEFORE INSERT ON chapter_versions
          FOR EACH ROW EXECUTE FUNCTION fn_auto_version_number();
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION fn_snapshot_on_done() RETURNS trigger AS $$
        BEGIN
            IF NEW.status = 'done'
               AND OLD.status IS DISTINCT FROM 'done'
               AND NEW.content IS NOT NULL THEN
                INSERT INTO chapter_versions (chapter_id, content, change_reason)
                VALUES (NEW.id, NEW.content, 'ai_generation');
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_chapters_snapshot_on_done
          AFTER UPDATE OF status ON chapters
          FOR EACH ROW EXECUTE FUNCTION fn_snapshot_on_done();
        """
    )

    # ------------------------------------------------------------------ #
    # 4) View'lar (Bölüm 5.4)
    # ------------------------------------------------------------------ #
    op.execute(
        """
        CREATE VIEW v_project_progress AS
        SELECT
            p.id                AS project_id,
            p.title             AS title,
            p.status            AS project_status,
            p.chapter_count     AS chapter_count,
            p.total_word_count  AS total_word_count,
            p.target_word_count AS target_word_count,
            CASE WHEN p.target_word_count > 0
                 THEN ROUND(100.0 * p.total_word_count / p.target_word_count, 2)
                 ELSE 0 END     AS word_pct,
            COUNT(c.id) FILTER (WHERE c.status = 'done')       AS chapters_done,
            COUNT(c.id) FILTER (WHERE c.status = 'generating') AS chapters_generating,
            COUNT(c.id) FILTER (WHERE c.status = 'error')      AS chapters_error,
            COUNT(c.id) FILTER (WHERE c.status = 'pending')    AS chapters_pending,
            CASE WHEN COUNT(c.id) > 0
                 THEN ROUND(100.0 * COUNT(c.id) FILTER (WHERE c.status = 'done') / COUNT(c.id), 2)
                 ELSE 0 END     AS chapter_pct
        FROM projects p
        LEFT JOIN chapters c ON c.project_id = p.id
        GROUP BY p.id;
        """
    )
    op.execute(
        """
        CREATE VIEW v_token_costs AS
        SELECT
            p.id     AS project_id,
            p.title  AS title,
            p.user_id AS user_id,
            COALESCE(SUM(tl.tokens_input), 0)                  AS total_tokens_input,
            COALESCE(SUM(tl.tokens_output), 0)                 AS total_tokens_output,
            COALESCE(SUM(tl.tokens_input + tl.tokens_output), 0) AS total_tokens,
            COUNT(tl.id) FILTER (WHERE tl.status = 'success')  AS successful_tasks,
            COUNT(tl.id) FILTER (WHERE tl.status = 'failure')  AS failed_tasks,
            AVG(tl.duration_ms)                                AS avg_duration_ms
        FROM projects p
        LEFT JOIN chapters c  ON c.project_id = p.id
        LEFT JOIN task_logs tl ON tl.chapter_id = c.id
        GROUP BY p.id;
        """
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS v_token_costs;")
    op.execute("DROP VIEW IF EXISTS v_project_progress;")

    op.execute("DROP TRIGGER IF EXISTS trg_chapters_snapshot_on_done ON chapters;")
    op.execute("DROP TRIGGER IF EXISTS trg_chversions_auto_number ON chapter_versions;")
    op.execute("DROP TRIGGER IF EXISTS trg_chapters_sync_stats ON chapters;")
    for tbl in ("users", "projects", "project_settings", "chapters"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{tbl}_updated_at ON {tbl};")

    op.execute("DROP FUNCTION IF EXISTS fn_snapshot_on_done();")
    op.execute("DROP FUNCTION IF EXISTS fn_auto_version_number();")
    op.execute("DROP FUNCTION IF EXISTS fn_sync_project_stats();")
    op.execute("DROP FUNCTION IF EXISTS fn_update_updated_at();")

    for tbl in (
        "export_jobs",
        "task_logs",
        "media_assets",
        "citations",
        "chapter_versions",
        "chapters",
        "project_settings",
        "projects",
        "refresh_tokens",
        "users",
    ):
        op.execute(f"DROP TABLE IF EXISTS {tbl} CASCADE;")
