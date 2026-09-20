from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.llm.base import ToolCall, ToolSpec
from app.llm.schema_utils import inline_refs
from app.models.calendar_event import CalendarEvent
from app.models.task import Task
from app.models.user import User
from app.schemas.event import EventCreate, EventSearchParams, EventUpdate
from app.schemas.task import TaskCreate, TaskSearchParams, TaskUpdate
from app.schemas.tools import (
    CompleteTaskArgs,
    CreateEventArgs,
    CreateTaskArgs,
    DeleteEventArgs,
    DeleteTaskArgs,
    GetEventArgs,
    GetTaskArgs,
    SearchEventsArgs,
    SearchTasksArgs,
    UpdateEventArgs,
    UpdateTaskArgs,
)
from app.services.event_service import EventService
from app.services.task_service import TaskService


@dataclass(frozen=True)
class PendingAction:
    """ユーザーの承認を待つ操作（要件定義書 24 の「確認を推奨／必須」）。"""

    tool: str
    arguments: dict[str, Any]
    #: 確認ダイアログに出す文言（例: タスク「ES作成」を削除します。）
    description: str
    #: 実行後にユーザーへ返す文言（例: タスク「ES作成」を削除しました。）
    done_message: str


@dataclass(frozen=True)
class ToolOutcome:
    content: Any
    is_error: bool = False
    #: データを変更したか（UI の再取得が必要かの判断に使う）
    mutated: bool = False
    pending: PendingAction | None = None


@dataclass(frozen=True)
class ToolDefinition:
    description: str
    args_model: type[BaseModel]
    handler: Callable[[BaseModel], ToolOutcome]
    #: 実行前にユーザーへ確認を求める
    needs_confirmation: bool = False


def summarize_task(task: Task) -> dict[str, Any]:
    """LLM に返す最小限の表現。

    created_at などを含めると毎回のトークンが増えるだけなので落とす。
    """
    return {
        "id": task.id,
        "title": task.title,
        "status": task.status.value,
        "priority": task.priority.value,
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "estimated_minutes": task.estimated_minutes,
    }


def summarize_event(event: CalendarEvent) -> dict[str, Any]:
    """LLM に返す最小限の表現。"""
    return {
        "id": event.id,
        "title": event.title,
        "start_at": event.start_at.isoformat(),
        "end_at": event.end_at.isoformat(),
        "location": event.location,
        "task_id": event.task_id,
    }


class ToolRegistry:
    """LLM が実行できる操作の一覧と、その実行。

    **Tool は必ず既存の Service を呼ぶ。** ここで新たにDBアクセスを書かない
    （通常UIとLLMで処理が分岐しないようにするため）。
    """

    def __init__(self, db: Session, user: User) -> None:
        self.user = user
        self.tasks = TaskService(db)
        self.events = EventService(db)
        self._definitions = self._build_definitions()

    # ------------------------------------------------------------------ 定義

    def _build_definitions(self) -> dict[str, ToolDefinition]:
        return {
            "create_task": ToolDefinition(
                description=(
                    "新しいタスクを作成する。"
                    "「〜するタスクを追加して」「〜をやることに入れて」などの依頼に使う。"
                ),
                args_model=CreateTaskArgs,
                handler=self._create_task,
            ),
            "get_task": ToolDefinition(
                description="IDを指定して1件のタスクを取得する。",
                args_model=GetTaskArgs,
                handler=self._get_task,
            ),
            "search_tasks": ToolDefinition(
                description=(
                    "条件でタスクを検索する。"
                    "「今日のタスク」「今週締切のタスク」「未完了のタスク」などの質問や、"
                    "変更・削除の対象を特定するために使う。"
                ),
                args_model=SearchTasksArgs,
                handler=self._search_tasks,
            ),
            "update_task": ToolDefinition(
                description=(
                    "既存タスクの内容を変更する。期限・優先度・タイトル・状態を変えられる。"
                    "対象のIDが不明なときは先に search_tasks で特定する。"
                ),
                args_model=UpdateTaskArgs,
                handler=self._update_task,
            ),
            "complete_task": ToolDefinition(
                description="タスクを完了にする。",
                args_model=CompleteTaskArgs,
                handler=self._complete_task,
            ),
            "delete_task": ToolDefinition(
                description="タスクを削除する。取り消せないためユーザーの確認が必要。",
                args_model=DeleteTaskArgs,
                handler=self._delete_task,
                needs_confirmation=True,
            ),
            "create_event": ToolDefinition(
                description=(
                    "カレンダーに予定を作成する。"
                    "「明日の14時から2時間〜を入れて」のような依頼に使う。"
                    "タスクの作業時間を確保する場合は task_id を指定する。"
                ),
                args_model=CreateEventArgs,
                handler=self._create_event,
            ),
            "get_event": ToolDefinition(
                description="IDを指定して1件の予定を取得する。",
                args_model=GetEventArgs,
                handler=self._get_event,
            ),
            "search_events": ToolDefinition(
                description=(
                    "期間やキーワードで予定を検索する。"
                    "「明日の予定を教えて」「今週の予定」などの質問や、"
                    "変更・削除の対象を特定するために使う。"
                    "指定期間に少しでも重なる予定が返る。"
                ),
                args_model=SearchEventsArgs,
                handler=self._search_events,
            ),
            "update_event": ToolDefinition(
                description=(
                    "既存の予定を変更する。時間の移動やタイトル変更に使う。"
                    "対象のIDが不明なときは先に search_events で特定する。"
                ),
                args_model=UpdateEventArgs,
                handler=self._update_event,
            ),
            "delete_event": ToolDefinition(
                description="予定を削除する。取り消せないためユーザーの確認が必要。",
                args_model=DeleteEventArgs,
                handler=self._delete_event,
                needs_confirmation=True,
            ),
        }

    def specs(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name=name,
                description=definition.description,
                input_schema=inline_refs(definition.args_model.model_json_schema()),
            )
            for name, definition in self._definitions.items()
        ]

    # ------------------------------------------------------------------ 実行

    def execute(self, call: ToolCall, *, confirmed: bool = False) -> ToolOutcome:
        definition = self._definitions.get(call.name)
        if definition is None:
            return ToolOutcome(
                {"error": f"'{call.name}' というツールはありません。"}, is_error=True
            )

        try:
            args = definition.args_model.model_validate(call.arguments)
        except ValidationError as exc:
            # LLM が誤った引数を出しても落とさず、内容を返して修正させる
            return ToolOutcome(
                {
                    "error": "引数が不正です。修正して呼び直してください。",
                    "details": [
                        {"field": ".".join(str(p) for p in e["loc"]), "reason": e["msg"]}
                        for e in exc.errors()
                    ],
                },
                is_error=True,
            )

        try:
            if definition.needs_confirmation and not confirmed:
                return self._request_confirmation(call.name, args)
            return definition.handler(args)
        except AppError as exc:
            return ToolOutcome({"error": exc.message}, is_error=True)

    def _request_confirmation(self, name: str, args: BaseModel) -> ToolOutcome:
        """実行せず、対象を特定したうえで確認用の情報を返す。"""
        if name == "delete_task":
            assert isinstance(args, DeleteTaskArgs)
            # 存在しないIDならここで NotFoundError になり、確認を出さずに済む
            task = self.tasks.get(self.user, args.task_id)
            description = f"タスク「{task.title}」を削除します。"
            done_message = f"タスク「{task.title}」を削除しました。"
        elif name == "delete_event":
            assert isinstance(args, DeleteEventArgs)
            event = self.events.get(self.user, args.event_id)
            when = event.start_at.strftime("%-m/%-d %H:%M")
            description = f"{when} の予定「{event.title}」を削除します。"
            done_message = f"{when} の予定「{event.title}」を削除しました。"
        else:  # pragma: no cover - 新しい確認対象を追加したら必ずここも書く
            description = f"{name} を実行します。"
            done_message = f"{name} を実行しました。"

        return ToolOutcome(
            {
                "status": "confirmation_required",
                "message": "ユーザーの承認待ちです。承認されるまで実行されません。",
            },
            pending=PendingAction(
                tool=name,
                arguments=args.model_dump(mode="json"),
                description=description,
                done_message=done_message,
            ),
        )

    # ------------------------------------------------------------ 各ツール実装

    def _create_task(self, args: BaseModel) -> ToolOutcome:
        assert isinstance(args, CreateTaskArgs)
        task = self.tasks.create(self.user, TaskCreate(**args.model_dump()))
        return ToolOutcome(summarize_task(task), mutated=True)

    def _get_task(self, args: BaseModel) -> ToolOutcome:
        assert isinstance(args, GetTaskArgs)
        return ToolOutcome(summarize_task(self.tasks.get(self.user, args.task_id)))

    def _search_tasks(self, args: BaseModel) -> ToolOutcome:
        assert isinstance(args, SearchTasksArgs)
        params = TaskSearchParams(
            statuses=args.statuses,
            priorities=args.priorities,
            keyword=args.keyword,
            due_from=args.due_from,
            due_to=args.due_to,
            limit=args.limit,
        )
        tasks = self.tasks.search(self.user, params)
        return ToolOutcome(
            {"count": len(tasks), "tasks": [summarize_task(t) for t in tasks]}
        )

    def _update_task(self, args: BaseModel) -> ToolOutcome:
        assert isinstance(args, UpdateTaskArgs)
        changes = args.model_dump(exclude={"task_id"}, exclude_unset=True)
        task = self.tasks.update(self.user, args.task_id, TaskUpdate(**changes))
        return ToolOutcome(summarize_task(task), mutated=True)

    def _complete_task(self, args: BaseModel) -> ToolOutcome:
        assert isinstance(args, CompleteTaskArgs)
        return ToolOutcome(
            summarize_task(self.tasks.complete(self.user, args.task_id)), mutated=True
        )

    def _delete_task(self, args: BaseModel) -> ToolOutcome:
        assert isinstance(args, DeleteTaskArgs)
        task = self.tasks.get(self.user, args.task_id)
        title = task.title
        self.tasks.delete(self.user, args.task_id)
        return ToolOutcome(
            {"deleted": True, "id": args.task_id, "title": title}, mutated=True
        )

    # ----------------------------------------------------- カレンダーの各ツール

    def _create_event(self, args: BaseModel) -> ToolOutcome:
        assert isinstance(args, CreateEventArgs)
        event = self.events.create(self.user, EventCreate(**args.model_dump()))
        return ToolOutcome(summarize_event(event), mutated=True)

    def _get_event(self, args: BaseModel) -> ToolOutcome:
        assert isinstance(args, GetEventArgs)
        return ToolOutcome(summarize_event(self.events.get(self.user, args.event_id)))

    def _search_events(self, args: BaseModel) -> ToolOutcome:
        assert isinstance(args, SearchEventsArgs)
        params = EventSearchParams(
            from_=args.period_start,
            to=args.period_end,
            keyword=args.keyword,
            limit=args.limit,
        )
        events = self.events.search(self.user, params)
        return ToolOutcome(
            {"count": len(events), "events": [summarize_event(e) for e in events]}
        )

    def _update_event(self, args: BaseModel) -> ToolOutcome:
        assert isinstance(args, UpdateEventArgs)
        changes = args.model_dump(exclude={"event_id"}, exclude_unset=True)
        event = self.events.update(self.user, args.event_id, EventUpdate(**changes))
        return ToolOutcome(summarize_event(event), mutated=True)

    def _delete_event(self, args: BaseModel) -> ToolOutcome:
        assert isinstance(args, DeleteEventArgs)
        event = self.events.get(self.user, args.event_id)
        title = event.title
        self.events.delete(self.user, args.event_id)
        return ToolOutcome(
            {"deleted": True, "id": args.event_id, "title": title}, mutated=True
        )
