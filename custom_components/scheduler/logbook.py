from collections.abc import Callable
from typing import Literal, NotRequired, TypedDict

import probatio

from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_SERVICE,
)
from homeassistant.core import (
    HomeAssistant,
    callback,
)
from homeassistant.components.logbook import (
    LOGBOOK_ENTRY_MESSAGE,
    LOGBOOK_ENTRY_NAME,
    LOGBOOK_ENTRY_ENTITY_ID,
    LazyEventPartialState,
)
from homeassistant.util.event_type import EventType

from .const import DOMAIN

type _DescribeEventCallbackT = Callable[[LazyEventPartialState], dict[str, str]]
type _DescribeEventT = Callable[[str, str | EventType[EventSchedulerChangedData], _DescribeEventCallbackT], None]


class EventSchedulerChangedData(TypedDict):
    entity_id: str
    friendly_name: str
    service: Literal["turn_on", "turn_off"]
    # Older recorded events do not include their calendar or reason.
    calendar_id: NotRequired[str]
    end_control: NotRequired[bool]

_EVENT_DATA_SCHEMA = probatio.TypedDictSchema(EventSchedulerChangedData)

EVENT_SCHEDULER_CHANGED: EventType[EventSchedulerChangedData] = EventType("scheduler_state_change")

@callback
def async_describe_events(
    hass: HomeAssistant,
    async_describe_event: _DescribeEventT
) -> None:
    """Describe logbook events."""

    @callback
    def async_describe_logbook_event(
        event: LazyEventPartialState,
    ) -> dict[str, str]:
        """Describe a logbook event."""
        data = _EVENT_DATA_SCHEMA(event.data)

        message = f"send command {data[ATTR_SERVICE]} for {data[ATTR_FRIENDLY_NAME]}"
        if calendar_id := data.get("calendar_id"):
            reason = "an event ended" if data.get("end_control") else "an event is active"
            message += f" because {reason} on {calendar_id}"

        return {
            LOGBOOK_ENTRY_NAME: "Scheduler",
            LOGBOOK_ENTRY_MESSAGE: message,
            LOGBOOK_ENTRY_ENTITY_ID: data[ATTR_ENTITY_ID],
        }

    async_describe_event(DOMAIN, EVENT_SCHEDULER_CHANGED, async_describe_logbook_event)
