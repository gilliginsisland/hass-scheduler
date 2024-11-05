from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .scheduler import Scheduler


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[Scheduler],
) -> bool:
    _async_register_service(hass, entry)

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


def _async_register_service(
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
