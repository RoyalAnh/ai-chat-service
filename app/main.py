from fastapi import FastAPI

from app.routers.chat import router

app = FastAPI(
    title="AI Chat Service",
    version="1.0.0",
    description="Streaming AI chat service powered by OpenAI Agents SDK",
)

app.include_router(router)
