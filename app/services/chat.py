import asyncio
import json
import uuid
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.db import MessageRole
from app.repositories.chat import ChatRepository
from app.services.agent import stream_agent_response


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def stream_chat(
    db: AsyncSession,
    session_id: uuid.UUID,
    user_id: str,
    message: str,
) -> AsyncGenerator[str, None]:
    repo = ChatRepository(db)

    # 1. Get or create session
    await repo.get_or_create_session(session_id, user_id)

    # 2. Save user message before running agent
    await repo.add_message(session_id, MessageRole.user, message)
    await db.commit()

    # 3. Load history for context 
    history_msgs = await repo.get_messages_for_context(session_id)
    history = [
        {"role": msg.role.value, "content": msg.content}
        for msg in history_msgs[:-1]  # exclude last (current user message)
    ]

    # 4. Stream agent response + heartbeat concurrently
    full_response = ""
    heartbeat_task: asyncio.Task | None = None
    queue: asyncio.Queue[str | None] = asyncio.Queue()

    async def heartbeat_producer():
        while True:
            await asyncio.sleep(settings.HEARTBEAT_INTERVAL)
            await queue.put(_sse("heartbeat", {"status": "alive"}))

    async def agent_producer():
        nonlocal full_response
        try:
            async for event_type, data in stream_agent_response(message, history):
                if event_type == "delta":
                    full_response += data["text"]
                    await queue.put(_sse("agent.message.delta", {"text": data["text"]}))
                elif event_type == "done":
                    await queue.put(None)  # signal completion
                elif event_type == "error":
                    await queue.put(_sse("agent.workflow.failed", {"error": data["error"]}))
                    await queue.put(None)
        except Exception as e:
            await queue.put(_sse("agent.workflow.failed", {"error": str(e)}))
            await queue.put(None)

    heartbeat_task = asyncio.create_task(heartbeat_producer())
    agent_task = asyncio.create_task(agent_producer())

    try:
        while True:
            item = await queue.get()
            if item is None:
                break
            yield item
    finally:
        heartbeat_task.cancel()
        agent_task.cancel()
        with suppress_cancelled():
            await heartbeat_task
        with suppress_cancelled():
            await agent_task

    # 5. Save assistant reply after streaming completes
    if full_response:
        await repo.add_message(session_id, MessageRole.assistant, full_response)
        await repo.touch_session(session_id)
        await db.commit()

    yield _sse("agent.message.done", {"session_id": str(session_id)})


class suppress_cancelled:
    """Context manager to suppress CancelledError."""
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, *_):
        return exc_type is asyncio.CancelledError

    def __enter__(self):
        return self

    def __exit__(self, exc_type, *_):
        return exc_type is asyncio.CancelledError
