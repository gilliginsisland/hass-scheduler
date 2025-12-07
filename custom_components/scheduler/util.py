from typing import (
	Iterable,
	NamedTuple,
)
from hashlib import sha256

from homeassistant.helpers import (
	area_registry as ar,
	device_registry as dr,
	entity_registry as er,
)
from homeassistant.components.calendar import CalendarEvent
from homeassistant.core import (
	HomeAssistant,
	State,
)

from .event import Event


class ParsedEventSummary(NamedTuple):
	entity_id_or_name: str
	invert: bool
	oneshot: bool


def friendly_name(state: State) -> str:
	return state.attributes.get('friendly_name', state.name).strip()


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


def parse_event_summary(entity_id_or_name: str) -> ParsedEventSummary:
	"""Parse the event name"""

	if entity_id_or_name[0] == '!':
		entity_id_or_name = entity_id_or_name[1:]
		invert = True
	else:
		invert = False

	if entity_id_or_name[-1] == '+':
		entity_id_or_name = entity_id_or_name[:-1]
		oneshot = True
	else:
		oneshot = False

	return ParsedEventSummary(
		entity_id_or_name, invert=invert, oneshot=oneshot
	)


def parse_event(hass: HomeAssistant, event: CalendarEvent) -> Event | None:
	"""Parse a calendar event into a scheduler event"""

	data = parse_event_summary(event.summary)

	if not (state := entity_state(hass, data.entity_id_or_name)):
		return None

	on_datetime = event.start_datetime_local
	off_datetime = event.end_datetime_local if not data.oneshot else None

	if data.invert:
		on_datetime, off_datetime = off_datetime, on_datetime

	return Event(
		hass,
		entity_id=state.entity_id,
		friendly_name=friendly_name(state),
		on_datetime=on_datetime,
		off_datetime=off_datetime,
	)


def ctag(event: CalendarEvent) -> str:
	"""Calculate the hash of a calendar event"""

	return sha256(str(event.as_dict()).encode('utf-8')).hexdigest()


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
