from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    DATABASE_URL: str = "sqlite:///./pdptw.db"
    SECRET_KEY: str = "be3a9b510d4a58d7c6028e3be1af7ac258e1e2c189d3c8197f21841561356d3f"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    EMAIL_VERIFICATION_EXPIRE_HOURS: int = 24
    PASSWORD_RESET_EXPIRE_HOURS: int = 1

    INSTANCES_DIR: str = "../instances"
    SOLUTIONS_DIR: str = "../solutions/my_solver"

    DEFAULT_TIME_LIMIT_SEC: float = 60.0
    DEFAULT_SEED: int = 0

    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    GROQ_API_KEY: str = ""

    FRONTEND_URL: str = "http://localhost:5173"

    # Email settings (configure via .env for real email)
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAIL_FROM: str = "noreply@pdptw.local"


settings = Settings()
