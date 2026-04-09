from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # ── database ──────────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://localhost/signal_hub"
    debug: bool = False

    # ── token storage ─────────────────────────────────────────────────────────
    # Directory for OAuth token files (.tokens/ is gitignored).
    # Relative paths are resolved from wherever uvicorn is started (apps/api/).
    token_dir: str = ".tokens"

    # ── Gmail / Google OAuth ──────────────────────────────────────────────────
    gmail_client_id: str = ""
    gmail_client_secret: str = ""
    gmail_redirect_uri: str = "http://localhost:8000/api/gmail/callback"

    # ── Notion ────────────────────────────────────────────────────────────────
    notion_token: str = ""
    notion_todo_database_id: str = ""

    # ── feature flags ─────────────────────────────────────────────────────────
    enable_imessage: bool = False


settings = Settings()
