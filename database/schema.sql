-- ============================================================
-- Customer Success Digital FTE — CRM Schema
-- Production-grade PostgreSQL schema
-- ============================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";       -- pgvector for embeddings

-- Enums
CREATE TYPE channel_type      AS ENUM ('web', 'gmail', 'whatsapp');
CREATE TYPE message_direction AS ENUM ('inbound', 'outbound');
CREATE TYPE message_sender    AS ENUM ('customer', 'agent', 'system');
CREATE TYPE ticket_status     AS ENUM ('open', 'in_progress', 'waiting_on_customer', 'escalated', 'resolved', 'closed');
CREATE TYPE ticket_priority   AS ENUM ('low', 'medium', 'high', 'critical');
CREATE TYPE ticket_event_type AS ENUM ('created', 'status_changed', 'priority_changed', 'assigned', 'escalated', 'note_added', 'resolved', 'closed');

-- ============================================================
-- 1. customers
-- Core customer record. One row per unique customer.
-- ============================================================
CREATE TABLE customers (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    full_name   VARCHAR(255) NOT NULL,
    company     VARCHAR(255),
    metadata    JSONB NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_customers_company    ON customers (company);
CREATE INDEX idx_customers_created_at ON customers (created_at);
CREATE INDEX idx_customers_metadata   ON customers USING gin (metadata);

-- ============================================================
-- 2. customer_identifiers
-- Links a customer to one or more channel identities
-- (email address, whatsapp phone, web session token, etc.)
-- ============================================================
CREATE TABLE customer_identifiers (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    customer_id   UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    channel       channel_type NOT NULL,
    identifier    VARCHAR(512) NOT NULL,   -- email, phone, session id
    is_primary    BOOLEAN NOT NULL DEFAULT false,
    verified      BOOLEAN NOT NULL DEFAULT false,
    metadata      JSONB NOT NULL DEFAULT '{}',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX idx_ci_channel_identifier ON customer_identifiers (channel, identifier);
CREATE INDEX idx_ci_customer_id               ON customer_identifiers (customer_id);

-- ============================================================
-- 3. conversations
-- A conversation groups messages within a channel session.
-- A customer can have many conversations over time.
-- ============================================================
CREATE TABLE conversations (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    customer_id   UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    channel       channel_type NOT NULL,
    subject       VARCHAR(512),
    status        VARCHAR(32) NOT NULL DEFAULT 'active',
    metadata      JSONB NOT NULL DEFAULT '{}',
    started_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at      TIMESTAMPTZ,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_conversations_customer_id ON conversations (customer_id);
CREATE INDEX idx_conversations_channel     ON conversations (channel);
CREATE INDEX idx_conversations_status      ON conversations (status);
CREATE INDEX idx_conversations_started_at  ON conversations (started_at);

-- ============================================================
-- 4. messages
-- Individual messages within a conversation.
-- ============================================================
CREATE TABLE messages (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id   UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    direction         message_direction NOT NULL,
    sender            message_sender NOT NULL,
    content           TEXT NOT NULL,
    channel           channel_type NOT NULL,
    channel_message_id VARCHAR(512),          -- external id from gmail/whatsapp
    metadata          JSONB NOT NULL DEFAULT '{}',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_messages_conversation_id   ON messages (conversation_id);
CREATE INDEX idx_messages_created_at        ON messages (created_at);
CREATE INDEX idx_messages_channel_message   ON messages (channel, channel_message_id);

-- ============================================================
-- 5. tickets
-- Support tickets created from conversations.
-- One conversation may produce one ticket.
-- ============================================================
CREATE TABLE tickets (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id  UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    customer_id      UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    channel          channel_type NOT NULL,
    subject          VARCHAR(512) NOT NULL,
    description      TEXT,
    status           ticket_status NOT NULL DEFAULT 'open',
    priority         ticket_priority NOT NULL DEFAULT 'medium',
    assigned_to      VARCHAR(255),            -- human agent or AI agent id
    tags             TEXT[] DEFAULT '{}',
    metadata         JSONB NOT NULL DEFAULT '{}',
    resolved_at      TIMESTAMPTZ,
    closed_at        TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_tickets_conversation_id ON tickets (conversation_id);
CREATE INDEX idx_tickets_customer_id     ON tickets (customer_id);
CREATE INDEX idx_tickets_status          ON tickets (status);
CREATE INDEX idx_tickets_priority        ON tickets (priority);
CREATE INDEX idx_tickets_assigned_to     ON tickets (assigned_to);
CREATE INDEX idx_tickets_created_at      ON tickets (created_at);
CREATE INDEX idx_tickets_tags            ON tickets USING gin (tags);

-- ============================================================
-- 6. ticket_events
-- Immutable audit log of every state change on a ticket.
-- ============================================================
CREATE TABLE ticket_events (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticket_id    UUID NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    event_type   ticket_event_type NOT NULL,
    actor        VARCHAR(255) NOT NULL,      -- 'ai_agent', 'system', or human id
    old_value    JSONB,
    new_value    JSONB,
    note         TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_te_ticket_id  ON ticket_events (ticket_id);
CREATE INDEX idx_te_event_type ON ticket_events (event_type);
CREATE INDEX idx_te_created_at ON ticket_events (created_at);

-- ============================================================
-- 7. knowledge_base
-- Articles / FAQ entries the AI agent retrieves via RAG.
-- Uses pgvector for semantic search.
-- ============================================================
CREATE TABLE knowledge_base (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title        VARCHAR(512) NOT NULL,
    content      TEXT NOT NULL,
    category     VARCHAR(255),
    tags         TEXT[] DEFAULT '{}',
    embedding    vector(1536),               -- OpenAI text-embedding-3-small dimension
    metadata     JSONB NOT NULL DEFAULT '{}',
    is_active    BOOLEAN NOT NULL DEFAULT true,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_kb_category   ON knowledge_base (category);
CREATE INDEX idx_kb_tags       ON knowledge_base USING gin (tags);
CREATE INDEX idx_kb_active     ON knowledge_base (is_active);
CREATE INDEX idx_kb_embedding  ON knowledge_base USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- ============================================================
-- 8. channel_configs
-- Per-channel configuration (API keys, webhook URLs, etc.)
-- Stored as JSONB so each channel can have its own shape.
-- ============================================================
CREATE TABLE channel_configs (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    channel      channel_type NOT NULL UNIQUE,
    is_enabled   BOOLEAN NOT NULL DEFAULT true,
    config       JSONB NOT NULL DEFAULT '{}',   -- keys, tokens, webhook urls
    metadata     JSONB NOT NULL DEFAULT '{}',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- 9. agent_metrics
-- Tracks AI agent performance per conversation / ticket.
-- ============================================================
CREATE TABLE agent_metrics (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id     UUID REFERENCES conversations(id) ON DELETE SET NULL,
    ticket_id           UUID REFERENCES tickets(id) ON DELETE SET NULL,
    channel             channel_type NOT NULL,
    response_time_ms    INTEGER,                  -- time to first AI response
    tokens_input        INTEGER,
    tokens_output       INTEGER,
    model_used          VARCHAR(128),
    resolved_by_ai      BOOLEAN NOT NULL DEFAULT false,
    escalated           BOOLEAN NOT NULL DEFAULT false,
    customer_sentiment  VARCHAR(32),              -- positive, neutral, negative
    metadata            JSONB NOT NULL DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_am_conversation_id ON agent_metrics (conversation_id);
CREATE INDEX idx_am_ticket_id       ON agent_metrics (ticket_id);
CREATE INDEX idx_am_channel         ON agent_metrics (channel);
CREATE INDEX idx_am_created_at      ON agent_metrics (created_at);
CREATE INDEX idx_am_resolved_by_ai  ON agent_metrics (resolved_by_ai);

-- ============================================================
-- Trigger: auto-update updated_at columns
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_customers_updated_at
    BEFORE UPDATE ON customers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_conversations_updated_at
    BEFORE UPDATE ON conversations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_tickets_updated_at
    BEFORE UPDATE ON tickets
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_knowledge_base_updated_at
    BEFORE UPDATE ON knowledge_base
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_channel_configs_updated_at
    BEFORE UPDATE ON channel_configs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
