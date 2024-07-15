from typing import NamedTuple
from hashlib import sha256

from homeassistant.components.calendar import CalendarEvent
from homeassistant.core import HomeAssistant

from .event import Event


class ParsedEventSummary(NamedTuple):
	entity_name_or_id: str
	invert: bool
	oneshot: bool


def parse_event_summary(entity_name_or_id: str) -> ParsedEventSummary:
	"""Parse the event name"""

	if entity_name_or_id[0] == '!':
		entity_name_or_id = entity_name_or_id[1:]
		invert = True
	else:
		invert = False

	if entity_name_or_id[-1] == '+':
		entity_name_or_id = entity_name_or_id[:-1]
		oneshot = True
	else:
		oneshot = False

	return ParsedEventSummary(
		entity_name_or_id, invert=invert, oneshot=oneshot
	)


def lookup_entity(hass: HomeAssistant, entity_name_or_id: str) -> tuple[str, str]:
	"""Find an entity by id or name"""

	return entity_name_or_id, entity_name_or_id


def parse_event(hass: HomeAssistant, event: CalendarEvent) -> Event:
	"""Parse a calendar event into a scheduler event"""

	data = parse_event_summary(event.summary)

	entity_id, display_name = lookup_entity(hass, data.entity_name_or_id)

	on_datetime = event.start_datetime_local
	off_datetime = event.end_datetime_local if not data.oneshot else None

	if data.invert:
		on_datetime, off_datetime = off_datetime, on_datetime

	return Event(
		hass,
		entity_id=entity_id,
		display_name=display_name,
		on_datetime=on_datetime,
		off_datetime=off_datetime,
	)


def ctag(event: CalendarEvent) -> str:
	"""Calculate the hash of a calendar event"""

	return sha256(str(event.as_dict()).encode('utf-8')).hexdigest()
