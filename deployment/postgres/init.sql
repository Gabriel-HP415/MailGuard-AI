-- MailGuard-AI — Postgres init for dev compose
--
-- Runs once on first container startup (docker-entrypoint-initdb.d).
-- Created automatically by Postgres for our `mailguard` user + `mailguard_ai`
-- DB via POSTGRES_* env vars, so we only need to create extensions.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";   -- used by some models for IDs
CREATE EXTENSION IF NOT EXISTS "pg_trgm";      -- optional: faster text similarity for search
