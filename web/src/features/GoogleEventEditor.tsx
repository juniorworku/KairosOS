import { useState } from "react";
import { DateTime } from "luxon";
import { Link } from "react-router-dom";
import type { AgendaItem } from "../api/agenda";
import type { CalendarList, GoogleEvent } from "../api/calendar";
import { googleEventPath } from "../api/calendar";
import { api } from "../api/client";
import { useData } from "../lib/hooks";
import { Modal } from "../components/ui/Modal";
import { Button } from "../components/ui/Button";
import { Field, Notice, SubmitForm } from "../components/ui/Forms";
import { Input } from "../components/primitives/input";
import { Textarea } from "../components/primitives/textarea";
import { NativeSelect } from "../components/primitives/native-select";
import { addDays } from "../lib/time";
import "./calendar-controls.css";
export function GoogleEventEditor({
  item,
  timezone,
  online,
  close,
  onChange,
}: {
  item: AgendaItem;
  timezone: string;
  online: boolean;
  close: () => void;
  onChange: () => Promise<void>;
}) {
  const calendarId = item.calendar_id || "";
  const left = DateTime.fromISO(item.start_at, { zone: timezone });
  const right = DateTime.fromISO(item.end_at, { zone: timezone });
  const display = item.all_day
    ? `${left.toLocaleString(DateTime.DATE_FULL)}${left.toISODate() === right.minus({ days: 1 }).toISODate() ? "" : " – " + right.minus({ days: 1 }).toLocaleString(DateTime.DATE_FULL)} · All day`
    : `${left.toLocaleString(DateTime.DATETIME_MED)} – ${right.toLocaleString(DateTime.DATETIME_MED)} (${timezone})`;
  const calendars = useData<CalendarList>("/calendar/calendars");
  const mayEdit =
    !!item.editable &&
    !!calendarId &&
    !!calendars.data?.write_enabled &&
    !!calendars.data.calendars.find(
      (calendar) => calendar.id === calendarId && calendar.can_write,
    );
  const event = useData<GoogleEvent>(
    googleEventPath(calendarId, item.source_id),
    mayEdit,
  );
  return (
    <Modal titleId="google-event-title" onClose={close}>
      <h2 id="google-event-title">
        {mayEdit ? "Edit Google event" : item.title}
      </h2>
      <Notice error={calendars.error || event.error} />
      {mayEdit && event.data ? (
        <GoogleEventForm
          key={event.data.etag}
          calendarId={calendarId}
          calendars={calendars.data!}
          timezone={timezone}
          online={online}
          initial={event.data}
          recurring={item.recurring}
          close={close}
          onChange={onChange}
        />
      ) : mayEdit ? (
        <p role="status">
          {event.error
            ? "The event could not be loaded. No changes can be saved."
            : "Loading Google event…"}
        </p>
      ) : (
        <>
          <p className="calendar-event-source">
            {item.calendar_name || "Google Calendar"} · Read-only
          </p>
          <p>{display}</p>
          {item.notes && <div className="agenda-notes">{item.notes}</div>}
          <p className="form-hint">
            Editing requires separate permission and a calendar you own. Shared
            calendars remain read-only.
          </p>
          <Button asChild>
            <Link to="/settings">Calendar settings</Link>
          </Button>
        </>
      )}
      <div className="modal-actions">
        {mayEdit && (
          <Button
            type="button"
            disabled={!online || event.isFetching}
            onClick={() => void event.refetch()}
          >
            Reload Google event
          </Button>
        )}
        <Button type="button" onClick={close}>
          Close
        </Button>
        <Button asChild variant="link">
          <a
            href="https://calendar.google.com"
            target="_blank"
            rel="noreferrer"
          >
            Open Google Calendar
          </a>
        </Button>
      </div>
    </Modal>
  );
}
export function GoogleEventForm({
  calendarId,
  calendars,
  timezone,
  initial,
  recurring,
  startAt,
  endAt,
  allDay: initialAllDay,
  online,
  close,
  onChange,
}: {
  calendarId: string;
  calendars: CalendarList;
  timezone: string;
  initial?: GoogleEvent;
  recurring?: boolean;
  startAt?: string;
  endAt?: string;
  allDay?: boolean;
  online: boolean;
  close: () => void;
  onChange: () => Promise<void>;
}) {
  const initialZone =
    initial?.timezone ||
    calendars.calendars.find((calendar) => calendar.id === calendarId)
      ?.timezone ||
    timezone;
  const base = DateTime.now()
    .setZone(initialZone)
    .startOf("hour")
    .plus({ hours: 1 });
  const [title, setTitle] = useState(initial?.title || "");
  const [notes, setNotes] = useState(initial?.notes || "");
  const [allDay, setAllDay] = useState(
    initial?.all_day ?? initialAllDay ?? false,
  );
  const [zone, setZone] = useState(initialZone);
  function format(value: string | undefined, day: boolean, fallback: DateTime) {
    const date = value
      ? DateTime.fromISO(value, { zone: initialZone }).setZone(initialZone)
      : fallback;
    return day ? date.toISODate() || "" : date.toFormat("yyyy-MM-dd'T'HH:mm");
  }
  const [start, setStart] = useState(
    format(initial?.start_at || startAt, allDay, base),
  );
  const [end, setEnd] = useState(
    format(
      initial?.end_at || endAt,
      allDay,
      base.plus(allDay ? { days: 1 } : { hours: 1 }),
    ),
  );
  const [clientId] = useState(() => crypto.randomUUID());
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [failure, setFailure] = useState<unknown>();
  const canWrite =
    calendars.write_enabled &&
    calendars.calendars.some(
      (calendar) => calendar.id === calendarId && calendar.can_write,
    );
  const isRecurring =
    recurring || initial?.recurring || !!initial?.recurring_event_id;
  return (
    <div className="calendar-event-form">
      <p className="calendar-event-source">
        {calendars.calendars.find((calendar) => calendar.id === calendarId)
          ?.name || calendarId}{" "}
        · Google Calendar
      </p>
      {isRecurring && (
        <p className="calendar-scope-note">
          This occurrence only. Other dates in the series stay unchanged. Edit
          the whole series in Google Calendar.
        </p>
      )}
      <p className="form-hint">
        Saving or deleting changes Google Calendar directly. Changes are checked
        against the loaded event version.
      </p>
      <Notice error={failure} />
      <SubmitForm
        onSubmit={async () => {
          if (!canWrite) throw new Error("This calendar is read-only.");
          const sameClock =
            initial && zone === initial.timezone && allDay === initial.all_day;
          const left = DateTime.fromISO(
            sameClock && start === format(initial.start_at, allDay, base)
              ? initial.start_at
              : start,
            { zone },
          );
          const right = DateTime.fromISO(
            sameClock && end === format(initial.end_at, allDay, base)
              ? initial.end_at
              : end,
            { zone },
          );
          const pattern = allDay ? "yyyy-MM-dd" : "yyyy-MM-dd'T'HH:mm";
          if (
            !left.isValid ||
            !right.isValid ||
            left.toFormat(pattern) !== start ||
            right.toFormat(pattern) !== end ||
            right.toMillis() <= left.toMillis()
          )
            throw new Error(
              "Choose valid start and end times in this time zone.",
            );
          if (initial && !initial.etag)
            throw new Error("Reload the event before saving.");
          const body = {
            calendar_id: calendarId,
            title,
            notes,
            start_at: left.toUTC().toISO(),
            end_at: right.toUTC().toISO(),
            timezone: zone,
            all_day: allDay,
            ...(initial
              ? { etag: initial.etag }
              : { client_event_id: clientId }),
          };
          await api(
            initial
              ? googleEventPath(calendarId, initial.source_id)
              : "/calendar/events",
            initial ? "PATCH" : "POST",
            body,
          );
          await onChange();
          close();
        }}
      >
        {(busy) => (
          <>
            <fieldset disabled={!online || !canWrite || busy || deleting}>
              <Field label="Title">
                <Input
                  required
                  autoFocus
                  maxLength={200}
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                />
              </Field>
              <Field label="Notes">
                <Textarea
                  rows={3}
                  maxLength={10000}
                  value={notes}
                  onChange={(event) => setNotes(event.target.value)}
                />
              </Field>
              <label className="checkbox">
                <input
                  type="checkbox"
                  checked={allDay}
                  onChange={(event) => {
                    const day = start.slice(0, 10);
                    setAllDay(event.target.checked);
                    setStart(event.target.checked ? day : day + "T09:00");
                    setEnd(
                      event.target.checked ? addDays(day, 1) : day + "T10:00",
                    );
                  }}
                />
                All day
              </label>
              <div className="form-grid">
                <Field label="Start">
                  <Input
                    type={allDay ? "date" : "datetime-local"}
                    required
                    value={start}
                    onChange={(event) => setStart(event.target.value)}
                  />
                </Field>
                <Field label={allDay ? "End date (exclusive)" : "End"}>
                  <Input
                    type={allDay ? "date" : "datetime-local"}
                    required
                    value={end}
                    min={allDay && start ? addDays(start, 1) : start}
                    onChange={(event) => setEnd(event.target.value)}
                  />
                </Field>
              </div>
              <Field label="Time zone">
                <Input
                  required
                  value={zone}
                  onChange={(event) => setZone(event.target.value)}
                />
              </Field>
              {allDay && (
                <p className="form-hint">
                  The end date is the first day after the event.
                </p>
              )}
            </fieldset>
            <div className="modal-actions">
              {initial && (
                <Button
                  type="button"
                  variant="destructive"
                  disabled={!online || !canWrite || busy || deleting}
                  onClick={() => setConfirmDelete(true)}
                >
                  Delete Google {isRecurring ? "occurrence" : "event"}
                </Button>
              )}
              <Button type="button" onClick={close}>
                Cancel
              </Button>
              <Button disabled={!online || !canWrite || busy || deleting}>
                {busy
                  ? "Saving…"
                  : "Save Google " + (isRecurring ? "occurrence" : "event")}
              </Button>
            </div>
          </>
        )}
      </SubmitForm>
      {confirmDelete && (
        <section
          className="calendar-delete-confirm"
          aria-label="Confirm Google deletion"
        >
          <p>
            {isRecurring
              ? "Delete only this occurrence from Google Calendar?"
              : "Delete this event from Google Calendar?"}{" "}
            This cannot be undone here.
          </p>
          <div className="button-row">
            <Button
              type="button"
              disabled={deleting}
              onClick={() => setConfirmDelete(false)}
            >
              Keep event
            </Button>
            <Button
              type="button"
              variant="destructive"
              disabled={!online || deleting || !initial?.etag}
              onClick={() => {
                if (!initial?.etag) return;
                setDeleting(true);
                setFailure(undefined);
                void api(
                  googleEventPath(calendarId, initial.source_id) +
                    "&etag=" +
                    encodeURIComponent(initial.etag),
                  "DELETE",
                )
                  .then(onChange)
                  .then(close)
                  .catch(setFailure)
                  .finally(() => setDeleting(false));
              }}
            >
              {deleting ? "Deleting…" : "Confirm delete"}
            </Button>
          </div>
        </section>
      )}
    </div>
  );
}
export function GoogleCalendarPicker({
  value,
  onChange,
  calendars,
  disabled,
}: {
  value: string;
  onChange: (value: string) => void;
  calendars: CalendarList;
  disabled?: boolean;
}) {
  return (
    <Field label="Calendar">
      <NativeSelect
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="">Kairos · Local event</option>
        {calendars.calendars
          .filter((calendar) => calendar.selected && calendar.can_write)
          .map((calendar) => (
            <option key={calendar.id} value={calendar.id}>
              {calendar.name} · Google
            </option>
          ))}
      </NativeSelect>
    </Field>
  );
}
