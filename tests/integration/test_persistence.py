"""
Integration test: verify messages are correctly persisted after a chat turn.
Uses a real test DB (SQLite in-memory), mocks the LLM.
"""
import json
import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.models.db import ChatMessage, MessageRole


async def _mock_agent(message: str, history: list):
    yield "delta", {"text": "Paris"}
    yield "delta", {"text": " is the capital."}
    yield "done", {"full_response": "Paris is the capital."}


@pytest.mark.asyncio
async def test_messages_persisted_after_chat(client, sample_session_id, sample_user_id):
    """After a successful chat, both user and assistant messages exist in DB."""
    with patch("app.services.chat.stream_agent_response", side_effect=_mock_agent):
        response = await client.post(
            "/api/v1/chat/stream",
            json={
                "session_id": str(sample_session_id),
                "user_id": sample_user_id,
                "message": "What is the capital of France?",
            },
        )
        # Consume the stream
        assert response.status_code == 200
        content = response.text

    # Verify SSE done event was emitted
    assert "agent.message.done" in content

    # Fetch history via API
    history_response = await client.get(
        f"/api/v1/sessions/{sample_session_id}/history",
        params={"user_id": sample_user_id},
    )
    assert history_response.status_code == 200
    data = history_response.json()

    messages = data["messages"]
    assert len(messages) == 2

    user_msg = next(m for m in messages if m["role"] == "user")
    assistant_msg = next(m for m in messages if m["role"] == "assistant")

    assert user_msg["content"] == "What is the capital of France?"
    assert assistant_msg["content"] == "Paris is the capital."


@pytest.mark.asyncio
async def test_session_isolation(client, sample_user_id):
    """A user cannot access another user's session."""
    session_id = uuid.uuid4()

    with patch("app.services.chat.stream_agent_response", side_effect=_mock_agent):
        await client.post(
            "/api/v1/chat/stream",
            json={
                "session_id": str(session_id),
                "user_id": sample_user_id,
                "message": "Hello",
            },
        )

    # Different user tries to access the session
    response = await client.get(
        f"/api/v1/sessions/{session_id}/history",
        params={"user_id": "other-user-999"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_session(client, sample_session_id, sample_user_id):
    """Deleting a session removes it and returns 404 on subsequent access."""
    with patch("app.services.chat.stream_agent_response", side_effect=_mock_agent):
        await client.post(
            "/api/v1/chat/stream",
            json={
                "session_id": str(sample_session_id),
                "user_id": sample_user_id,
                "message": "Hello",
            },
        )

    delete_response = await client.delete(
        f"/api/v1/sessions/{sample_session_id}",
        params={"user_id": sample_user_id},
    )
    assert delete_response.status_code == 204

    history_response = await client.get(
        f"/api/v1/sessions/{sample_session_id}/history",
        params={"user_id": sample_user_id},
    )
    assert history_response.status_code == 404
