from app.llm.base import ChatMessage, ChatResult, LLMProvider, ToolSpec


class FakeProvider(LLMProvider):
    """実際のLLMを呼ばずにサービス・APIを検証するための差し替え。

    script に ChatResult を順番に積んでおくと、呼ばれるたびに1つずつ返す。
    """

    name = "fake"
    model = "fake-model"

    def __init__(
        self,
        script: list[ChatResult] | None = None,
        *,
        available: bool = True,
        error: Exception | None = None,
    ) -> None:
        self.script = list(script or [])
        self.available = available
        self.error = error
        self.calls: list[list[ChatMessage]] = []
        self.received_system = ""
        self.received_tools: list[ToolSpec] = []

    def chat(
        self,
        messages: list[ChatMessage],
        system: str,
        tools: list[ToolSpec] | None = None,
    ) -> ChatResult:
        if self.error:
            raise self.error

        self.calls.append(list(messages))
        self.received_system = system
        self.received_tools = list(tools or [])

        if self.script:
            return self.script.pop(0)
        return ChatResult(content="こんにちは", provider=self.name, model=self.model)

    def is_available(self) -> bool:
        return self.available
