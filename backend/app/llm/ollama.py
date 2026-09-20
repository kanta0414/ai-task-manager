import httpx

from app.core.exceptions import LLMError, LLMUnavailableError
from app.llm.base import ChatMessage, ChatResult, LLMProvider

# ローカルLLMは生成が遅いことがあるため長めに取る
REQUEST_TIMEOUT_SECONDS = 180.0


class OllamaProvider(LLMProvider):
    """ローカルの Ollama を利用するプロバイダ。

    API 料金がかからず、データを外部へ送らない構成（要件定義書 30）。
    Ollama には公式のHTTP APIがあるため httpx で直接呼び出す。
    """

    name = "ollama"

    def __init__(self, base_url: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model

    def chat(self, messages: list[ChatMessage], system: str) -> ChatResult:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                *({"role": m.role, "content": m.content} for m in messages),
            ],
            "stream": False,
        }

        try:
            response = httpx.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except httpx.ConnectError as exc:
            raise LLMUnavailableError(
                "Ollama に接続できません。`ollama serve` が起動しているか確認してください。"
            ) from exc
        except httpx.TimeoutException as exc:
            raise LLMError("Ollama の応答がタイムアウトしました。") from exc

        if response.status_code == 404:
            raise LLMUnavailableError(
                f"モデル '{self.model}' が見つかりません。"
                f"`ollama pull {self.model}` で取得してください。"
            )
        if response.status_code >= 400:
            raise LLMError(f"Ollama がエラーを返しました: {response.text[:200]}")

        content = response.json().get("message", {}).get("content", "")
        return ChatResult(content=content, provider=self.name, model=self.model)

    def is_available(self) -> bool:
        try:
            response = httpx.get(f"{self.base_url}/api/tags", timeout=3.0)
        except httpx.HTTPError:
            return False
        if response.status_code != 200:
            return False
        # モデル名は "qwen3:8b" のようにタグ付き。タグ省略指定にも対応する
        installed = {m["name"] for m in response.json().get("models", [])}
        return self.model in installed or any(
            name.split(":")[0] == self.model.split(":")[0] for name in installed
        )
