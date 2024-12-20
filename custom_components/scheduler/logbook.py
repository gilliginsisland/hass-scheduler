from typing import Any, Callable, Mapping, TypeVar, TypedDict

from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_SERVICE,
)
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
_DescribeEventCallbackT = Callable[[Event[_DataT]], dict[str, str]]
_DescribeEventT = Callable[[str, EventType[_DataT], _DescribeEventCallbackT[_DataT]], None]


class EventSchedulerChangedData(TypedDict):
    entity_id: str
    friendly_name: str
    service: str

EVENT_SCHEDULER_CHANGED: EventType[EventSchedulerChangedData] = EventType("scheduler_state_change")

@callback
def async_describe_events(
    hass: HomeAssistant,
    async_describe_event: _DescribeEventT[EventSchedulerChangedData]
) -> None:
    """Describe logbook events."""

    @callback
    def async_describe_logbook_event(
        event: Event[EventSchedulerChangedData],
    ) -> dict[str, str]:
        """Describe a logbook event."""
        data = event.data

        message = f"send command {data[ATTR_SERVICE]} for {data[ATTR_FRIENDLY_NAME]}"

        return {
            LOGBOOK_ENTRY_NAME: "Scheduler",
            LOGBOOK_ENTRY_MESSAGE: message,
            LOGBOOK_ENTRY_ENTITY_ID: data[ATTR_ENTITY_ID],
        }

    async_describe_event(DOMAIN, EVENT_SCHEDULER_CHANGED, async_describe_logbook_event)
