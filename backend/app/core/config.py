from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """環境変数から読み込むアプリケーション設定。

    APIキー等の秘密情報はここだけで扱い、フロントエンドへは絶対に渡さない。
    """

    # 起動ディレクトリに依存せず backend/.env を読む
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    timezone: str = "Asia/Tokyo"
    database_url: str = "postgresql+psycopg://kanta@localhost:5432/ai_task_manager"
    cors_origins: str = "http://localhost:3000"

    # LLM (Phase 5 以降)
    llm_provider: str = "claude"
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-5"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
