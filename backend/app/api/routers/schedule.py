from datetime import UTC, datetime

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, ScheduleServiceDep
from app.schemas.common import AwareDatetime
from app.schemas.schedule import (
    FreeSlotRead,
    FreeTimeResponse,
    ReschedulePlanResponse,
    SchedulePlanResponse,
)
from app.services.schedule_service import ScheduleConstraints, default_constraints

router = APIRouter(prefix="/schedule", tags=["schedule"])


@router.get("/free-time", response_model=FreeTimeResponse)
def find_free_time(
    user: CurrentUser,
    service: ScheduleServiceDep,
    period_start: AwareDatetime,
    period_end: AwareDatetime,
    minutes_needed: int = Query(ge=1, le=1440),
    exclude_weekends: bool = False,
) -> FreeTimeResponse:
    """空き時間を探す。通常UIとLLM Tool が同じ Service を使う。"""
    constraints = ScheduleConstraints(
        day_start_hour=default_constraints().day_start_hour,
        day_end_hour=default_constraints().day_end_hour,
        exclude_weekends=exclude_weekends,
    )
    slots = service.find_free_time(
        user,
        period_start=period_start,
        period_end=period_end,
        minutes_needed=minutes_needed,
        constraints=constraints,
    )
    return FreeTimeResponse(
        rule=constraints.describe(),
        count=len(slots),
        slots=[FreeSlotRead.from_slot(slot) for slot in slots],
    )


@router.get("/plan", response_model=SchedulePlanResponse)
def preview_schedule(
    user: CurrentUser,
    service: ScheduleServiceDep,
    period_start: AwareDatetime,
    period_end: AwareDatetime,
    exclude_weekends: bool = False,
) -> SchedulePlanResponse:
    """未完了タスクを空き時間に配置した案を返す（登録はしない）。"""
    defaults = default_constraints()
    plan = service.generate_schedule(
        user,
        period_start=period_start,
        period_end=period_end,
        constraints=ScheduleConstraints(
            day_start_hour=defaults.day_start_hour,
            day_end_hour=defaults.day_end_hour,
            exclude_weekends=exclude_weekends,
        ),
    )
    return SchedulePlanResponse.from_plan(plan)


@router.get("/reschedule-plan", response_model=ReschedulePlanResponse)
def preview_reschedule(
    user: CurrentUser,
    service: ScheduleServiceDep,
    period_end: AwareDatetime,
    period_start: AwareDatetime | None = None,
    exclude_weekends: bool = False,
) -> ReschedulePlanResponse:
    """終わらなかった作業を組み直す案を返す（反映はしない）。"""
    defaults = default_constraints()
    plan = service.reschedule_unfinished(
        user,
        now=datetime.now(UTC),
        period_start=period_start,
        period_end=period_end,
        constraints=ScheduleConstraints(
            day_start_hour=defaults.day_start_hour,
            day_end_hour=defaults.day_end_hour,
            exclude_weekends=exclude_weekends,
        ),
    )
    return ReschedulePlanResponse.from_plan(plan)
