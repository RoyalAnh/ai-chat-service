import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.db import ChatMessage, ChatSession, MessageRole


class ChatRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_create_session(
        self, session_id: uuid.UUID, user_id: str
    ) -> ChatSession:
        result = await self.db.execute(
            select(ChatSession).where(
                ChatSession.id == session_id,
                ChatSession.user_id == user_id,
            )
        )
        session = result.scalar_one_or_none()

        if session is None:
            session = ChatSession(id=session_id, user_id=user_id)
            self.db.add(session)
            await self.db.flush()

        return session

    async def add_message(
        self, session_id: uuid.UUID, role: MessageRole, content: str
    ) -> ChatMessage:
        message = ChatMessage(session_id=session_id, role=role, content=content)
        self.db.add(message)
        await self.db.flush()
        return message

    async def get_session_history(
        self, session_id: uuid.UUID, user_id: str
    ) -> ChatSession | None:
        result = await self.db.execute(
            select(ChatSession)
            .where(
                ChatSession.id == session_id,
                ChatSession.user_id == user_id,
            )
            .options(selectinload(ChatSession.messages))
        )
        return result.scalar_one_or_none()

    async def get_messages_for_context(
        self, session_id: uuid.UUID
    ) -> list[ChatMessage]:
        result = await self.db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at)
        )
        return list(result.scalars().all())

    async def delete_session(self, session_id: uuid.UUID, user_id: str) -> bool:
        result = await self.db.execute(
            select(ChatSession).where(
                ChatSession.id == session_id,
                ChatSession.user_id == user_id,
            )
        )
        session = result.scalar_one_or_none()
        if session is None:
            return False
        await self.db.delete(session)
        return True

    async def touch_session(self, session_id: uuid.UUID) -> None:
        result = await self.db.execute(
            select(ChatSession).where(ChatSession.id == session_id)
        )
        session = result.scalar_one_or_none()
        if session:
            session.updated_at = datetime.now(timezone.utc)
