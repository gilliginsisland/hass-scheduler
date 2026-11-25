from collections.abc import Iterable
from typing import (
	NamedTuple,
)

import probatio

from homeassistant.helpers import (
	area_registry as ar,
	device_registry as dr,
	entity_registry as er,
)
from homeassistant.core import (
	HomeAssistant,
	State,
)

_NAME_SCHEMA = probatio.All(str, str.strip)


class ParsedEventSummary(NamedTuple):
	entity_id_or_name: str
	invert: bool
	oneshot: bool


def friendly_name(state: State) -> str:
	try:
		return _NAME_SCHEMA(state.attributes.get('friendly_name', state.name))
	except probatio.Invalid:
		return state.entity_id


def entity_state(hass: HomeAssistant, entity_id_or_name: str) -> State | None:
	"""Find an entity by id or name"""
	entity_id_or_name = entity_id_or_name.strip().lower()

	if (state := hass.states.get(entity_id_or_name)) is not None:
		return state

	for state in hass.states.async_all():
		if friendly_name(state).lower() == entity_id_or_name:
			return state

	area_reg = ar.async_get(hass)
	for area in area_reg.areas.values():
		area_name = area.name.strip().lower()
		if not entity_id_or_name.startswith(area_name):
			continue

		suffix = entity_id_or_name[len(area_name):].strip()
		for entity_id in area_entities(hass, area.id):
			if (state := hass.states.get(entity_id)) and friendly_name(state).lower() == suffix:
				return state

	return None


def parse_event_summary(entity_id_or_name: str) -> ParsedEventSummary | None:
	"""Parse the event name"""

	entity_id_or_name = entity_id_or_name.strip()
	if entity_id_or_name.startswith('!'):
		entity_id_or_name = entity_id_or_name[1:]
		invert = True
	else:
		invert = False

	if entity_id_or_name.endswith('+'):
		entity_id_or_name = entity_id_or_name[:-1]
		oneshot = True
	else:
		oneshot = False

	entity_id_or_name = entity_id_or_name.strip()
	if not entity_id_or_name:
		return None

	return ParsedEventSummary(
		entity_id_or_name, invert=invert, oneshot=oneshot
	)


def area_entities(hass: HomeAssistant, area_id: str) -> Iterable[str]:
	"""Return entities for a given area ID or name."""

	ent_reg = er.async_get(hass)
	yield from (
		entry.entity_id for entry in er.async_entries_for_area(ent_reg, area_id)
	)

	dev_reg = dr.async_get(hass)
	# We also need to add entities tied to a device in the area that don't themselves
	# have an area specified since they inherit the area from the device.
	yield from (
		entity.entity_id
		for device in dr.async_entries_for_area(dev_reg, area_id)
		for entity in er.async_entries_for_device(ent_reg, device.id)
		if entity.area_id is None
	)
