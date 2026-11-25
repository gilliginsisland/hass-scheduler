from collections.abc import Mapping
from typing import TypedDict, override

import probatio

from homeassistant.components.calendar import DOMAIN as CALENDAR_DOMAIN
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
    SchemaFlowStep,
)
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
)

from .const import (
    DOMAIN,
    CONF_CALENDARS,
    CONF_PRELOAD,
    CONF_INTERVAL,
    CONF_END_CONTROL,
    CONF_RETRY_INTERVAL,
    DEFAULT_PRELOAD,
    DEFAULT_INTERVAL,
    DEFAULT_END_CONTROL,
    DEFAULT_RETRY_INTERVAL,
)


class SchedulerOptions(TypedDict):
    calendars: list[str]
    preload: int
    interval: int
    end_control: int
    retry_interval: int


OPTIONS_SCHEMA = probatio.Schema({
    probatio.Required(CONF_CALENDARS): EntitySelector(
        EntitySelectorConfig(domain=CALENDAR_DOMAIN, multiple=True)
    ),
    probatio.Required(CONF_PRELOAD, default=DEFAULT_PRELOAD): probatio.All(int, probatio.Range(min=0)),
    probatio.Required(CONF_INTERVAL, default=DEFAULT_INTERVAL): probatio.All(int, probatio.Range(min=1)),
    probatio.Required(CONF_END_CONTROL, default=DEFAULT_END_CONTROL): probatio.All(int, probatio.Range(min=0)),
    probatio.Required(CONF_RETRY_INTERVAL, default=DEFAULT_RETRY_INTERVAL): probatio.All(int, probatio.Range(min=1)),
})


CONFIG_FLOW: dict[str, SchemaFlowStep] = {
    "user": SchemaFlowFormStep(schema=OPTIONS_SCHEMA)
}

OPTIONS_FLOW: dict[str, SchemaFlowStep] = {
    "init": SchemaFlowFormStep(schema=OPTIONS_SCHEMA)
}


class SchedulerConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config flow for Scheduler."""

    MINOR_VERSION: int = 2

    config_flow: Mapping[str, SchemaFlowStep] = CONFIG_FLOW
    options_flow: Mapping[str, SchemaFlowStep] | None = OPTIONS_FLOW
    options_flow_reloads: bool = True

    @override
    def async_config_entry_title(self, options: Mapping[str, object]) -> str:
        """Return config entry title."""

        return f'Scheduler {options[CONF_CALENDARS]}'
