from typing import Any, Mapping

import voluptuous as vol

from homeassistant.helpers.schema_config_entry_flow import (
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
)
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
)

from .const import (
    DOMAIN,
    CALENDAR_DOMAIN,
    CONF_CALENDARS,
    CONF_HISTORIC,
    CONF_PRELOAD,
    CONF_INTERVAL,
)

CONFIG_SCHEMA = vol.Schema({
    vol.Required(CONF_CALENDARS): EntitySelector(
        EntitySelectorConfig(domain=CALENDAR_DOMAIN, multiple=True)
    ),
})

OPTIONS_SCHEMA = CONFIG_SCHEMA.extend({
    vol.Required(CONF_HISTORIC, default=300): int,
    vol.Required(CONF_PRELOAD, default=3600): int,
    vol.Required(CONF_INTERVAL, default=300): int,
})

CONFIG_FLOW = {
    "user": SchemaFlowFormStep(schema=CONFIG_SCHEMA)
}

OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(schema=OPTIONS_SCHEMA)
}


class SchedulerConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config flow for Scheduler."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""

        return f'Scheduler {options[CONF_CALENDARS]}'
