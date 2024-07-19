from typing import Any, Callable, Mapping, TypeVar, TypedDict

from homeassistant.core import (
    HomeAssistant,
    Event,
    callback,
)
from homeassistant.components.logbook import (
    LOGBOOK_ENTRY_MESSAGE,
    LOGBOOK_ENTRY_NAME,
    LOGBOOK_ENTRY_ENTITY_ID,
)
from homeassistant.util.event_type import EventType

from .const import DOMAIN

_DataT = TypeVar("_DataT", bound=Mapping[str, Any])
_DescribeEventCallbackT = Callable[[str, EventType[_DataT], Callable[[Event[_DataT]], dict[str, str]]], None]


class EventSchedulerChangedData(TypedDict):
    entity_id: str
    display_name: str
    service: str

EVENT_SCHEDULER_CHANGED: EventType[EventSchedulerChangedData] = EventType("scheduler_state_change")

@callback
def async_describe_events(
    hass: HomeAssistant,
    async_describe_event: _DescribeEventCallbackT[EventSchedulerChangedData]
) -> None:
    """Describe logbook events."""

    @callback
    def async_describe_logbook_event(
        event: Event[EventSchedulerChangedData],
    ) -> dict[str, str]:
        """Describe a logbook event."""

        return {
            LOGBOOK_ENTRY_NAME: "Scheduler",
            LOGBOOK_ENTRY_MESSAGE: f"send command {event.data['service']} for {event.data['display_name']}",
            LOGBOOK_ENTRY_ENTITY_ID: event.data['entity_id'],
        }

    async_describe_event(DOMAIN, EVENT_SCHEDULER_CHANGED, async_describe_logbook_event)
