/**
 * @typedef {{title?: string, entry_id?: string}} CardConfig
 * @typedef {"upcoming" | "pending" | "confirmed" | "overridden" | "unresolved"} ActionStatus
 * @typedef {{calendar_id: string, target: string, entity_id: string | null,
 * name: string, start: string, end: string, state: "on" | "off",
 * current_state: string | null, end_control: boolean, status: ActionStatus}} ScheduledAction
 * @typedef {{entity_id: string, available: boolean, error: string | null}} CalendarStatus
 * @typedef {{entry_id: string, title: string, actions: ScheduledAction[],
 * calendars: CalendarStatus[]}} SchedulerSnapshot
 * @typedef {() => Promise<void>} Unsubscribe
 * @typedef {{subscribeMessage: (callback: (data: SchedulerSnapshot[]) => void,
 * message: {type: string}) => Promise<Unsubscribe>}} Connection
 * @typedef {{connection: Connection, locale: {language: string},
 * config: {time_zone: string}, states: Record<string,
 * {attributes: {friendly_name?: string}}>}} HomeAssistant
 */

class SchedulerCard extends HTMLElement {
    /** @type {CardConfig} */
    _config = {};
    /** @type {HomeAssistant | undefined} */
    _hass;
    /** @type {SchedulerSnapshot[] | undefined} */
    _snapshots;
    /** @type {Promise<Unsubscribe> | undefined} */
    _subscription;
    /** @type {string | undefined} */
    _error;

    constructor() {
        super();
        const root = this.attachShadow({mode: "open"});
        // Only this fixed template uses HTML. Calendar and entity text uses textContent.
        root.innerHTML = `
            <style>
                :host { display: block; }
                ha-card { overflow: hidden; }
                header { padding: 20px 16px 12px; }
                h2 { margin: 0; font-size: var(--ha-card-header-font-size, 24px); font-weight: 400; }
                .summary, .meta, .status, time { color: var(--secondary-text-color); font-size: 12px; }
                .summary { margin-top: 4px; }
                .content { max-height: 480px; overflow: auto; padding: 0 16px 12px; }
                h3 { margin: 16px 0 12px; font-size: 14px; font-weight: 500; }
                ol { list-style: none; padding: 0; margin: 0; }
                li { display: grid; grid-template-columns: 70px 1fr; gap: 16px; }
                time { padding-top: 2px; line-height: 20px; }
                .event { position: relative; border-inline-start: 2px solid var(--divider-color); padding: 0 0 20px 16px; min-width: 0; }
                .event::before { content: ""; position: absolute; inset-inline-start: -5px; top: 6px; width: 8px; height: 8px; border-radius: 50%; background: var(--secondary-text-color); }
                .confirmed .event::before { background: var(--success-color, #43a047); }
                .pending .event::before, .unresolved .event::before { background: var(--warning-color, #ffa600); }
                .overridden .event { opacity: .65; }
                .line { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
                button { font: inherit; color: var(--primary-color); background: none; border: 0; cursor: pointer; padding: 0; text-align: start; }
                .entity { color: var(--primary-text-color); font-weight: 500; overflow-wrap: anywhere; }
                button:focus-visible { outline: 2px solid var(--primary-color); outline-offset: 3px; }
                .state { font-size: 12px; font-weight: 600; color: var(--primary-color); }
                .meta, .status { margin-top: 4px; overflow-wrap: anywhere; }
                .notice { padding: 12px 0; color: var(--secondary-text-color); }
                .warning { color: var(--warning-color, #ffa600); }
            </style>
            <ha-card>
                <header><h2></h2><div class="summary"></div></header>
                <div class="content" aria-live="polite"></div>
            </ha-card>`;
        this._heading = /** @type {HTMLElement} */ (root.querySelector("h2"));
        this._summary = /** @type {HTMLElement} */ (root.querySelector(".summary"));
        this._content = /** @type {HTMLElement} */ (root.querySelector(".content"));
    }

    /** @param {CardConfig} config */
    setConfig(config) {
        if (config.title !== undefined && typeof config.title !== "string") {
            throw new Error("title must be a string");
        }
        if (config.entry_id !== undefined && typeof config.entry_id !== "string") {
            throw new Error("entry_id must be a string");
        }
        this._config = config;
        this._render();
    }

    /** @param {HomeAssistant} hass */
    set hass(hass) {
        if (this._hass?.connection !== hass.connection) this._disconnect();
        this._hass = hass;
        this._connect();
    }

    connectedCallback() {
        this._connect();
    }

    disconnectedCallback() {
        this._disconnect();
    }

    _connect() {
        if (!this.isConnected || !this._hass || this._subscription) return;
        this._error = undefined;
        this._snapshots = undefined;
        const subscription = this._hass.connection.subscribeMessage((data) => {
            if (this._subscription !== subscription) return;
            this._snapshots = data;
            this._render();
        }, {type: "scheduler/subscribe"});
        this._subscription = subscription;
        subscription.catch((error) => {
            if (this._subscription !== subscription) return;
            this._subscription = undefined;
            this._error = error.message || "Could not load scheduler actions";
            this._render();
        });
        this._render();
    }

    _disconnect() {
        const subscription = this._subscription;
        this._subscription = undefined;
        subscription?.then((unsubscribe) => unsubscribe()).catch(() => {});
    }

    _render() {
        this._heading.textContent = this._config.title ?? "Scheduler";
        this._content.replaceChildren();
        this._summary.textContent = "";
        if (this._error) {
            this._notice(this._error, true);
            const retry = document.createElement("button");
            retry.textContent = "Retry";
            retry.onclick = () => this._connect();
            this._content.append(retry);
            return;
        }
        if (!this._snapshots || !this._hass) {
            this._notice("Loading scheduler actions…");
            return;
        }
        const snapshots = this._snapshots.filter((entry) =>
            !this._config.entry_id || entry.entry_id === this._config.entry_id);
        const actions = snapshots.flatMap((entry) => entry.actions)
            .sort((a, b) => a.start.localeCompare(b.start) || a.name.localeCompare(b.name));
        const active = actions.filter((action) => ["pending", "confirmed"].includes(action.status)).length;
        this._summary.textContent = `${active} active · ${actions.length - active} other planned windows`;
        for (const calendar of snapshots.flatMap((entry) => entry.calendars)) {
            if (!calendar.available || calendar.error) {
                const name = this._name(calendar.entity_id);
                this._notice(`${name}: ${calendar.error || "waiting for calendar to become available"}. Previously loaded events are retained.`, true);
            }
        }
        if (!actions.length) {
            this._notice(snapshots.length
                ? "No active or upcoming actions in the loaded calendar data."
                : "No loaded scheduler entries found.");
            return;
        }
        const locale = this._hass.locale.language;
        const timeZone = this._hass.config.time_zone;
        const dayFormat = new Intl.DateTimeFormat(locale, {dateStyle: "full", timeZone});
        const timeFormat = new Intl.DateTimeFormat(locale, {hour: "numeric", minute: "2-digit", timeZone});
        let day = "";
        let list = document.createElement("ol");
        for (const action of actions) {
            const start = new Date(action.start);
            const end = new Date(action.end);
            const nextDay = dayFormat.format(start);
            if (day !== nextDay) {
                day = nextDay;
                const heading = document.createElement("h3");
                heading.textContent = day;
                list = document.createElement("ol");
                this._content.append(heading, list);
            }
            const row = document.createElement("li");
            row.className = action.status;
            const time = document.createElement("time");
            time.dateTime = action.start;
            time.textContent = `${timeFormat.format(start)} – ${timeFormat.format(end)}`;
            time.title = `${dayFormat.format(start)} ${timeFormat.format(start)} – ${dayFormat.format(end)} ${timeFormat.format(end)}`;
            const details = document.createElement("div");
            details.className = "event";
            const line = document.createElement("div");
            line.className = "line";
            const entity = document.createElement(action.entity_id ? "button" : "span");
            entity.className = "entity";
            entity.textContent = action.name;
            if (action.entity_id) entity.onclick = () => this.dispatchEvent(new CustomEvent("hass-more-info", {
                detail: {entityId: action.entity_id}, bubbles: true, composed: true,
            }));
            const state = document.createElement("span");
            state.className = "state";
            state.textContent = action.state.toUpperCase();
            const meta = document.createElement("div");
            meta.className = "meta";
            meta.textContent = `${this._name(action.calendar_id)} · ${action.end_control ? "End control" : "Calendar event"}`;
            const status = document.createElement("div");
            status.className = "status";
            status.textContent = {
                upcoming: "Upcoming · subject to overlapping events",
                pending: `Pending · currently ${action.current_state ?? "unavailable"}`,
                confirmed: "Confirmed · enforcing",
                overridden: "Overridden by another active event",
                unresolved: "Entity not found",
            }[action.status];
            line.append(entity, state);
            details.append(line, meta, status);
            row.append(time, details);
            list.append(row);
        }
    }

    /** @param {string} entityId */
    _name(entityId) {
        return this._hass?.states[entityId]?.attributes.friendly_name || entityId;
    }

    /** @param {string} text @param {boolean} [warning] */
    _notice(text, warning = false) {
        const notice = document.createElement("div");
        notice.className = warning ? "notice warning" : "notice";
        notice.textContent = text;
        this._content.append(notice);
    }

    getCardSize() {
        return 6;
    }

    getGridOptions() {
        return {columns: 12, rows: "auto", min_columns: 6};
    }

    static getStubConfig() {
        return {type: "custom:scheduler-card"};
    }
}

if (!customElements.get("scheduler-card")) {
    customElements.define("scheduler-card", SchedulerCard);
    const cardWindow = /** @type {Window & {customCards?: {type: string, name: string, description: string}[]}} */ (window);
    (cardWindow.customCards ??= []).push({
        type: "scheduler-card",
        name: "Scheduler",
        description: "Active and upcoming calendar actions, including end control.",
    });
}
