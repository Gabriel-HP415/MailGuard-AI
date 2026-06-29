"""Application configuration loaded from environment variables."""

from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---------- General ----------
    app_name: str = "MailGuard-AI"
    app_env: str = "development"
    app_debug: bool = True
    app_version: str = "1.0.0"

    # ---------- Backend ----------
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    backend_url: str = "http://localhost:8000"

    # ---------- Database ----------
    db_host: str = "localhost"
    db_port: int = 3306
    db_name: str = "mailguard_ai"
    db_user: str = "mailguard"
    db_password: str = "change_me_in_production"

    database_url: str | None = None

    # ---------- Authentication ----------
    jwt_secret_key: str = "replace_with_long_random_string"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 1440

    # ---------- Firebase Authentication (Chrome extension sign-in) ----------
    firebase_enabled: bool = False
    firebase_project_id: str = ""
    firebase_credentials_path: str = "secrets/firebase-service-account.json"
    firebase_credentials_json: str = ""  # Inline JSON for cloud deployments
    firebase_web_api_key: str = ""  # Public Web API key (Firebase project settings)
    firebase_oauth_client_id: str = ""  # Chrome extension OAuth client (Web application type)

    # ---------- CORS ----------
    # Accept a comma-separated string from env (Render, plain `.env`) or a JSON
    # array. pydantic-settings v2 runs JSON decode BEFORE field validators, so
    # if we declared `List[str]` directly a value like
    # `chrome-extension://*,http://localhost:5500` would crash on
    # `json.loads(...)`. Reading as `str` and splitting below sidesteps that.
    cors_origins_raw: str = Field(
        default="http://localhost:3000,http://localhost:5500,chrome-extension://*",
        validation_alias="CORS_ORIGINS",
    )

    @property
    def cors_origins(self) -> List[str]:
        """Split the env-supplied string into a list of origins."""
        return [item.strip() for item in self.cors_origins_raw.split(",") if item.strip()]

    # ---------- Rate Limiting ----------
    rate_limit_per_minute: int = 120

    # ---------- AI Service ----------
    ai_provider: str = "http"  # "gemini" | "http" | "local"
    ai_service_url: str = "http://localhost:8001"
    ai_model_dir: str = "../ai_service/models/artifacts"
    active_model_version: str = "auto"
    distilbert_model_name: str = "distilbert-base-uncased"
    max_sequence_length: int = 256

    # ---------- Google Gemini (when AI_PROVIDER=gemini) ----------
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"

    # ---------- Logging ----------
    log_level: str = "INFO"
    log_file: str = "logs/app.log"

    # ---------- Admin Bootstrap ----------
    admin_email: str = "admin@mailguard.ai"
    admin_password: str = "ChangeMe123!"

    @property
    def sqlalchemy_url(self) -> str:
        """Return the SQLAlchemy URL."""
        if self.database_url:
            return self.database_url
        return (
            f"mysql+pymysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"
        )


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()


settings = get_settings()