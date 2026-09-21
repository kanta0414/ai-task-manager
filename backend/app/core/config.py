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

    # 非同期処理（Celery）
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = ""
    # filesystem ブローカーを使う場合の置き場所（Redis が無い環境向け）
    celery_broker_folder: str = ".celery-broker"

    # 自動スケジューリングの制約。LLM ではなく Backend が持つルール
    schedule_day_start_hour: int = 9
    schedule_day_end_hour: int = 22

    # 認証導入前の既定ユーザー（Phase 16 で置き換える）
    default_user_email: str = "owner@example.com"
    default_user_name: str = "Owner"

    # LLM。既定はローカルの Ollama（API料金が発生しない）
    llm_provider: str = "ollama"
    anthropic_api_key: str = ""
    claude_model: str = "claude-opus-5"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:1.7b"
    # Tool 定義と履歴が入る余裕を持たせる（既定の 4096 だと溢れる）
    ollama_num_ctx: int = 6144

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
