import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.repositories.chat import ChatRepository
from app.schemas.chat import ChatRequest, SessionHistoryOut, MessageOut
from app.services.chat import stream_chat

router = APIRouter(prefix="/api/v1")


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.post("/chat/stream")
async def chat_stream(
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    return StreamingResponse(
        stream_chat(db, body.session_id, body.user_id, body.message),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/sessions/{session_id}/history", response_model=SessionHistoryOut)
async def get_session_history(
    session_id: uuid.UUID,
    user_id: str,
    db: AsyncSession = Depends(get_db),
):
    repo = ChatRepository(db)
    session = await repo.get_session_history(session_id, user_id)

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    return SessionHistoryOut(
        session_id=session.id,
        messages=[
            MessageOut(
                role=msg.role.value,
                content=msg.content,
                created_at=msg.created_at,
            )
            for msg in sorted(session.messages, key=lambda m: m.created_at)
        ],
    )


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: uuid.UUID,
    user_id: str,
    db: AsyncSession = Depends(get_db),
):
    repo = ChatRepository(db)
    deleted = await repo.delete_session(session_id, user_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )
    await db.commit()
