"""プロバイダごとのメッセージ形式変換のテスト。

実際のLLMは呼ばない。ここがズレると Tool Calling が黙って壊れるため、
変換だけを切り出して検証する。
"""

from app.llm.base import ChatMessage, ToolCall
from app.llm.claude import to_claude_messages
from app.llm.ollama import parse_tool_calls, to_ollama_messages
from app.llm.schema_utils import inline_refs


def test_claude_converts_plain_conversation() -> None:
    messages = [
        ChatMessage(role="user", content="こんにちは"),
        ChatMessage(role="assistant", content="はい"),
    ]
    assert to_claude_messages(messages) == [
        {"role": "user", "content": "こんにちは"},
        {"role": "assistant", "content": "はい"},
    ]


def test_claude_converts_tool_use_blocks() -> None:
    messages = [
        ChatMessage(
            role="assistant",
            content="調べます",
            tool_calls=(ToolCall(id="c1", name="search_tasks", arguments={"keyword": "ES"}),),
        ),
    ]
    blocks = to_claude_messages(messages)[0]["content"]

    assert blocks[0] == {"type": "text", "text": "調べます"}
    assert blocks[1] == {
        "type": "tool_use",
        "id": "c1",
        "name": "search_tasks",
        "input": {"keyword": "ES"},
    }


def test_claude_merges_consecutive_tool_results_into_one_message() -> None:
    """並列Tool呼び出しの結果は1つの user メッセージにまとめる必要がある。"""
    messages = [
        ChatMessage(
            role="assistant",
            tool_calls=(
                ToolCall(id="c1", name="create_task", arguments={}),
                ToolCall(id="c2", name="create_task", arguments={}),
            ),
        ),
        ChatMessage(role="tool", content="{}", tool_call_id="c1", tool_name="create_task"),
        ChatMessage(role="tool", content="{}", tool_call_id="c2", tool_name="create_task"),
    ]

    converted = to_claude_messages(messages)

    assert len(converted) == 2
    assert converted[1]["role"] == "user"
    assert [b["tool_use_id"] for b in converted[1]["content"]] == ["c1", "c2"]


def test_claude_marks_tool_errors() -> None:
    messages = [
        ChatMessage(
            role="tool",
            content='{"error": "だめ"}',
            tool_call_id="c1",
            tool_name="create_task",
            is_error=True,
        )
    ]
    assert to_claude_messages(messages)[0]["content"][0]["is_error"] is True


def test_ollama_converts_tool_messages() -> None:
    messages = [
        ChatMessage(
            role="assistant",
            content="",
            tool_calls=(ToolCall(id="c1", name="create_task", arguments={"title": "A"}),),
        ),
        ChatMessage(role="tool", content="{}", tool_call_id="c1", tool_name="create_task"),
    ]

    converted = to_ollama_messages(messages)

    assert converted[0]["tool_calls"] == [
        {"function": {"name": "create_task", "arguments": {"title": "A"}}}
    ]
    assert converted[1]["role"] == "tool"
    assert converted[1]["tool_name"] == "create_task"


def test_ollama_parses_tool_calls_with_dict_arguments() -> None:
    calls = parse_tool_calls(
        [{"function": {"name": "create_task", "arguments": {"title": "A"}}}]
    )
    assert calls[0].name == "create_task"
    assert calls[0].arguments == {"title": "A"}
    assert calls[0].id == "call_0"


def test_ollama_parses_tool_calls_with_string_arguments() -> None:
    """引数を JSON 文字列で返す実装もあるため、その場合も解釈する。"""
    calls = parse_tool_calls(
        [{"function": {"name": "create_task", "arguments": '{"title": "A"}'}}]
    )
    assert calls[0].arguments == {"title": "A"}


def test_ollama_tolerates_broken_arguments() -> None:
    calls = parse_tool_calls([{"function": {"name": "create_task", "arguments": "{壊れ"}}])
    assert calls[0].arguments == {}


def test_inline_refs_expands_definitions() -> None:
    schema = {
        "$defs": {"Color": {"enum": ["red", "blue"], "type": "string", "title": "Color"}},
        "properties": {"color": {"$ref": "#/$defs/Color", "description": "色"}},
        "type": "object",
        "title": "Args",
    }

    resolved = inline_refs(schema)

    assert resolved == {
        "properties": {
            "color": {"enum": ["red", "blue"], "type": "string", "description": "色"}
        },
        "type": "object",
    }


def test_inline_refs_keeps_a_property_named_title() -> None:
    """"title" は JSON Schema の注釈でもあるが、プロパティ名なら残す。

    ここを落とすと LLM から create_task の title 引数が見えなくなる。
    """
    schema = {
        "title": "CreateTaskArgs",
        "type": "object",
        "properties": {
            "title": {"type": "string", "title": "Title", "description": "タイトル"},
            "priority": {"type": "string"},
        },
        "required": ["title"],
    }

    resolved = inline_refs(schema)

    assert set(resolved["properties"]) == {"title", "priority"}
    # プロパティの中身にある注釈としての title は落とす
    assert resolved["properties"]["title"] == {
        "type": "string",
        "description": "タイトル",
    }
    assert "title" not in resolved  # スキーマ自体の注釈は落とす


def test_simplify_nullable_removes_null_variant() -> None:
    """任意項目の anyOf と default:null を削り、入力トークンを減らす。"""
    from app.llm.schema_utils import simplify_nullable

    schema = {
        "type": "object",
        "properties": {
            "description": {
                "anyOf": [{"type": "string"}, {"type": "null"}],
                "default": None,
                "description": "補足",
            },
            "limit": {"type": "integer", "default": 20},
        },
        "required": [],
    }

    simplified = simplify_nullable(schema)

    assert simplified["properties"]["description"] == {
        "type": "string",
        "description": "補足",
    }
    # null 以外の既定値は LLM に有用なので残す
    assert simplified["properties"]["limit"] == {"type": "integer", "default": 20}


def test_simplify_nullable_keeps_property_named_anyof_safe() -> None:
    """複数の型が本当に許される場合は anyOf を残す。"""
    from app.llm.schema_utils import simplify_nullable

    schema = {
        "properties": {
            "value": {"anyOf": [{"type": "string"}, {"type": "integer"}]},
        }
    }
    assert "anyOf" in simplify_nullable(schema)["properties"]["value"]


def test_ollama_requests_are_deterministic() -> None:
    """Tool 選択を安定させるため temperature=0 で送ること。"""
    import httpx

    from app.llm.ollama import OllamaProvider

    provider = OllamaProvider(base_url="http://127.0.0.1:1", model="qwen3:1.7b")
    captured: dict = {}

    def fake_post(url, json, timeout):  # noqa: ANN001, A002
        captured.update(json)
        return httpx.Response(200, json={"message": {"content": "ok"}})

    original = httpx.post
    httpx.post = fake_post  # type: ignore[assignment]
    try:
        provider.chat([ChatMessage(role="user", content="hi")], system="s")
    finally:
        httpx.post = original  # type: ignore[assignment]

    assert captured["options"]["temperature"] == 0
    assert captured["options"]["num_ctx"] == 6144
    assert captured["think"] is False


def test_recovers_tool_call_written_as_text() -> None:
    """小型モデルが本文に書いてしまった Tool 呼び出しを拾う。"""
    from app.llm.ollama import recover_tool_call_from_text

    call = recover_tool_call_from_text(
        '{"name": "search_tasks", "arguments": {"statuses": ["todo"]}}'
    )
    assert call is not None
    assert call.name == "search_tasks"
    assert call.arguments == {"statuses": ["todo"]}


def test_recovers_tool_call_inside_code_fence() -> None:
    from app.llm.ollama import recover_tool_call_from_text

    call = recover_tool_call_from_text(
        '```json\n{"name": "create_task", "arguments": {"title": "ES"}}\n```'
    )
    assert call is not None
    assert call.arguments == {"title": "ES"}


def test_does_not_recover_from_normal_text() -> None:
    from app.llm.ollama import recover_tool_call_from_text

    assert recover_tool_call_from_text("こんにちは。お手伝いします。") is None
    assert recover_tool_call_from_text('{"foo": 1}') is None
    assert recover_tool_call_from_text("") is None
    assert recover_tool_call_from_text('{"name": "x", "arguments": "壊れ"}') is None
