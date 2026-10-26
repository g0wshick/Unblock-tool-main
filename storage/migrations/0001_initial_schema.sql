-- Superseded by Alembic (see /alembic and storage/models/) for table schema.
-- Kept only so docker-entrypoint-initdb.d enables the pgvector extension on
-- first container start; run `alembic upgrade head` to create the tables.

CREATE EXTENSION IF NOT EXISTS vector;
