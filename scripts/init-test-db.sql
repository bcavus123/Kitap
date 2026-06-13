-- Postgres ilk başlatılırken çalışır (docker-entrypoint-initdb.d).
-- pytest 'kitap_test' veritabanına bağlanır (Spec Bölüm 15); burada oluşturulur.
-- pgvector extension'ı her veritabanında migration tarafından kurulur (CREATE EXTENSION IF NOT EXISTS vector).
CREATE DATABASE kitap_test;
