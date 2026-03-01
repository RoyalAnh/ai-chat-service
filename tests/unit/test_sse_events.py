"""
Unit test: verify SSE events are emitted in correct order.
The OpenAI agent is mocked — no real API calls.
"""
import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest

from app.services.chat import stream_chat


async def _fake_agent_stream(
    message: str, history: list
) -> AsyncGenerator[tuple[str, dict], None]:
    """Mock agent that yields two delta chunks then done."""
    yield "delta", {"text": "Hello"}
    yield "delta", {"text": " world"}
    yield "done", {"full_response": "Hello world"}


async def collect_sse_events(gen) -> list[tuple[str, str]]:
    """Parse raw SSE text into list of (event_name, data) tuples."""
    events = []
    current_event = None
    async for chunk in gen:
        for line in chunk.splitlines():
            if line.startswith("event: "):
                current_event = line[len("event: "):]
            elif line.startswith("data: ") and current_event:
                events.append((current_event, line[len("data: "):]))
                current_event = None
    return events


@pytest.mark.asyncio
async def test_sse_event_order(db_session, sample_session_id, sample_user_id):
    """Delta events should arrive before the done event."""
    with patch(
        "app.services.chat.stream_agent_response",
        side_effect=_fake_agent_stream,
    ):
        gen = stream_chat(
            db_session, sample_session_id, sample_user_id, "Hi"
        )
        events = await collect_sse_events(gen)

    event_names = [e[0] for e in events]

    # Should have at least 2 deltas + 1 done
    delta_events = [e for e in events if e[0] == "agent.message.delta"]
    done_events = [e for e in events if e[0] == "agent.message.done"]

    assert len(delta_events) == 2, f"Expected 2 delta events, got {delta_events}"
    assert len(done_events) == 1, f"Expected 1 done event, got {done_events}"

    # done must come last
    assert event_names.index("agent.message.done") > event_names.index(
        "agent.message.delta"
    ), "done event must come after delta events"


@pytest.mark.asyncio
async def test_sse_error_event(db_session, sample_session_id, sample_user_id):
    """On agent error, a failed event should be emitted."""

    async def _failing_agent(message, history):
        yield "error", {"error": "Something went wrong"}

    with patch(
        "app.services.chat.stream_agent_response",
        side_effect=_failing_agent,
    ):
        gen = stream_chat(
            db_session, sample_session_id, sample_user_id, "Hi"
        )
        events = await collect_sse_events(gen)

    event_names = [e[0] for e in events]
    assert "agent.workflow.failed" in event_names
