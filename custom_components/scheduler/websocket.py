"""Expose the scheduler's current plan without fetching or changing calendars."""

from typing import TYPE_CHECKING, cast

import probatio

from homeassistant.auth.permissions.const import POLICY_READ
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN, SIGNAL_SCHEDULES_UPDATED

if TYPE_CHECKING:
    from .scheduler import Scheduler, SchedulerSnapshot


@callback
def _tasks(hass: HomeAssistant, connection: websocket_api.ActiveConnection) -> list["SchedulerSnapshot"]:
    result: list["SchedulerSnapshot"] = []
    for entry in hass.config_entries.async_loaded_entries(DOMAIN):
        snapshot = cast("Scheduler", entry.runtime_data).async_get_tasks()
        can_read = connection.user.permissions.check_entity
        snapshot["calendars"] = [
            calendar for calendar in snapshot["calendars"]
            if can_read(calendar["entity_id"], POLICY_READ)
        ]
        snapshot["actions"] = [
            action for action in snapshot["actions"]
            if can_read(action["calendar_id"], POLICY_READ)
            and (action["entity_id"] is None or can_read(action["entity_id"], POLICY_READ))
        ]
        if snapshot["calendars"]:
            result.append(snapshot)
    return result


@websocket_api.websocket_command({probatio.Required("type"): "scheduler/tasks"})
@callback
def ws_get_tasks(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, object],
) -> None:
    """Return active and upcoming actions across loaded scheduler entries."""
    connection.send_result(cast(int, msg["id"]), _tasks(hass, connection))


@websocket_api.websocket_command({probatio.Required("type"): "scheduler/subscribe"})
@callback
def ws_subscribe_tasks(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, object],
) -> None:
    """Send an initial snapshot and changes; HA cleans up on unsubscribe."""
    message_id = cast(int, msg["id"])
    previous: list["SchedulerSnapshot"] | None = None

    @callback
    def async_send_tasks() -> None:
        nonlocal previous
        snapshot = _tasks(hass, connection)
        if snapshot != previous:
            previous = snapshot
            connection.send_event(message_id, snapshot)

    connection.subscriptions[message_id] = async_dispatcher_connect(
        hass, SIGNAL_SCHEDULES_UPDATED, async_send_tasks
    )
    connection.send_result(message_id)
    async_send_tasks()
