# Testing Guide — Customer Success Digital FTE

This document shows how to test the full system end-to-end, from a single
unit test to a 1000-message load simulation and failure-recovery drills.

The test suite lives in `tests/` and is organized by layer:

| File                            | What it covers                                              |
| ------------------------------- | ----------------------------------------------------------- |
| `conftest.py`                   | Shared fixtures (ASGI client, mocked queue, fake session)   |
| `test_api.py`                   | FastAPI intake endpoints: Web, Gmail, WhatsApp, health      |
| `test_worker.py`                | Kafka consumer — `process_message()` happy + error paths    |
| `test_agent.py`                 | `run_agent()` + `search_kb`, `create_ticket`, `escalate`, `send_response` |
| `test_agent_tools_history.py`   | Direct tests for the `get_customer_history` agent tool      |
| `test_tickets_api.py`           | Full tickets CRUD: list / get / events / transition / assign / resolve / close |
| `test_metrics_api.py`           | Metrics dashboard + every per-KPI endpoint + `hours` filter |
| `test_services.py`              | CustomerService, ConversationService, TicketService lifecycle |
| `test_load.py`                  | 1000-message throughput / latency simulation                |
| `test_failure_recovery.py`      | Kafka outage, DB hiccup, poison-pill, consumer reconnect    |
| `test_idempotency.py`           | Baseline + xfail tests documenting the dedupe gap           |

`pytest.ini` lives at the **repository root** (not under `tests/`), so `pytest` discovery is standard.

---

## 1. Install test dependencies

```bash
pip install -r requirements.txt
pip install pytest pytest-asyncio httpx
```

---

## 2. Run the full offline test suite (no Postgres / Kafka needed)

Everything except the *real* load test runs fully in-process — the
database, Kafka producer and OpenAI SDK are all stubbed.

```bash
# from the repository root
pytest tests/
```

Expected output (shape, not exact numbers):

```
tests/test_agent.py ........                 [ 25%]
tests/test_api.py ..........                 [ 55%]
tests/test_failure_recovery.py .....         [ 70%]
tests/test_load.py .                         [ 75%]
tests/test_worker.py ....                    [100%]

── Load Test Report ─────────────────────────
  messages sent     : 1000
  duration          : 1.43s
  throughput        : 699.3 req/s
  success rate      : 100.00%
  errors            : 0
  latency p50       :  54.2 ms
  latency p90       : 128.7 ms
  latency p95       : 161.3 ms
  latency p99       : 248.1 ms
─────────────────────────────────────────────

========= 28 passed in 3.12s =========
```

Run a single file:

```bash
pytest tests/test_api.py -v
pytest tests/test_worker.py::test_process_message_happy_path -v
```

---

## 3. End-to-end test against the real stack

This exercises API → Kafka → Worker → Postgres → AI Agent for real.

### 3.1 Start the full stack

```bash
docker compose up -d --build
docker compose ps           # wait until all services are healthy
```

Verify readiness:

```bash
curl -s localhost:8000/health/ready
# {"status":"ready","database":"connected"}
```

### 3.2 Send one message through each channel

```bash
# Web form
curl -s -X POST http://localhost:8000/api/v1/channels/web \
  -H 'Content-Type: application/json' \
  -d '{
    "name":"Alice",
    "email":"alice@example.com",
    "subject":"Cannot log in",
    "message":"I keep getting invalid password errors.",
    "company":"Acme"
  }' | jq

# Gmail webhook
curl -s -X POST http://localhost:8000/api/v1/channels/gmail \
  -H 'Content-Type: application/json' \
  -d '{
    "message_id":"gmail-1",
    "from_email":"bob@example.com",
    "from_name":"Bob",
    "to_email":"support@company.com",
    "subject":"Refund request",
    "body_plain":"I want a refund."
  }' | jq

# WhatsApp webhook
curl -s -X POST http://localhost:8000/api/v1/channels/whatsapp \
  -H 'Content-Type: application/json' \
  -d '{
    "entry":[{
      "message_id":"wa-1",
      "from_number":"+14155551234",
      "from_name":"Carol",
      "body":"Is my order shipped?"
    }]
  }' | jq
```

Each call returns a `conversation_id` and `message_id`. Within a
second or two, the worker should log that it consumed the message and
the agent should store a response in the `messages` table.

### 3.3 Verify the worker processed the message

```bash
docker compose logs -f worker
# Received: topic=customer_messages partition=0 offset=0 ...
# Processing message_id=...
# Agent completed for message_id=... response_length=178
```

Query Postgres for the agent's reply:

```bash
docker compose exec postgres psql -U postgres customer_success -c \
  "SELECT direction, sender, LEFT(content, 80) FROM messages ORDER BY created_at DESC LIMIT 4;"
```

You should see an inbound customer message followed by an outbound
`agent` message.

### 3.4 Check metrics and tickets

```bash
curl -s localhost:8000/api/v1/tickets?limit=5 | jq
curl -s localhost:8000/api/v1/metrics/summary | jq
```

---

## 4. Load test — 1000 messages

### 4.1 Mocked (CI / offline)

Runs in-process, no infra needed, typically finishes in a couple of
seconds:

```bash
pytest tests/test_load.py::test_load_1000_messages_mocked -s
```

The `-s` flag lets the load report print to stdout.

### 4.2 Real stack

Spin the stack up (`docker compose up -d`) and run:

```bash
LOAD_TEST_REAL=1 LOAD_TEST_URL=http://localhost:8000 \
  pytest tests/test_load.py::test_load_1000_messages_real -s
```

Or invoke the script directly for a one-off run with tunables:

```bash
python tests/test_load.py --count 1000 --concurrency 50 --url http://localhost:8000
```

Watch the worker chew through the queue:

```bash
docker compose logs -f worker | grep "Processing message_id"
```

Sanity check: after the run, Postgres should contain ~1000 new inbound
messages plus ~1000 outbound agent responses (modulo in-flight):

```bash
docker compose exec postgres psql -U postgres customer_success -c \
  "SELECT direction, COUNT(*) FROM messages GROUP BY direction;"
```

**Acceptance targets (real stack, local laptop):**

| Metric          | Target         |
| --------------- | -------------- |
| Success rate    | ≥ 99 %         |
| Throughput      | ≥ 200 req/s    |
| API p95 latency | ≤ 500 ms       |
| Worker drain    | ≤ 2 min for 1k |

---

## 5. Failure recovery drills

`tests/test_failure_recovery.py` covers these scenarios automatically:

1. **Producer not started** — `QueueService.enqueue_message` logs and
   drops instead of raising, so the API still returns 200 and the row
   remains in Postgres for replay.
2. **Publish-time broker outage** — the exception bubbles up to the
   intake handler (returns 500). No partial commit.
3. **Poison message** — a failing `run_agent` call triggers a rollback
   + error metric; the next message still processes cleanly.
4. **Consumer reconnect** — `AIOKafkaConsumer.start()` raises once and
   then succeeds; the worker picks up where it left off.
5. **Readiness probe** — returns 5xx when the DB is unreachable, so
   Kubernetes removes the pod from its endpoint set.

Run just the recovery tests:

```bash
pytest tests/test_failure_recovery.py -v
```

### Manual chaos drills against the real stack

With the stack running:

```bash
# 1. Kill Kafka mid-flight
docker compose stop kafka
# POST 20 messages to /api/v1/channels/web
# Observe: API returns 500 (publish fails) — DB rows still exist.

docker compose start kafka
# Replay: tail worker logs — backlog drains once the broker returns.

# 2. Kill Postgres
docker compose stop postgres
curl -i localhost:8000/health/ready       # returns 503
docker compose start postgres
curl -i localhost:8000/health/ready       # returns 200

# 3. Kill the worker
docker compose stop worker
# Send 50 messages — they queue in Kafka (retained).
docker compose start worker
# Worker consumes from committed offset, drains the backlog.
```

---

## 6. Quick reference

```bash
# Unit + integration (mocked)
pytest tests/

# Just one layer
pytest tests/test_api.py
pytest tests/test_worker.py
pytest tests/test_agent.py

# Load test (mocked, fast)
pytest tests/test_load.py -s

# Load test (real stack)
LOAD_TEST_REAL=1 pytest tests/test_load.py -s

# Chaos / recovery
pytest tests/test_failure_recovery.py -v

# Everything verbose
pytest tests/ -v -s
```
