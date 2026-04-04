from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "postgresql+asyncpg://localhost/signal_hub"
    debug: bool = False

    # Feature flags for experimental integrations
    enable_imessage: bool = False


settings = Settings()
