import anthropic

from app.core.exceptions import LLMError, LLMUnavailableError
from app.llm.base import ChatMessage, ChatResult, LLMProvider

MAX_TOKENS = 16000


class ClaudeProvider(LLMProvider):
    """Claude API を利用するプロバイダ。

    **注意: 呼び出すと従量課金が発生する。**
    LLM_PROVIDER=claude に切り替えたときだけ使われる（既定は ollama）。
    """

    name = "claude"

    def __init__(self, api_key: str, model: str) -> None:
        self.model = model
        self._api_key = api_key
        # APIキーが無い状態でクライアントを作ると生成時に失敗するため遅延生成する
        self._client: anthropic.Anthropic | None = None

    @property
    def client(self) -> anthropic.Anthropic:
        if not self._api_key:
            raise LLMUnavailableError(
                "ANTHROPIC_API_KEY が設定されていません。backend/.env に設定してください。"
            )
        if self._client is None:
            self._client = anthropic.Anthropic(api_key=self._api_key)
        return self._client

    def chat(self, messages: list[ChatMessage], system: str) -> ChatResult:
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=MAX_TOKENS,
                system=system,
                messages=[{"role": m.role, "content": m.content} for m in messages],
            )
        except anthropic.AuthenticationError as exc:
            raise LLMUnavailableError("Claude API の認証に失敗しました（APIキーを確認してください）。") from exc
        except anthropic.NotFoundError as exc:
            raise LLMError(f"モデル '{self.model}' が利用できません。") from exc
        except anthropic.RateLimitError as exc:
            raise LLMError("Claude API のレート制限に達しました。時間をおいて再試行してください。") from exc
        except anthropic.APIStatusError as exc:
            raise LLMError(f"Claude API がエラーを返しました（{exc.status_code}）。") from exc
        except anthropic.APIConnectionError as exc:
            raise LLMUnavailableError("Claude API に接続できません。") from exc

        text = "".join(
            block.text for block in response.content if block.type == "text"
        )
        return ChatResult(content=text, provider=self.name, model=self.model)

    def is_available(self) -> bool:
        """APIキーの有無だけを見る（確認のためにAPIを呼ぶと課金されるため）。"""
        return bool(self._api_key)
