"""Refresh calendar schedules and reconcile the states they currently require."""

import asyncio
from collections.abc import Collection, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import TYPE_CHECKING, Literal, TypedDict, cast

from homeassistant.components.calendar import CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_SERVICE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    Context,
    Event,
    EventStateChangedData,
    HomeAssistant,
    callback,
    valid_entity_id,
)
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util import dt as dt_util

from .const import (
    COMMAND_TIMEOUT,
    DOMAIN,
    SIGNAL_SCHEDULES_UPDATED,
)
from .coordinator import CalendarCoordinator
from .logbook import EVENT_SCHEDULER_CHANGED, EventSchedulerChangedData
from .util import entity_state, friendly_name, parse_event_summary

if TYPE_CHECKING:
    from .config_flow import SchedulerOptions

_LOGGER = logging.getLogger(__name__)


type ActionStatus = Literal["upcoming", "pending", "confirmed", "overridden", "unresolved"]


class ScheduledAction(TypedDict):
    calendar_id: str
    target: str
    entity_id: str | None
    name: str
    start: str
    end: str
    state: Literal["on", "off"]
    current_state: str | None
    end_control: bool
    status: ActionStatus


class CalendarStatus(TypedDict):
    entity_id: str
    available: bool
    error: str | None


class SchedulerSnapshot(TypedDict):
    entry_id: str
    title: str
    actions: list[ScheduledAction]
    calendars: list[CalendarStatus]


@dataclass(frozen=True)
class Schedule():
    calendar_id: str
    target: str
    start: datetime
    end: datetime
    state: Literal["on", "off"]
    priority: Literal[0, 1] = 1

    @property
    def sort_key(self) -> tuple[int, datetime, bool]:
        # Calendar schedules beat end control; later starts beat earlier ones.
        # Equally timed contradictory schedules deterministically prefer off.
        return self.priority, self.start, self.state == "off"


@dataclass
class _RetryAttempt():
    schedule: Schedule
    next_at: float = 0
    failed: bool = False


def parse_event(event: CalendarEvent, calendar_id: str, end_control: timedelta) -> list[Schedule]:
    """Expand a calendar event into its primary and optional end schedules."""

    if (data := parse_event_summary(event.summary)) is None:
        return []

    start = dt_util.as_utc(event.start_datetime_local)
    end = dt_util.as_utc(event.end_datetime_local)
    if end <= start:
        return []

    schedules = [Schedule(
        calendar_id=calendar_id,
        target=data.entity_id_or_name,
        start=start,
        end=end,
        state="off" if data.invert else "on",
    )]
    if not data.oneshot and end_control > timedelta():
        schedules.append(Schedule(
            calendar_id=calendar_id,
            target=data.entity_id_or_name,
            start=end,
            end=(end + end_control),
            state="on" if data.invert else "off",
            priority=0,
        ))
    return schedules


class Scheduler():
    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry["Scheduler"],
    ) -> None:
        options = cast("SchedulerOptions", cast(object, entry.options))
        self.hass: HomeAssistant = hass
        self.config_entry: ConfigEntry["Scheduler"] = entry
        self._retry_interval: float = options["retry_interval"]
        self._end_control: timedelta = timedelta(seconds=options["end_control"])
        self._calendars: dict[str, CalendarCoordinator["Scheduler"]] = {
            entity_id: CalendarCoordinator(hass, entry, entity_id, options)
            for entity_id in sorted(set(options["calendars"]))
        }
        self._task: asyncio.Task[None] | None = None
        self._wakeup: asyncio.Event = asyncio.Event()
        self._unresolved: set[str] = set()
        self._cancel_listeners: list[CALLBACK_TYPE] = []

    @callback
    def async_start(self) -> None:
        """Watch calendar readiness, poll independently, and start enforcement."""
        if self._calendars:
            self._cancel_listeners.append(async_track_state_change_event(
                self.hass, self._calendars, self._async_calendar_ready
            ))
        for calendar in self._calendars.values():
            self._cancel_listeners.append(calendar.async_add_listener(self._wakeup.set))
            calendar.async_refresh_if_ready()
        self._task = self.config_entry.async_create_background_task(
            self.hass,
            self._async_run(),
            f'{DOMAIN} {self.config_entry.entry_id} enforcement',
        )

    @callback
    def _async_calendar_ready(self, event: Event[EventStateChangedData]) -> None:
        """Refresh when a selected calendar appears or becomes available again."""
        self._wakeup.set()
        previous = event.data["old_state"]
        if previous is None or previous.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            self._calendars[event.data["entity_id"]].async_refresh_if_ready()

    async def async_stop(self) -> None:
        """Remove listeners and stop enforcement and calendar polling."""
        for cancel in self._cancel_listeners:
            cancel()
        self._cancel_listeners.clear()
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None
        await asyncio.gather(*(
            calendar.async_shutdown() for calendar in self._calendars.values()
        ))

    def _active_schedules(self, now: datetime) -> tuple[dict[str, Schedule], datetime | None]:
        """Choose one active schedule per entity and the next boundary."""
        desired: dict[str, Schedule] = {}
        next_change: datetime | None = None
        unresolved: set[str] = set()
        for schedule in self._schedules():
            for boundary in (schedule.start, schedule.end):
                if now < boundary and (next_change is None or boundary < next_change):
                    next_change = boundary
            if not schedule.start <= now < schedule.end:
                continue

            if (entity_id := self._resolve_target(schedule.target)) is None:
                target = schedule.target
                unresolved.add(target)
                if target not in self._unresolved:
                    _LOGGER.warning(
                        "Could not resolve scheduled entity %s; will retry", target
                    )
                continue
            if entity_id not in desired or schedule.sort_key > desired[entity_id].sort_key:
                desired[entity_id] = schedule
        self._unresolved = unresolved
        return desired, next_change

    def _schedules(self) -> Iterator[Schedule]:
        """Expand the current calendar data; removed events have no schedules."""
        for calendar in self._calendars.values():
            for event in calendar.data:
                yield from parse_event(event, calendar.entity_id, self._end_control)

    def _resolve_target(self, target: str) -> str | None:
        target = target.strip().lower()
        if valid_entity_id(target):
            return target
        state = entity_state(self.hass, target)
        return state.entity_id if state is not None else None

    @callback
    def async_get_tasks(self) -> SchedulerSnapshot:
        """Describe the same schedules and priorities used by enforcement."""
        now = dt_util.utcnow()
        desired, _ = self._active_schedules(now)
        actions: list[ScheduledAction] = []
        for schedule in self._schedules():
            if schedule.end <= now:
                continue
            entity_id = self._resolve_target(schedule.target)
            state = self.hass.states.get(entity_id) if entity_id is not None else None
            status: ActionStatus
            if entity_id is None:
                status = "unresolved"
            elif now < schedule.start:
                status = "upcoming"
            elif desired.get(entity_id) != schedule:
                status = "overridden"
            elif self._state_matches(entity_id, schedule):
                status = "confirmed"
            else:
                status = "pending"
            actions.append({
                "calendar_id": schedule.calendar_id,
                "target": schedule.target,
                "entity_id": entity_id,
                "name": friendly_name(state) if state is not None else schedule.target,
                "start": schedule.start.isoformat(),
                "end": schedule.end.isoformat(),
                "state": schedule.state,
                "current_state": state.state if state is not None else None,
                "end_control": schedule.priority == 0,
                "status": status,
            })
        actions.sort(key=lambda action: (action["start"], action["end"], action["name"]))
        return {
            "entry_id": self.config_entry.entry_id,
            "title": self.config_entry.title,
            "actions": actions,
            "calendars": [{
                "entity_id": calendar.entity_id,
                "available": calendar.calendar is not None,
                "error": str(calendar.last_exception) if not calendar.last_update_success else None,
            } for calendar in self._calendars.values()],
        }

    async def _async_run(self) -> None:
        attempts: dict[str, _RetryAttempt] = {}
        while True:
            self._wakeup.clear()
            active, next_change = self._active_schedules(dt_util.utcnow())
            with self._track_state_changes(active):
                async_dispatcher_send(self.hass, SIGNAL_SCHEDULES_UPDATED)
                delay = await self._async_retry(active, attempts)
                if delay == 0:
                    # Re-read states and ownership after commands finish.
                    continue
                await self._async_wait_for_change(next_change, delay)

    async def _async_retry(
        self,
        schedules: dict[str, Schedule],
        attempts: dict[str, _RetryAttempt],
    ) -> float | None:
        """Return the next retry delay, zero to re-read, or None when idle."""
        for entity_id, attempt in list(attempts.items()):
            if schedules.get(entity_id) != attempt.schedule:
                del attempts[entity_id]

        pending: dict[str, _RetryAttempt] = {}
        now = asyncio.get_running_loop().time()
        for entity_id, schedule in schedules.items():
            if self._state_matches(entity_id, schedule):
                if attempts.pop(entity_id, None) is not None:
                    _LOGGER.info("Confirmed %s is %s", entity_id, schedule.state)
                continue

            attempt = attempts.get(entity_id)
            if attempt is None:
                attempt = attempts[entity_id] = _RetryAttempt(schedule)
            if now < attempt.next_at:
                continue
            attempt.next_at = now + self._retry_interval
            pending[entity_id] = attempt

        if not pending:
            next_at = min(
                (attempt.next_at for attempt in attempts.values()),
                default=None,
            )
            if next_at is None:
                # An active target named by the user may not be loaded yet.
                return self._retry_interval if self._unresolved else None
            return max(0, next_at - now)

        results = await asyncio.gather(*(
            self._async_apply(entity_id, attempt.schedule)
            for entity_id, attempt in pending.items()
        ), return_exceptions=True)
        for (entity_id, attempt), result in zip(pending.items(), results):
            if isinstance(result, BaseException) and not attempt.failed:
                _LOGGER.warning(
                    "Could not confirm %s is %s; retrying while its schedule is active: %s",
                    entity_id, attempt.schedule.state, result,
                )
                attempt.failed = True
        return 0

    def _state_matches(self, entity_id: str, schedule: Schedule) -> bool:
        state = self.hass.states.get(entity_id)
        return state is not None and state.state == schedule.state

    @contextmanager
    def _track_state_changes(self, entities: Collection[str]) -> Iterator[None]:
        """Listen to active targets, including ones already in the desired state."""
        @callback
        def _async_state_changed(_event: Event[EventStateChangedData]) -> None:
            self._wakeup.set()

        cancel = async_track_state_change_event(
            self.hass, entities, _async_state_changed
        ) if entities else None
        try:
            yield
        finally:
            if cancel:
                cancel()

    async def _async_wait_for_change(self, next_change: datetime | None, retry_delay: float | None) -> None:
        if next_change is not None:
            boundary_delay = max(0, (next_change - dt_util.utcnow()).total_seconds())
            retry_delay = boundary_delay if retry_delay is None else min(retry_delay, boundary_delay)
        try:
            await asyncio.wait_for(self._wakeup.wait(), timeout=retry_delay)
        except TimeoutError:
            pass

    async def _async_apply(self, entity_id: str, schedule: Schedule) -> None:
        """Send a bounded command; only a matching reported state confirms it."""
        desired, next_change = self._active_schedules(dt_util.utcnow())
        # A refresh may have removed this event since the retry was queued.
        if desired.get(entity_id) != schedule or next_change is None:
            return
        timeout = min(
            COMMAND_TIMEOUT,
            (next_change - dt_util.utcnow()).total_seconds(),
        )
        if timeout <= 0:
            return
        state = self.hass.states.get(entity_id)
        if state is None or state.state == STATE_UNAVAILABLE:
            raise ValueError("Entity is unavailable")
        service = "turn_on" if schedule.state == "on" else "turn_off"
        _LOGGER.debug("Requesting %s for %s", service, entity_id)
        context = Context()
        event_data: EventSchedulerChangedData = {
            ATTR_ENTITY_ID: entity_id,
            ATTR_FRIENDLY_NAME: friendly_name(state),
            ATTR_SERVICE: service,
            "calendar_id": schedule.calendar_id,
            "end_control": schedule.priority == 0,
        }
        self.hass.bus.async_fire(EVENT_SCHEDULER_CHANGED, event_data, context=context)
        async with asyncio.timeout(timeout):
            await self.hass.services.async_call(
                "homeassistant", service, {ATTR_ENTITY_ID: entity_id},
                blocking=True, context=context,
            )
        if not self._state_matches(entity_id, schedule):
            raise ValueError("Requested state has not been reported")
