"""LLM が正しい Tool を選べるかの評価（開発手順 Phase 18）。

**これは単体テストではなく評価**。実際の LLM を呼ぶため結果は揺れるし遅い。
既定の `pytest` では実行されない。動かすときは次のようにする。

    ./.venv/bin/python -m pytest -m llm -v

`LLM_PROVIDER` の設定がそのまま使われる（ollama / claude）。
失敗しても実装の不具合とは限らず、モデルの能力の問題であることが多い。
その切り分けのために、選ばれた Tool 名を出力する。
"""

import pytest
from sqlalchemy.orm import Session

from app.llm.base import ChatMessage
from app.llm.factory import get_llm_provider
from app.models.user import User
from app.services.chat_service import build_current_time_note, build_system_prompt
from app.services.tool_registry import ToolRegistry

pytestmark = pytest.mark.llm

#: 入力と、期待する Tool（開発手順 Phase 18 の表を元にしている）
CASES = [
    ("SPIの勉強というタスクを追加して", "create_task"),
    ("今日のタスクを教えて", "search_tasks"),
    ("未完了のタスクを教えて", "search_tasks"),
    ("明日の予定を教えて", "search_events"),
    ("明日の14時から2時間、企業研究の予定を入れて", "create_event"),
    ("明日2時間空いている時間を探して", "find_free_time"),
    ("ESを完成させるを必要な作業に分解して", "create_subtasks"),
]


@pytest.fixture(scope="module")
def provider():
    llm = get_llm_provider()
    if not llm.is_available():
        pytest.skip(f"LLM({llm.name}/{llm.model}) に接続できないため評価をとばす")
    return llm


def first_tool_called(provider, registry: ToolRegistry, user: User, message: str) -> str:
    """1回目の応答で選ばれた Tool 名。呼ばなければ空文字。"""
    result = provider.chat(
        [ChatMessage(role="user", content=f"{build_current_time_note(user)}\n{message}")],
        system=build_system_prompt(user),
        tools=registry.specs(),
    )
    return result.tool_calls[0].name if result.tool_calls else ""


#: 現状のモデルでは安定しない指示。実装ではなくモデルの能力の問題。
#: 将来より大きなモデルに変えたときに成功すれば XPASS で気づける。
HARD_CASES = [
    # 「調べる」と「配置する」の区別がつかず find_free_time を選んでしまう
    ("空いている時間にタスクを配置して", "generate_schedule"),
    # 対象を検索してから消すべきところ、IDを推測して delete_task を呼んでしまう
    ("ESのタスクを削除して", "search_tasks"),
]


@pytest.mark.parametrize(("message", "expected"), CASES, ids=[c[0] for c in CASES])
def test_selects_expected_tool(
    provider, db: Session, user: User, message: str, expected: str
) -> None:
    registry = ToolRegistry(db, user)

    chosen = first_tool_called(provider, registry, user, message)

    assert chosen == expected, (
        f"「{message}」で {expected} を期待したが "
        f"{chosen or '（ツールを呼ばなかった）'} が選ばれた"
    )


@pytest.mark.xfail(
    reason="小型モデルでは安定しない。より大きなモデルなら通る想定",
    strict=False,
)
@pytest.mark.parametrize(
    ("message", "expected"), HARD_CASES, ids=[c[0] for c in HARD_CASES]
)
def test_selects_expected_tool_for_hard_cases(
    provider, db: Session, user: User, message: str, expected: str
) -> None:
    registry = ToolRegistry(db, user)

    chosen = first_tool_called(provider, registry, user, message)

    assert chosen == expected, (
        f"「{message}」で {expected} を期待したが "
        f"{chosen or '（ツールを呼ばなかった）'} が選ばれた"
    )
