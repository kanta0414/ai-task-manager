from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.core.exceptions import AppError, NotFoundError
from app.llm.base import ToolCall, ToolSpec
from app.llm.schema_utils import inline_refs, simplify_nullable
from app.models.calendar_event import CalendarEvent
from app.models.task import Task
from app.models.user import User
from app.schemas.event import EventCreate, EventSearchParams, EventUpdate
from app.schemas.task import TaskCreate, TaskSearchParams, TaskUpdate
from app.schemas.tools import (
    ApplyRescheduleArgs,
    ApplyScheduleArgs,
    CompleteTaskArgs,
    CreateSubtasksArgs,
    FindFreeTimeArgs,
    GenerateScheduleArgs,
    RescheduleArgs,
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
from app.services.schedule_service import (
    ReschedulePlan,
    SchedulePlan,
    ScheduleConstraints,
    ScheduleService,
    default_constraints,
)
from app.services.task_service import TaskService

#: LLM に返す空き時間候補の最大件数
MAX_FREE_SLOTS = 10


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
    #: 承認後にユーザーへ返す文言（件数など実行結果に依存する場合に使う）
    message: str | None = None
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
    #: LLM に提示するか（承認後の実行専用ツールは提示しない）
    exposed: bool = True


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
        "parent_task_id": task.parent_task_id,
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
        self.schedule = ScheduleService(db)
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
                    "task_id は、既存タスクの作業時間として確保する場合にだけ指定する。"
                    "指定するidが分からなければ省略する。"
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
            "find_free_time": ToolDefinition(
                description=(
                    "空き時間を「調べるだけ」のツール。"
                    "「2時間空いている時間を探して」「いつが空いてる？」に使う。"
                    "タスクを配置するところまで求められている場合は"
                    "generate_schedule を使うこと。"
                    "いつ空いているかを推測せず、必ずこのツールの結果を使うこと。"
                ),
                args_model=FindFreeTimeArgs,
                handler=self._find_free_time,
            ),
            "create_subtasks": ToolDefinition(
                description=(
                    "大きなタスクを小さなタスクに分解して登録する。"
                    "「〜を分解して」「何から始めればいい？」"
                    "「〜までに完成させたい、必要な作業に分けて」といった依頼に使う。"
                    "分解した内容は自分で考えて subtasks に渡す。"
                    "登録前にユーザーの承認が必要。"
                ),
                args_model=CreateSubtasksArgs,
                handler=self._create_subtasks,
                needs_confirmation=True,
            ),
            "generate_schedule": ToolDefinition(
                description=(
                    "未完了タスクを空き時間へ「配置する」ツール。"
                    "「空いている時間にタスクを入れて」「スケジュールを組んで」"
                    "「今週中に終わらせたい」のように、"
                    "調べるだけでなく予定を作ってほしい依頼はすべてこれを使う。"
                    "空き時間の計算もこのツールが内部で行うので、"
                    "先に find_free_time を呼ぶ必要はない。"
                    "登録前にユーザーの承認が求められる。"
                ),
                args_model=GenerateScheduleArgs,
                handler=self._unreachable,
                needs_confirmation=True,
            ),
            "reschedule_unfinished": ToolDefinition(
                description=(
                    "終わらなかった作業を、これからの空き時間へ組み直す。"
                    "「今日終わらなかったタスクを明日以降に回して」"
                    "「やり残しを再配置して」といった依頼に使う。"
                    "対象は、時間が過ぎたのに完了していないタスクの予定。"
                    "変更前にユーザーの承認が必要。"
                ),
                args_model=RescheduleArgs,
                handler=self._unreachable,
                needs_confirmation=True,
            ),
            "apply_reschedule": ToolDefinition(
                description="承認された組み直しを反映する。",
                args_model=ApplyRescheduleArgs,
                handler=self._apply_reschedule,
                needs_confirmation=True,
                exposed=False,
            ),
            "apply_schedule": ToolDefinition(
                description="承認されたスケジュールを予定として登録する。",
                args_model=ApplyScheduleArgs,
                handler=self._apply_schedule,
                needs_confirmation=True,
                exposed=False,
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
                input_schema=simplify_nullable(
                    inline_refs(definition.args_model.model_json_schema())
                ),
            )
            for name, definition in self._definitions.items()
            if definition.exposed
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
        except NotFoundError as exc:
            # LLM は id を推測しがちなので、立て直し方まで書いて返す
            search_tool = "search_events" if "event" in call.name else "search_tasks"
            return ToolOutcome(
                {
                    "error": exc.message,
                    "next_step": (
                        f"id を推測してはいけません。{search_tool} で対象を検索し、"
                        "返ってきた id を使って呼び直してください。"
                    ),
                },
                is_error=True,
            )
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
        elif name == "create_subtasks":
            assert isinstance(args, CreateSubtasksArgs)
            return self._propose_subtasks(args)
        elif name == "reschedule_unfinished":
            assert isinstance(args, RescheduleArgs)
            return self._propose_reschedule(args)
        elif name == "generate_schedule":
            assert isinstance(args, GenerateScheduleArgs)
            return self._propose_schedule(args)
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

    # ------------------------------------------------------- スケジュールの Tool

    def _find_free_time(self, args: BaseModel) -> ToolOutcome:
        assert isinstance(args, FindFreeTimeArgs)
        defaults = default_constraints()
        constraints = ScheduleConstraints(
            day_start_hour=defaults.day_start_hour,
            day_end_hour=defaults.day_end_hour,
            exclude_weekends=args.exclude_weekends,
        )
        slots = self.schedule.find_free_time(
            self.user,
            period_start=args.period_start,
            period_end=args.period_end,
            minutes_needed=args.minutes_needed,
            constraints=constraints,
        )
        # 候補が多すぎると応答トークンが膨らむので先頭だけ返す
        shown = slots[:MAX_FREE_SLOTS]
        return ToolOutcome(
            {
                "rule": constraints.describe(),
                "count": len(slots),
                "slots": [
                    {
                        "start_at": slot.start_at.isoformat(),
                        "end_at": slot.end_at.isoformat(),
                        "minutes": slot.minutes,
                    }
                    for slot in shown
                ],
            }
        )

    # --------------------------------------------------- 自動スケジューリング

    def _propose_schedule(self, args: GenerateScheduleArgs) -> ToolOutcome:
        """配置案を作って承認を求める。**この時点では登録しない。**"""
        defaults = default_constraints()
        plan = self.schedule.generate_schedule(
            self.user,
            period_start=args.period_start,
            period_end=args.period_end,
            task_ids=args.task_ids,
            constraints=ScheduleConstraints(
                day_start_hour=defaults.day_start_hour,
                day_end_hour=defaults.day_end_hour,
                exclude_weekends=args.exclude_weekends,
            ),
        )

        if not plan.items:
            # 置けるものが無いときは承認を求めず、理由をそのまま伝える
            return ToolOutcome(
                {
                    "scheduled": 0,
                    "rule": plan.rule,
                    "skipped": [
                        {"task_id": s.task_id, "title": s.title, "reason": s.reason}
                        for s in plan.skipped
                    ],
                }
            )

        return ToolOutcome(
            {
                "status": "confirmation_required",
                "message": "ユーザーの承認待ちです。承認されるまで登録されません。",
                "rule": plan.rule,
                "planned": [
                    {
                        "task_id": item.task_id,
                        "title": item.title,
                        "start_at": item.start_at.isoformat(),
                        "end_at": item.end_at.isoformat(),
                    }
                    for item in plan.items
                ],
                "skipped": [
                    {"title": s.title, "reason": s.reason} for s in plan.skipped
                ],
            },
            pending=PendingAction(
                tool="apply_schedule",
                arguments={
                    "items": [
                        {
                            "task_id": item.task_id,
                            "start_at": item.start_at.isoformat(),
                            "end_at": item.end_at.isoformat(),
                        }
                        for item in plan.items
                    ]
                },
                description=format_plan(plan),
                done_message=f"{len(plan.items)}件の予定を登録しました。",
            ),
        )

    def _apply_schedule(self, args: BaseModel) -> ToolOutcome:
        assert isinstance(args, ApplyScheduleArgs)
        created = []
        for item in args.items:
            # タスクの所有者確認はここで行われる（他人のタスクは登録できない）
            task = self.tasks.get(self.user, item.task_id)
            event = self.events.create(
                self.user,
                EventCreate(
                    title=task.title,
                    start_at=item.start_at,
                    end_at=item.end_at,
                    task_id=task.id,
                ),
            )
            created.append({"event_id": event.id, "title": event.title})

        return ToolOutcome(
            {"created": len(created), "events": created},
            mutated=True,
            message=f"{len(created)}件の予定を登録しました。",
        )

    def _unreachable(self, args: BaseModel) -> ToolOutcome:  # pragma: no cover
        """承認フローを必ず通すツール用。直接は呼ばれない。"""
        raise AssertionError("このツールは確認フローを経由して実行される")


    # ------------------------------------------------------------- タスク分解

    def _propose_subtasks(self, args: CreateSubtasksArgs) -> ToolOutcome:
        """分解案を見せて承認を求める。**この時点では登録しない。**"""
        # 存在と所有者をここで確認する（承認を出す前に弾く）
        parent = self.tasks.get(self.user, args.parent_task_id)

        lines = [f"「{parent.title}」を次の{len(args.subtasks)}個に分解して登録します。", ""]
        lines.extend(
            f"  {index}. {subtask.title}"
            + (f"（{subtask.estimated_minutes}分）" if subtask.estimated_minutes else "")
            for index, subtask in enumerate(args.subtasks, start=1)
        )

        return ToolOutcome(
            {
                "status": "confirmation_required",
                "message": "ユーザーの承認待ちです。承認されるまで登録されません。",
                "parent": {"id": parent.id, "title": parent.title},
                "subtasks": [subtask.title for subtask in args.subtasks],
            },
            pending=PendingAction(
                tool="create_subtasks",
                arguments=args.model_dump(mode="json"),
                description="\n".join(lines),
                done_message=f"{len(args.subtasks)}個のタスクを登録しました。",
            ),
        )

    def _create_subtasks(self, args: BaseModel) -> ToolOutcome:
        assert isinstance(args, CreateSubtasksArgs)
        parent = self.tasks.get(self.user, args.parent_task_id)

        created = []
        for subtask in args.subtasks:
            task = self.tasks.create(
                self.user,
                TaskCreate(
                    title=subtask.title,
                    estimated_minutes=subtask.estimated_minutes,
                    # 期限の指定がなければ親の期限を引き継ぐ
                    due_date=subtask.due_date or parent.due_date,
                    priority=parent.priority,
                    parent_task_id=parent.id,
                ),
            )
            created.append(summarize_task(task))

        return ToolOutcome(
            {"parent_id": parent.id, "created": len(created), "tasks": created},
            mutated=True,
            message=f"{len(created)}個のタスクを登録しました。",
        )


    # --------------------------------------------------------- 未完了の再配置

    def _propose_reschedule(self, args: RescheduleArgs) -> ToolOutcome:
        """終わらなかった作業の組み直し案を作り、承認を求める。"""
        defaults = default_constraints()
        plan = self.schedule.reschedule_unfinished(
            self.user,
            now=datetime.now(UTC),
            period_start=args.period_start,
            period_end=args.period_end,
            constraints=ScheduleConstraints(
                day_start_hour=defaults.day_start_hour,
                day_end_hour=defaults.day_end_hour,
                exclude_weekends=args.exclude_weekends,
            ),
        )

        if not plan.items:
            return ToolOutcome(
                {
                    "rescheduled": 0,
                    "message": (
                        "組み直す対象がありません。"
                        "時間が過ぎた予定はすべて完了扱いになっています。"
                        if not plan.skipped
                        else "対象はありますが、空き時間に収まりませんでした。"
                    ),
                    "skipped": [
                        {"title": s.title, "reason": s.reason} for s in plan.skipped
                    ],
                }
            )

        return ToolOutcome(
            {
                "status": "confirmation_required",
                "message": "ユーザーの承認待ちです。承認されるまで変更されません。",
                "planned": [
                    {
                        "title": item.title,
                        "from": item.previous_start_at.isoformat(),
                        "to": item.start_at.isoformat(),
                    }
                    for item in plan.items
                ],
            },
            pending=PendingAction(
                tool="apply_reschedule",
                arguments={
                    "items": [
                        {
                            "task_id": item.task_id,
                            "previous_event_id": item.previous_event_id,
                            "start_at": item.start_at.isoformat(),
                            "end_at": item.end_at.isoformat(),
                        }
                        for item in plan.items
                    ]
                },
                description=format_reschedule(plan),
                done_message=f"{len(plan.items)}件の予定を組み直しました。",
            ),
        )

    def _apply_reschedule(self, args: BaseModel) -> ToolOutcome:
        assert isinstance(args, ApplyRescheduleArgs)
        moved = []
        for item in args.items:
            task = self.tasks.get(self.user, item.task_id)
            # 所有者確認を兼ねて取得してから消す
            self.events.get(self.user, item.previous_event_id)
            self.events.delete(self.user, item.previous_event_id)

            event = self.events.create(
                self.user,
                EventCreate(
                    title=task.title,
                    start_at=item.start_at,
                    end_at=item.end_at,
                    task_id=task.id,
                ),
            )
            moved.append({"event_id": event.id, "title": event.title})

        return ToolOutcome(
            {"moved": len(moved), "events": moved},
            mutated=True,
            message=f"{len(moved)}件の予定を組み直しました。",
        )



WEEKDAYS_JA = ["月", "火", "水", "木", "金", "土", "日"]


def format_plan(plan: SchedulePlan) -> str:
    """確認ダイアログに出す文面（要件定義書 19 の形式）。"""
    lines = ["以下の予定を登録します。", ""]

    current_day = None
    for item in plan.items:
        day = item.start_at.date()
        if day != current_day:
            current_day = day
            lines.append(f"{day.month}/{day.day}({WEEKDAYS_JA[day.weekday()]})")
        lines.append(
            f"  {item.start_at:%H:%M}〜{item.end_at:%H:%M} {item.title}"
        )

    if plan.skipped:
        lines.append("")
        lines.append("配置できなかったタスク:")
        lines.extend(f"  {s.title}（{s.reason}）" for s in plan.skipped)

    lines.append("")
    lines.append(f"条件: {plan.rule}")
    return "\n".join(lines)


def format_reschedule(plan: ReschedulePlan) -> str:
    """組み直しの確認文面。どこからどこへ動かすかを示す。"""
    lines = ["以下の予定を組み直します。", ""]
    for item in plan.items:
        before = item.previous_start_at
        after = item.start_at
        lines.append(
            f"  {item.title}: "
            f"{before.month}/{before.day} {before:%H:%M} → "
            f"{after.month}/{after.day}({WEEKDAYS_JA[after.weekday()]}) "
            f"{after:%H:%M}〜{item.end_at:%H:%M}"
        )

    if plan.skipped:
        lines.append("")
        lines.append("組み直せなかったもの:")
        lines.extend(f"  {s.title}（{s.reason}）" for s in plan.skipped)

    lines.append("")
    lines.append(f"条件: {plan.rule}")
    return "\n".join(lines)
