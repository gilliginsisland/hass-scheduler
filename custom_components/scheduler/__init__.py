from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN
from .scheduler import Scheduler


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[Scheduler],
) -> bool:
    scheduler = entry.runtime_data = Scheduler(hass, entry.options)
    scheduler.async_start()
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[Scheduler],
) -> bool:
    scheduler = entry.runtime_data
    scheduler.async_stop()
    return True
