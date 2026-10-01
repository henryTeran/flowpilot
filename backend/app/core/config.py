from urllib.parse import urlparse

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
    ENABLE_RATE_LIMITING: bool = True
    RATE_LIMIT_AUTH_WINDOW_SECONDS: int = 60
    RATE_LIMIT_AUTH_MAX_REQUESTS: int = 5

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def cors_allow_methods(self) -> list[str]:
        if self.is_production_like_env:
            return ["GET", "POST", "PATCH", "OPTIONS"]
        return ["*"]

    @property
    def cors_allow_headers(self) -> list[str]:
        if self.is_production_like_env:
            return ["Authorization", "Content-Type", "X-Request-ID"]
        return ["*"]

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

    def validate_runtime_security(self) -> None:
        if not self.is_production_like_env:
            return

        if self.APP_DEBUG:
            raise RuntimeError("APP_DEBUG must be false in production.")

        if self.has_weak_secret_key:
            raise RuntimeError("SECRET_KEY is weak or default in production.")

        if not self.ENABLE_RATE_LIMITING:
            raise RuntimeError("ENABLE_RATE_LIMITING must be true in production.")

        if not self.cors_origins_list:
            raise RuntimeError("CORS_ORIGINS cannot be empty in production.")

        for origin in self.cors_origins_list:
            if origin == "*":
                raise RuntimeError("CORS wildcard is forbidden in production.")

            parsed = urlparse(origin)
            if parsed.scheme != "https":
                raise RuntimeError("CORS origins must use HTTPS in production.")

            hostname = (parsed.hostname or "").lower()
            if hostname in {"localhost", "127.0.0.1"}:
                raise RuntimeError("Localhost CORS origins are forbidden in production.")


settings = Settings()
