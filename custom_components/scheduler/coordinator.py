"""Poll one ready calendar independently of the other calendars."""

import asyncio
from datetime import timedelta
import logging
from typing import TYPE_CHECKING, override

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.components.calendar.const import DATA_COMPONENT as CALENDAR_DATA
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import CALENDAR_TIMEOUT, DOMAIN

if TYPE_CHECKING:
    from .config_flow import SchedulerOptions

_LOGGER = logging.getLogger(__name__)


class CalendarCoordinator[T](DataUpdateCoordinator[list[CalendarEvent]]):
    config_entry: ConfigEntry[T]

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry[T],
        entity_id: str,
        options: "SchedulerOptions",
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=entity_id,
            update_interval=timedelta(seconds=options["interval"]),
            always_update=False,
        )
        self.entity_id: str = entity_id
        self.options: "SchedulerOptions" = options
        self.data: list[CalendarEvent] = []

    @property
    def calendar(self) -> CalendarEntity | None:
        component = self.hass.data.get(CALENDAR_DATA)
        calendar = component.get_entity(self.entity_id) if component is not None else None
        state = self.hass.states.get(self.entity_id)
        if (
            calendar is None or not calendar.available
            or state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN)
        ):
            return None
        return calendar

    @callback
    def async_refresh_if_ready(self) -> None:
        if self.calendar is not None:
            self.config_entry.async_create_background_task(
                self.hass,
                self.async_request_refresh(),
                f'{DOMAIN} refresh {self.entity_id}',
            )

    @override
    async def _async_update_data(self) -> list[CalendarEvent]:
        if (calendar := self.calendar) is None:
            return self.data
        now = dt_util.utcnow()
        end_control = timedelta(seconds=self.options["end_control"])
        preload = timedelta(seconds=self.options["preload"])
        try:
            async with asyncio.timeout(CALENDAR_TIMEOUT):
                # A successful read replaces all events, including with [].
                return await calendar.async_get_events(
                    self.hass,
                    dt_util.as_local(now - end_control),
                    dt_util.as_local(now + preload),
                )
        except Exception as err:
            raise UpdateFailed(f'Could not read calendar: {err}') from err
