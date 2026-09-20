from functools import lru_cache

from app.core.config import get_settings
from app.core.exceptions import LLMError
from app.llm.base import LLMProvider
from app.llm.claude import ClaudeProvider
from app.llm.ollama import OllamaProvider


@lru_cache
def get_llm_provider() -> LLMProvider:
    """設定に応じたプロバイダを返す。

    プロバイダを増やすときはここに追加する。呼び出し側は LLMProvider しか知らない。
    """
    settings = get_settings()

    match settings.llm_provider:
        case "ollama":
            return OllamaProvider(
                base_url=settings.ollama_base_url, model=settings.ollama_model
            )
        case "claude":
            return ClaudeProvider(
                api_key=settings.anthropic_api_key, model=settings.claude_model
            )
        case unknown:
            raise LLMError(
                f"未知の LLM_PROVIDER: '{unknown}'（利用可能: ollama, claude）"
            )
