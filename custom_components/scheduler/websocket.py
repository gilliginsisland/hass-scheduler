from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant, callback
from homeassistant.components import panel_custom, websocket_api


async def register_panel(hass: HomeAssistant) -> None:
    websocket_api.async_register_command(hass, ws_get_tasks)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "scheduler/tasks",
    }
)
@callback
def ws_get_tasks(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
):
    connection.send_result(msg["id"], [])
