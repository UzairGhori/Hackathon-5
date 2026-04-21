# ============================================================
# Customer Success Digital FTE — PostgreSQL 16 + pgvector
#
# Based on pgvector/pgvector:pg16 which includes the vector
# extension for semantic search / RAG embeddings.
#
# The schema is baked into the image and runs automatically
# on first container start (empty data volume).
# ============================================================

FROM pgvector/pgvector:pg16

# Bake the DDL into the image — runs on first initdb only
COPY database/schema.sql /docker-entrypoint-initdb.d/01-schema.sql

ENV POSTGRES_USER=postgres \
    POSTGRES_PASSWORD=postgres \
    POSTGRES_DB=customer_success
