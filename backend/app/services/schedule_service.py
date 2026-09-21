from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import BusinessRuleError
from app.models.enums import TaskPriority, TaskStatus
from app.models.task import Task
from app.models.user import User
from app.repositories.event_repository import EventRepository
from app.repositories.task_repository import TaskRepository
from app.schemas.event import EventSearchParams
from app.schemas.task import TaskSearchParams

#: 一度に走査できる期間の上限（取得件数と応答サイズを抑えるため）
MAX_PERIOD_DAYS = 31
#: 1日に自動配置する作業時間の上限（開発手順15「1日6時間以上は入れない」）
DEFAULT_MAX_MINUTES_PER_DAY = 360
#: 優先度の高い順に並べるための重み
_PRIORITY_ORDER = {
    TaskPriority.HIGH: 0,
    TaskPriority.MEDIUM: 1,
    TaskPriority.LOW: 2,
}


@dataclass(frozen=True)
class FreeSlot:
    start_at: datetime
    end_at: datetime

    @property
    def minutes(self) -> int:
        return int((self.end_at - self.start_at).total_seconds() // 60)


@dataclass(frozen=True)
class ScheduleConstraints:
    """予定を入れてよい時間帯のルール。

    **LLM に決めさせず Backend が持つ**（開発手順 15）。
    「23時〜7時は入れない」「土日は入れない」といった制約をここで表現する。
    """

    day_start_hour: int = 9
    day_end_hour: int = 22
    exclude_weekends: bool = False

    def describe(self) -> str:
        rule = f"{self.day_start_hour}:00〜{self.day_end_hour}:00 の範囲で探索"
        if self.exclude_weekends:
            rule += "（土日を除く）"
        return rule


@dataclass(frozen=True)
class ScheduledItem:
    """自動配置されたタスクの作業時間。"""

    task_id: int
    title: str
    start_at: datetime
    end_at: datetime

    @property
    def minutes(self) -> int:
        return int((self.end_at - self.start_at).total_seconds() // 60)


@dataclass(frozen=True)
class SkippedTask:
    """配置できなかったタスクと、その理由。"""

    task_id: int
    title: str
    reason: str


@dataclass(frozen=True)
class SchedulePlan:
    """スケジュール案。**この時点では登録しない**（要件定義書 19）。"""

    items: list[ScheduledItem]
    skipped: list[SkippedTask]
    rule: str


@dataclass(frozen=True)
class RescheduledItem:
    """終わらなかった作業時間を、先の空き時間へ移す案。"""

    task_id: int
    title: str
    previous_event_id: int
    previous_start_at: datetime
    start_at: datetime
    end_at: datetime

    @property
    def minutes(self) -> int:
        return int((self.end_at - self.start_at).total_seconds() // 60)


@dataclass(frozen=True)
class ReschedulePlan:
    items: list[RescheduledItem]
    skipped: list[SkippedTask]
    rule: str


def sort_key_for_scheduling(task: Task) -> tuple:
    """配置する順番。

    開発手順15 のとおり「期限が近い → 優先度が高い → 所要時間が長い」。
    期限なしのタスクは期限ありより後に回す。
    """
    return (
        task.due_date is None,
        task.due_date or datetime.max.replace(tzinfo=timezone.utc),
        _PRIORITY_ORDER[task.priority],
        -(task.estimated_minutes or 0),
    )


def _describe_plan_rule(rules: ScheduleConstraints, max_minutes_per_day: int) -> str:
    return f"{rules.describe()} / 1日あたり最大{max_minutes_per_day // 60}時間"


class ScheduleService:
    """カレンダーの空き時間を計算する。

    LLM は「いつ空いているか」を推測せず、このサービスの結果を使う。
    """

    def __init__(self, db: Session) -> None:
        self.events = EventRepository(db)
        self.tasks = TaskRepository(db)

    def find_free_time(
        self,
        user: User,
        *,
        period_start: datetime,
        period_end: datetime,
        minutes_needed: int,
        constraints: ScheduleConstraints | None = None,
    ) -> list[FreeSlot]:
        if period_end <= period_start:
            raise BusinessRuleError("終了日時は開始日時より後にしてください")
        if (period_end - period_start).days > MAX_PERIOD_DAYS:
            raise BusinessRuleError(
                f"一度に探せるのは{MAX_PERIOD_DAYS}日までです。期間を分けてください"
            )

        rules = constraints or default_constraints()
        tz = ZoneInfo(user.timezone or get_settings().timezone)

        busy = _merge(
            [
                (event.start_at, event.end_at)
                for event in self.events.search(
                    user.id,
                    EventSearchParams(from_=period_start, to=period_end, limit=1000),
                )
            ]
        )

        slots: list[FreeSlot] = []
        for day in _days_between(period_start, period_end, tz):
            if rules.exclude_weekends and day.weekday() >= 5:
                continue

            midnight = datetime.combine(day, time(0), tzinfo=tz)
            window_start = max(
                midnight + timedelta(hours=rules.day_start_hour), period_start
            )
            window_end = min(
                midnight + timedelta(hours=rules.day_end_hour), period_end
            )
            if window_end <= window_start:
                continue

            slots.extend(
                FreeSlot(start, end)
                for start, end in _gaps(window_start, window_end, busy)
                if (end - start).total_seconds() >= minutes_needed * 60
            )

        return slots

    def generate_schedule(
        self,
        user: User,
        *,
        period_start: datetime,
        period_end: datetime,
        task_ids: list[int] | None = None,
        constraints: ScheduleConstraints | None = None,
        max_minutes_per_day: int = DEFAULT_MAX_MINUTES_PER_DAY,
    ) -> SchedulePlan:
        """未完了タスクを空き時間へ配置した案を作る。

        **ここでは登録しない。** 提案を返し、ユーザーの承認後に予定化する
        （要件定義書 19）。配置の規則は LLM ではなくこのメソッドが持つ。
        """
        rules = constraints or default_constraints()
        tz = ZoneInfo(user.timezone or get_settings().timezone)

        # 空き時間は1分単位で全部取り、ここで埋めていく
        free: list[list[datetime]] = [
            [slot.start_at, slot.end_at]
            for slot in self.find_free_time(
                user,
                period_start=period_start,
                period_end=period_end,
                minutes_needed=1,
                constraints=rules,
            )
        ]

        used_per_day: dict[date, int] = defaultdict(int)
        items: list[ScheduledItem] = []
        skipped: list[SkippedTask] = []

        for task in self._tasks_to_schedule(user, task_ids):
            if not task.estimated_minutes:
                skipped.append(
                    SkippedTask(task.id, task.title, "所要時間が未設定です")
                )
                continue

            item, reason = self._place_task(
                task, free, used_per_day, tz, max_minutes_per_day
            )
            if item is None:
                skipped.append(SkippedTask(task.id, task.title, reason))
            else:
                items.append(item)

        items.sort(key=lambda item: item.start_at)
        return SchedulePlan(
            items=items,
            skipped=skipped,
            rule=_describe_plan_rule(rules, max_minutes_per_day),
        )

    def reschedule_unfinished(
        self,
        user: User,
        *,
        now: datetime,
        period_end: datetime,
        period_start: datetime | None = None,
        constraints: ScheduleConstraints | None = None,
        max_minutes_per_day: int = DEFAULT_MAX_MINUTES_PER_DAY,
    ) -> ReschedulePlan:
        """終わらなかった作業時間を、これからの空き時間へ組み直す案を作る。

        対象は「終了時刻を過ぎたのに、紐づくタスクが未完了のままの予定」。
        **ここでは何も変更しない。** 承認後に予定を差し替える。
        """
        rules = constraints or default_constraints()
        tz = ZoneInfo(user.timezone or get_settings().timezone)
        # 過去へは置き直せないので開始は現在以降。
        # 「17:09:48から」のような提案にならないよう15分単位へ切り上げる
        # 返す日時は利用者のタイムゾーンで表す。UTC のまま返すと
        # LLM が「8:15」のように時差込みの数字をそのまま報告してしまう
        start_from = round_up_to_quarter(max(period_start or now, now)).astimezone(tz)

        stale = self.events.past_events_of_unfinished_tasks(user.id, now)
        if not stale:
            return ReschedulePlan(
                items=[], skipped=[], rule=_describe_plan_rule(rules, max_minutes_per_day)
            )

        free: list[list[datetime]] = [
            [slot.start_at, slot.end_at]
            for slot in self.find_free_time(
                user,
                period_start=start_from,
                period_end=period_end,
                minutes_needed=1,
                constraints=rules,
            )
        ]

        used_per_day: dict[date, int] = defaultdict(int)
        items: list[RescheduledItem] = []
        skipped: list[SkippedTask] = []

        for event in stale:
            task = event.task
            assert task is not None  # 問い合わせで紐付きのみ取得している
            minutes = int((event.end_at - event.start_at).total_seconds() // 60)

            slot, reason = _find_slot(
                minutes=minutes,
                due_date=task.due_date,
                free=free,
                used_per_day=used_per_day,
                tz=tz,
                max_minutes_per_day=max_minutes_per_day,
            )
            if slot is None:
                skipped.append(SkippedTask(task.id, task.title, reason))
                continue

            items.append(
                RescheduledItem(
                    task_id=task.id,
                    title=task.title,
                    previous_event_id=event.id,
                    previous_start_at=event.start_at,
                    start_at=slot[0],
                    end_at=slot[1],
                )
            )

        items.sort(key=lambda item: item.start_at)
        return ReschedulePlan(
            items=items,
            skipped=skipped,
            rule=_describe_plan_rule(rules, max_minutes_per_day),
        )

    def _tasks_to_schedule(self, user: User, task_ids: list[int] | None) -> list[Task]:
        tasks = self.tasks.search(
            user.id,
            TaskSearchParams(
                statuses=[TaskStatus.TODO, TaskStatus.IN_PROGRESS], limit=100
            ),
        )
        if task_ids is not None:
            wanted = set(task_ids)
            tasks = [task for task in tasks if task.id in wanted]
        return sorted(tasks, key=sort_key_for_scheduling)

    def _place_task(
        self,
        task: Task,
        free: list[list[datetime]],
        used_per_day: dict[date, int],
        tz: ZoneInfo,
        max_minutes_per_day: int,
    ) -> tuple[ScheduledItem | None, str]:
        slot, reason = _find_slot(
            minutes=task.estimated_minutes or 0,
            due_date=task.due_date,
            free=free,
            used_per_day=used_per_day,
            tz=tz,
            max_minutes_per_day=max_minutes_per_day,
        )
        if slot is None:
            return None, reason
        return (
            ScheduledItem(
                task_id=task.id, title=task.title, start_at=slot[0], end_at=slot[1]
            ),
            "",
        )



def default_constraints() -> ScheduleConstraints:
    settings = get_settings()
    return ScheduleConstraints(
        day_start_hour=settings.schedule_day_start_hour,
        day_end_hour=settings.schedule_day_end_hour,
    )


def _days_between(start: datetime, end: datetime, tz: ZoneInfo) -> list[date]:
    """期間に含まれる日付を、利用者のタイムゾーンで数える。"""
    first = start.astimezone(tz).date()
    last = end.astimezone(tz).date()
    return [first + timedelta(days=i) for i in range((last - first).days + 1)]


def _merge(intervals: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    """重なり合う予定を1つにまとめる（空き時間の計算を単純にするため）。"""
    merged: list[tuple[datetime, datetime]] = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            last_start, last_end = merged[-1]
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def _gaps(
    window_start: datetime,
    window_end: datetime,
    busy: list[tuple[datetime, datetime]],
) -> list[tuple[datetime, datetime]]:
    """稼働時間帯から予定を差し引いた残りを返す。"""
    gaps: list[tuple[datetime, datetime]] = []
    cursor = window_start

    for start, end in busy:
        if end <= cursor:
            continue
        if start >= window_end:
            break
        if start > cursor:
            gaps.append((cursor, min(start, window_end)))
        cursor = max(cursor, end)
        if cursor >= window_end:
            return gaps

    if cursor < window_end:
        gaps.append((cursor, window_end))
    return gaps


def _find_slot(
    *,
    minutes: int,
    due_date: datetime | None,
    free: list[list[datetime]],
    used_per_day: dict[date, int],
    tz: ZoneInfo,
    max_minutes_per_day: int,
) -> tuple[tuple[datetime, datetime] | None, str]:
    """空き時間の早い順に、最初に収まる場所を確保する。

    見つかった分は free から取り除く（同じ時間に二重に置かないため）。
    自動配置と再配置の両方から使う。
    """
    duration = timedelta(minutes=minutes)
    blocked_by_daily_cap = False

    for index, (start, end) in enumerate(free):
        day = start.astimezone(tz).date()

        if used_per_day[day] + minutes > max_minutes_per_day:
            blocked_by_daily_cap = True
            continue
        if end - start < duration:
            continue

        finish = start + duration
        if due_date is not None and finish > due_date:
            # 空きは時刻順なので、これ以降はさらに遅くなる
            return None, "期限までに空き時間が足りません"

        free[index] = [finish, end]
        if free[index][0] >= free[index][1]:
            free.pop(index)
        used_per_day[day] += minutes

        return (start, finish), ""

    if blocked_by_daily_cap:
        return None, "1日の作業上限に達したため置けませんでした"
    return None, "十分な長さの空き時間がありません"


def round_up_to_quarter(moment: datetime) -> datetime:
    """15分単位へ切り上げる（提案する開始時刻を読みやすくするため）。"""
    if moment.minute % 15 == 0 and moment.second == 0 and moment.microsecond == 0:
        return moment
    return (moment + timedelta(minutes=15 - moment.minute % 15)).replace(
        second=0, microsecond=0
    )
