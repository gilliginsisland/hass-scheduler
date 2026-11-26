from functools import partial
from pathlib import Path

from homeassistant.components import frontend, websocket_api
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.typing import ConfigType
from homeassistant.exceptions import ConfigEntryError

from .const import (
    DOMAIN,
    CARD_URL,
    SIGNAL_SCHEDULES_UPDATED,
    CONF_PRELOAD,
    CONF_INTERVAL,
    CONF_END_CONTROL,
    CONF_RETRY_INTERVAL,
    DEFAULT_PRELOAD,
    DEFAULT_INTERVAL,
    DEFAULT_END_CONTROL,
    DEFAULT_RETRY_INTERVAL,
)
from .scheduler import Scheduler
from .websocket import ws_get_tasks, ws_subscribe_tasks


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the read-only API and dashboard card once per integration."""
    websocket_api.async_register_command(hass, ws_get_tasks)
    websocket_api.async_register_command(hass, ws_subscribe_tasks)
    await hass.http.async_register_static_paths([
        StaticPathConfig(CARD_URL, str(Path(__file__).parent / "scheduler-card.js"), False)
    ])
    frontend.add_extra_js_url(hass, CARD_URL)
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[Scheduler],
) -> None:
    """Set up Calendar Scheduler from a config entry."""
    _async_register_device(hass, entry)

    scheduler = entry.runtime_data = Scheduler(hass, entry)
    entry.async_on_unload(entry.async_on_state_change(
        partial(async_dispatcher_send, hass, SIGNAL_SCHEDULES_UPDATED)
    ))
    scheduler.async_start()


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry[Scheduler]) -> None:
    """Fill missing defaults for entries created with the calendars-only form."""
    if entry.version > 1:
        raise ConfigEntryError("Unsupported scheduler configuration version")
    if entry.minor_version < 2:
        options = {
            CONF_PRELOAD: DEFAULT_PRELOAD,
            CONF_INTERVAL: DEFAULT_INTERVAL,
            CONF_END_CONTROL: DEFAULT_END_CONTROL,
            CONF_RETRY_INTERVAL: DEFAULT_RETRY_INTERVAL,
            **entry.options,
        }
        options.pop("historic", None)
        hass.config_entries.async_update_entry(
            entry,
            options=options,
            minor_version=2,
        )


async def async_unload_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[Scheduler],
) -> None:
    """Unload Calendar Scheduler and await its workers."""
    scheduler = entry.runtime_data
    await scheduler.async_stop()


def _async_register_device(
    hass: HomeAssistant,
    entry: ConfigEntry[Scheduler],
) -> None:
    dev_reg = dr.async_get(hass)
    dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
        entry_type=dr.DeviceEntryType.SERVICE,
    )
