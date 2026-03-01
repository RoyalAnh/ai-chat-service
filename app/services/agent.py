from collections.abc import AsyncGenerator
from typing import Any

from agents import Agent, Runner

from app.config import settings

SYSTEM_PROMPT = """You are a helpful, concise, and friendly AI assistant.
You answer questions clearly and accurately.
If you don't know something, you say so honestly.
Keep responses focused and avoid unnecessary verbosity."""


def build_agent() -> Agent:
    return Agent(
        name=settings.AGENT_NAME,
        model=settings.OPENAI_MODEL,
        instructions=SYSTEM_PROMPT,
    )


async def stream_agent_response(
    message: str,
    history: list[dict[str, str]],
) -> AsyncGenerator[tuple[str, dict[str, Any]], None]:
    agent = build_agent()
    messages = history + [{"role": "user", "content": message}]

    full_response = ""

    try:
        result = Runner.run_streamed(agent, input=messages)
        async for event in result.stream_events():
            if event.type == "raw_response_event":
                delta = getattr(event.data, "delta", None)
                if delta:
                    full_response += delta
                    yield "delta", {"text": delta}

        yield "done", {"full_response": full_response}

    except Exception as e:
        yield "error", {"error": str(e)}