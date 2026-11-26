# Calendar Scheduler

Calendar Scheduler uses calendar event titles to control entities. An event can
name an entity ID, a friendly name, or an area-prefixed friendly name.

- A normal event enforces **on** for its duration, then **off** for the configured
  end-control period (five minutes by default).
- A title prefixed with `!` reverses those states.
- A title ending in `+` has no end-control period.
- Active events take priority over end control. When active events conflict, the
  later-starting event wins.

Commands are checked against the entity's reported state and retried while their
schedule is active. A successful calendar refresh replaces that calendar's plan;
if an event was removed, its active and end-control periods are dropped without
restoring the entity's previous state.

## Dashboard card

The integration includes a small timeline card. After installing this version,
restart Home Assistant and reload the browser so it loads the card module. Add a
manual card to a dashboard:

```yaml
type: custom:scheduler-card
title: Scheduler
```

By default, the card shows every loaded scheduler entry you can read. To show one
entry, add its config-entry ID (also returned by the WebSocket API):

```yaml
type: custom:scheduler-card
title: Shabbat schedule
entry_id: YOUR_CONFIG_ENTRY_ID
```

The module is served at `/scheduler/scheduler-card.js` and registered with the
frontend automatically. No separate JavaScript build or dashboard resource is
required. The card is also listed in the custom-card picker.

The card shows each remaining event window and end-control window, grouped by
start date, with the entity, requested state, calendar, start and end times, and:

- **Upcoming:** a future window; overlapping events may take priority when it starts.
- **Pending:** an active winning window whose requested state is not yet reported.
- **Confirmed:** an active winning window already reporting the requested state;
  the scheduler continues listening for changes while the window is active.
- **Overridden:** a currently active window that loses to another active window.
- **Entity not found:** the event's friendly name cannot currently be resolved.

Click an entity name to open Home Assistant's more-info dialog. Calendar
unavailability and read failures appear above the timeline. Failed reads retain
previously loaded events; successful empty reads clear them.

This is a view of the events already loaded by the integration, within its
configured preload period (24 hours by default), rather than a new calendar
fetch. Deletions and edits appear after the next successful calendar poll.
The displayed times use Home Assistant's configured time zone.

## Read-only WebSocket API

The original command name now returns the current plan instead of an empty list:

```json
{"id": 1, "type": "scheduler/tasks"}
```

For an initial snapshot followed by updates:

```json
{"id": 2, "type": "scheduler/subscribe"}
```

The result, or each subscription event, is a list of scheduler snapshots. Each
snapshot contains `entry_id`, `title`, `actions`, and `calendars`. Each action
includes the source calendar, target and resolved entity ID, name, start and end
as ISO timestamps, desired and current states, whether it is end control, and its
status. Calendar records include availability and the latest read error, if any.
Completed windows are omitted. Calendar and target entity read permissions are
respected.

Subscriptions update when calendar data, active entity state, schedule boundaries,
or entry availability change. Identical snapshots are not sent again. They do
not add polling or change how commands are enforced. Stop a subscription using
Home Assistant's standard `unsubscribe_events` command:

```json
{"id": 3, "type": "unsubscribe_events", "subscription": 2}
```
