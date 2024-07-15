from homeassistant.components.calendar import (
	DOMAIN as CALENDAR_DOMAIN,
	CalendarEntity,
)
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.util.hass_dict import HassKey

DOMAIN = "scheduler"

CALENDAR_HASS_KEY: HassKey[EntityComponent[CalendarEntity]] = HassKey(CALENDAR_DOMAIN)

CONF_ALIASES = "aliases"
CONF_CALENDARS = "calendars"
CONF_HISTORIC = "historic"
CONF_PRELOAD = "preload"
CONF_INTERVAL = "interval"
