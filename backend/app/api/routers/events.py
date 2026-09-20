from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, EventServiceDep
from app.models.calendar_event import CalendarEvent
from app.schemas.common import AwareDatetime
from app.schemas.event import EventCreate, EventRead, EventSearchParams, EventUpdate
from app.schemas.task import SortOrder

router = APIRouter(prefix="/events", tags=["events"])


@router.post("", response_model=EventRead, status_code=status.HTTP_201_CREATED)
def create_event(
    payload: EventCreate, user: CurrentUser, service: EventServiceDep
) -> CalendarEvent:
    return service.create(user, payload)


@router.get("", response_model=list[EventRead])
def search_events(
    user: CurrentUser,
    service: EventServiceDep,
    from_: AwareDatetime | None = Query(
        default=None, alias="from", description="この日時以降に終わる予定"
    ),
    to: AwareDatetime | None = Query(
        default=None, description="この日時より前に始まる予定"
    ),
    keyword: str | None = None,
    task_id: int | None = None,
    order: SortOrder = SortOrder.ASC,
    limit: int = Query(default=500, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> list[CalendarEvent]:
    params = EventSearchParams(
        from_=from_,
        to=to,
        keyword=keyword,
        task_id=task_id,
        order=order,
        limit=limit,
        offset=offset,
    )
    return service.search(user, params)


@router.get("/{event_id}", response_model=EventRead)
def get_event(
    event_id: int, user: CurrentUser, service: EventServiceDep
) -> CalendarEvent:
    return service.get(user, event_id)


@router.patch("/{event_id}", response_model=EventRead)
def update_event(
    event_id: int, payload: EventUpdate, user: CurrentUser, service: EventServiceDep
) -> CalendarEvent:
    return service.update(user, event_id, payload)


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(event_id: int, user: CurrentUser, service: EventServiceDep) -> None:
    service.delete(user, event_id)
