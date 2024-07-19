import asyncio
from datetime import timedelta, datetime
from itertools import chain
from typing import Any, Callable, Coroutine, Iterable, Mapping
import logging

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from .const import (
    CALENDAR_HASS_KEY,
    CONF_CALENDARS,
    CONF_HISTORIC,
    CONF_INTERVAL,
    CONF_PRELOAD,
)

from .event import Event
from .util import ctag, parse_event

_LOGGER = logging.getLogger(__name__)


def _async_calendar_event_getter(
    hass: HomeAssistant,
    start: datetime,
    end: datetime,
) -> Callable[
    [CalendarEntity],
    Coroutine[Any, Any, Iterable[tuple[str, CalendarEvent]]]
]:
    async def _async_get_calendar_events(calendar: CalendarEntity) -> Iterable[tuple[str, CalendarEvent]]:
        return (
            (ctag(event), event)
            for event in await calendar.async_get_events(hass, start, end)
        )

    return _async_get_calendar_events


class Scheduler():
    def __init__(self, hass: HomeAssistant, config: Mapping[str, Any]):
        self.hass = hass

        self.calendars = set[str](config.get(CONF_CALENDARS, set()))
        self.historic = timedelta(seconds=config.get(CONF_HISTORIC, 300))
        self.preload = timedelta(seconds=config.get(CONF_PRELOAD, 86400))
        self.interval = timedelta(seconds=config.get(CONF_INTERVAL, 300))

        self._events: dict[str, Event] = {}
        self._cancel_interval: CALLBACK_TYPE | None = None

    def async_start(self):
        _LOGGER.debug("Starting calendar refresh interval")

        self._cancel_interval = async_track_time_interval(
            self.hass, self.async_refresh_events, self.interval
        )
        self.hass.async_create_task(
            self.async_refresh_events(dt_util.utcnow())
        )

    def async_stop(self):
        _LOGGER.debug("Stopping calendar refresh interval")

        if self._cancel_interval:
            self._cancel_interval()

        self._async_untrack(list(self._events))

    def _async_track(self, events: list[tuple[str, Event]]):
        for tag, event in events:
            _LOGGER.debug(f'Tracking new event: "{event.display_name}"<{tag}>')
            event.track()
            self._events[tag] = event

    def _async_untrack(self, tags: list[str]):
        for tag in tags:
            _LOGGER.debug(f'Untracking event: "{self._events[tag].display_name}"<{tag}>')
            self._events.pop(tag).untrack()

    async def async_refresh_events(self, now: datetime):
        _LOGGER.debug("Getting list of calendars")
        entities = [
            entity for entity in self.hass.data[CALENDAR_HASS_KEY].entities
            if entity.entity_id in self.calendars
        ]

        _LOGGER.debug(f'Refreshing events for: {entities}')
        coros = map(_async_calendar_event_getter(
            self.hass,
            start=(now - self.historic),
            end=(now + self.preload),
        ), entities)

        calendar_events = dict(chain.from_iterable(await asyncio.gather(*coros)))

        self._async_untrack([
            tag for tag in self._events
            if tag not in calendar_events
        ])

        self._async_track([
            (tag, event)
            for tag, calendar_event in calendar_events.items()
            if tag not in self._events and (event := parse_event(self.hass, calendar_event))
        ])
