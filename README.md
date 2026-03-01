# AI Chat Service

A streaming AI chat service built with FastAPI, OpenAI Agents SDK, and PostgreSQL.

## Requirements

- Docker & Docker Compose
- An OpenAI API key

## Setup & Run

```bash
# 1. Clone the repo
git clone <repo-url> && cd ai-chat-service

# 2. Copy env file and add your OpenAI key
cp .env.example .env
# Edit .env and set OPENAI_API_KEY=sk-...

# 3. Start everything (DB + app + migrations)
docker compose up --build
```

The service will be available at `http://localhost:8000`.

Migrations run automatically on startup via `alembic upgrade head`.

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/chat/stream` | Stream a chat response via SSE |
| `GET` | `/api/v1/sessions/{session_id}/history?user_id=...` | Get session history |
| `DELETE` | `/api/v1/sessions/{session_id}?user_id=...` | Delete a session |
| `GET` | `/api/v1/health` | Health check |

### Example: Stream a chat message

```bash
curl -N -X POST http://localhost:8000/api/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
    "user_id": "user-123",
    "message": "What is LLM?"
  }'
```

### Example: Get history

```bash
curl "http://localhost:8000/api/v1/sessions/a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11/history?user_id=user-123"
```

## Running Tests

```bash
# Install dependencies locally
pip install -r requirements.txt
pip install aiosqlite

# Run all tests
pytest

# Run only unit tests
pytest tests/unit/

# Run only integration tests
pytest tests/integration/
```

## Design Choices & Trade-offs

### Layered architecture
The code is split into Router → Service → Repository layers. Routers handle HTTP concerns, services contain business logic (orchestrating the agent and DB), and repositories are the only layer touching SQLAlchemy directly. This keeps each layer independently testable and easy to swap out (e.g., replacing the agent SDK without touching DB code).

### Streaming with concurrent heartbeat
The streaming endpoint uses an `asyncio.Queue` to fan-in two concurrent producers: the agent stream and a periodic heartbeat task. This avoids blocking the heartbeat on agent output and ensures clients with aggressive timeout settings stay connected on slow responses. The queue approach is clean to reason about and extend (e.g., adding tool-call events in future).

### User isolation at the repository level
All DB queries filter by both `session_id` and `user_id`. There is no auth middleware — `user_id` is a plain string passed in the request body — but ownership is enforced at query time. This means a user who guesses another session's UUID still gets a 404, which is sufficient for the scope of this assignment. In production, this would be backed by JWT claims rather than a request body field.

### SQLite for tests
Integration tests use SQLite (via `aiosqlite`) instead of a live PostgreSQL instance. This keeps tests fast and dependency-free. The one caveat is that PostgreSQL-specific types (UUID, ENUM) are abstracted away by SQLAlchemy, so the tests still exercise the full ORM layer correctly. For CI/CD, a real Postgres test container would be preferable.
