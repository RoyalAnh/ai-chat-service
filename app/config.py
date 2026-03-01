from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://chatuser:chatpass@localhost:5432/chatdb"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    AGENT_NAME: str = "Assistant"
    HEARTBEAT_INTERVAL: int = 15

    class Config:
        env_file = ".env"


settings = Settings()
