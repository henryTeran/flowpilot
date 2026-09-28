from functools import cached_property

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "FlowPilot Institut Manager"
    APP_ENV: str = "local"
    APP_DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"

    SECRET_KEY: str = "change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    DATABASE_URL: str = "postgresql+psycopg2://flowpilot:flowpilot@localhost:5432/flowpilot_flow"
    REDIS_URL: str = "redis://localhost:6379/0"
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"
    AUTO_CREATE_SCHEMA_ON_STARTUP: bool = True
    ENABLE_SECURITY_HEADERS: bool = True

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @cached_property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def app_env_normalized(self) -> str:
        return self.APP_ENV.strip().lower()

    @property
    def is_local_like_env(self) -> bool:
        return self.app_env_normalized in {"local", "dev", "development", "test"}

    @property
    def is_production_like_env(self) -> bool:
        return self.app_env_normalized in {"prod", "production"}

    @property
    def has_weak_secret_key(self) -> bool:
        weak_defaults = {"change-me", "change-me-in-production"}
        return self.SECRET_KEY in weak_defaults or len(self.SECRET_KEY) < 16


settings = Settings()
