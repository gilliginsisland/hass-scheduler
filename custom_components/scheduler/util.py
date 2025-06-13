from typing import NamedTuple
from hashlib import sha256

from homeassistant.helpers import (
	area_registry,
	entity_registry,
)
from homeassistant.components.calendar import CalendarEvent
from homeassistant.core import HomeAssistant, State

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

	ar = area_registry.async_get(hass)
	er = entity_registry.async_get(hass)

	for area in ar.areas.values():
		area_name = area.name.strip().lower()
		if not entity_id_or_name.startswith(area_name):
			continue

		suffix = entity_id_or_name[len(area_name):].strip()
		for entity in er.entities.values():
			if entity.area_id != area.id:
				continue

			if (state := hass.states.get(entity.entity_id)) and friendly_name(state).lower() == suffix:
				return state

	for state in hass.states.async_all():
		if friendly_name(state) == entity_id_or_name:
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
