from datetime import datetime
from functools import partial

from homeassistant.core import (
    CALLBACK_TYPE,
    HomeAssistant,
    callback,
    Context,
    DOMAIN as HOMEASSISTANT_DOMAIN
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_SERVICE,
    SERVICE_TURN_ON,
    SERVICE_TURN_OFF,
)
from homeassistant.helpers.event import (
    async_track_point_in_time,
)
from homeassistant.util import dt as dt_util

from .logbook import (
    EVENT_SCHEDULER_CHANGED,
    EventSchedulerChangedData,
)


class Event():
    def __init__(
        self,
        hass: HomeAssistant,
        *,
        entity_id: str,
        friendly_name: str,
        on_datetime: datetime | None = None,
        off_datetime: datetime | None = None,
    ):
        self.hass = hass
        self.entity_id = entity_id
        self.friendly_name = friendly_name

        self._actions: list[tuple[str, datetime]] = []
        if on_datetime:
            self._actions.append((SERVICE_TURN_ON,  on_datetime))
        if off_datetime:
            self._actions.append((SERVICE_TURN_OFF,  off_datetime))

        self.subscriptions: dict[tuple[str, datetime], CALLBACK_TYPE] = {}

    def track(self) -> CALLBACK_TYPE:
        now = dt_util.utcnow()

        # sort by latest datetime first
        # so we can break at first event in the past
        for service, dt in sorted(self._actions, key=lambda x: x[1], reverse=True):
            # schedule and track the service datetime combo
            service_data = { ATTR_ENTITY_ID: self.entity_id }
            call_service = partial(self._async_call_service, service, service_data)
            self.subscriptions[(service, dt)] = async_track_point_in_time(
                self.hass, call_service, dt
            )

            # break if the current time is past the prev event since any earlier
            # event will be superceeded by the last one
            if now >= dt:
                break

        return self.untrack

    def untrack(self):
        for k in list(self.subscriptions.keys()):
            self.subscriptions.pop(k)()

    @callback
    def _async_call_service(self, service: str, service_data: dict[str, str], _: datetime):
        event_data: EventSchedulerChangedData = {
            ATTR_ENTITY_ID: self.entity_id,
            ATTR_FRIENDLY_NAME: self.friendly_name,
            ATTR_SERVICE: service,
        }
        context = Context()

        self.hass.bus.async_fire(EVENT_SCHEDULER_CHANGED, event_data, context=context)
        self.hass.async_create_task(
            self.hass.services.async_call(
                HOMEASSISTANT_DOMAIN, service, service_data, context=context
            )
        )
