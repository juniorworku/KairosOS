import { Input } from "../components/primitives/input";
import { Textarea } from "../components/primitives/textarea";
import { NativeSelect } from "../components/primitives/native-select";
import { useState } from "react";
import { DateTime } from "luxon";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type {
  AgendaItem,
  LocalEvent,
  NotedBlock,
  Recurrence,
  Task,
} from "../api/agenda";
import type { Goal } from "../api/types";
import { copy as c, agendaCopy as a } from "../copy/en";
import { Button } from "../components/ui/Button";
import { Empty, Field, Notice, SubmitForm } from "../components/ui/Forms";
import { Modal } from "../components/ui/Modal";
import { useData } from "../lib/hooks";
import { addDays } from "../lib/time";

export type AgendaEditorSelection =
  | {
      kind: "event";
      item?: AgendaItem;
      task?: Task;
      start?: string;
      end?: string;
      allDay?: boolean;
    }
  | { kind: "block"; block?: NotedBlock; start?: string; end?: string };
interface Props {
  selection: AgendaEditorSelection;
  timezone: string;
  goals: Goal[];
  tasks: Task[];
  online: boolean;
  close: () => void;
  onChange: () => Promise<void>;
  onFocus: (block: NotedBlock) => Promise<void>;
}
export function AgendaEditor(props: Props) {
  return props.selection.kind === "block" ? (
    <BlockEditor {...props} selection={props.selection} />
  ) : props.selection.item?.source === "google" ||
    props.selection.item?.editable === false ? (
    <ReadOnlyEvent
      item={props.selection.item}
      timezone={props.timezone}
      close={props.close}
    />
  ) : (
    <EventEditor {...props} selection={props.selection} />
  );
}
function ReadOnlyEvent({
  item,
  timezone,
  close,
}: {
  item: AgendaItem;
  timezone: string;
  close: () => void;
}) {
  const start = DateTime.fromISO(item.start_at, { zone: timezone });
  const end = DateTime.fromISO(item.end_at, { zone: timezone });
  const display = item.all_day
    ? start.toISODate() === end.minus({ days: 1 }).toISODate()
      ? start.toLocaleString(DateTime.DATE_FULL)
      : `${start.toLocaleString(DateTime.DATE_FULL)} – ${end.minus({ days: 1 }).toLocaleString(DateTime.DATE_FULL)}`
    : `${start.toLocaleString(DateTime.DATETIME_MED)} – ${end.toLocaleString(DateTime.DATETIME_MED)} (${timezone})`;
  return (
    <Modal titleId="event-title" onClose={close}>
      <h2 id="event-title">{item.title}</h2>
      <span className="status-label">
        {a.google} · {a.readOnly}
      </span>
      <p>{display}</p>
      {item.notes && <div className="agenda-notes">{item.notes}</div>}
      <p className="form-hint">{a.googleHint}</p>
      <div className="modal-actions">
        <Button type="button" onClick={close}>
          {c.close}
        </Button>
        <a
          className="button"
          href="https://calendar.google.com"
          target="_blank"
          rel="noreferrer"
        >
          {a.openGoogle}
        </a>
      </div>
    </Modal>
  );
}
function EventEditor(
  props: Props & {
    selection: Extract<AgendaEditorSelection, { kind: "event" }>;
  },
) {
  const { selection, close } = props;
  const item = selection.item;
  const series = useData<LocalEvent>(`/events/${item?.source_id}`, !!item);
  const [scope, setScope] = useState<"occurrence" | "series">(
    item?.recurring && item.occurrence_date ? "occurrence" : "series",
  );
  const initial: LocalEvent | undefined =
    scope === "occurrence" && item
      ? {
          id: item.source_id,
          title: item.title,
          notes: item.notes,
          start_at: item.start_at,
          end_at: item.end_at,
          timezone: item.timezone,
          all_day: item.all_day,
          task_id: item.task_id || null,
          recurrence: null,
        }
      : series.data;
  return (
    <Modal titleId="event-title" onClose={close}>
      <h2 id="event-title">{item ? a.editEvent : a.newEvent}</h2>
      {item?.recurring && item.occurrence_date && (
        <div
          className="segmented agenda-edit-scope"
          role="group"
          aria-label={a.recurring}
        >
          <Button
            type="button"
            aria-pressed={scope === "occurrence"}
            onClick={() => setScope("occurrence")}
          >
            {a.thisOccurrence}
          </Button>
          <Button
            type="button"
            aria-pressed={scope === "series"}
            onClick={() => setScope("series")}
          >
            {a.wholeSeries}
          </Button>
        </div>
      )}
      <Notice error={series.error} />
      {item && scope === "series" && !series.data ? (
        <p role="status">{series.error ? c.requestFailed : c.loading}</p>
      ) : (
        <EventForm
          key={`${scope}-${item?.id || "new"}`}
          {...props}
          initial={initial}
          occurrence={scope === "occurrence"}
          onSave={async (body) => {
            const path = item
              ? scope === "occurrence"
                ? `/events/${item.source_id}/occurrences/${item.occurrence_date}`
                : `/events/${item.source_id}`
              : "/events";
            await api(path, item ? "PATCH" : "POST", body);
            await props.onChange();
            close();
          }}
          onDelete={
            item
              ? async () => {
                  await api(
                    scope === "occurrence"
                      ? `/events/${item.source_id}/occurrences/${item.occurrence_date}`
                      : `/events/${item.source_id}`,
                    "DELETE",
                  );
                  await props.onChange();
                  close();
                }
              : undefined
          }
        />
      )}
    </Modal>
  );
}
function wall(
  value: string | undefined,
  zone: string,
  allDay: boolean,
  fallback: DateTime,
): string {
  const parsed = value
    ? DateTime.fromISO(value, { zone }).setZone(zone)
    : fallback;
  return allDay
    ? parsed.toISODate() || ""
    : parsed.toFormat("yyyy-MM-dd'T'HH:mm");
}
function EventForm({
  selection,
  timezone,
  tasks,
  online,
  close,
  initial,
  occurrence,
  onSave,
  onDelete,
}: Props & {
  selection: Extract<AgendaEditorSelection, { kind: "event" }>;
  initial?: LocalEvent;
  occurrence: boolean;
  onSave: (body: unknown) => Promise<void>;
  onDelete?: () => Promise<void>;
}) {
  const zone = initial?.timezone || timezone;
  const base = DateTime.now().setZone(zone).startOf("hour").plus({ hours: 1 });
  const [title, setTitle] = useState(
    initial?.title || selection.task?.title || "",
  );
  const [notes, setNotes] = useState(
    initial?.notes || selection.task?.notes || "",
  );
  const [allDay, setAllDay] = useState(
    initial?.all_day ?? selection.allDay ?? false,
  );
  const [tz, setTz] = useState(zone);
  const [start, setStart] = useState(
    wall(initial?.start_at || selection.start, zone, allDay, base),
  );
  const [end, setEnd] = useState(
    wall(
      initial?.end_at || selection.end,
      zone,
      allDay,
      allDay
        ? base.plus({ days: 1 })
        : base.plus({ minutes: selection.task?.estimated_minutes || 60 }),
    ),
  );
  const [taskId, setTaskId] = useState(
    initial?.task_id || selection.task?.id || "",
  );
  const [repeats, setRepeats] = useState(!!initial?.recurrence);
  const [frequency, setFrequency] = useState<Recurrence["frequency"]>(
    initial?.recurrence?.frequency || "weekly",
  );
  const [interval, setInterval] = useState(initial?.recurrence?.interval || 1);
  const [weekdays, setWeekdays] = useState<number[]>(
    initial?.recurrence?.weekdays.length
      ? initial.recurrence.weekdays
      : [DateTime.fromISO(start, { zone }).weekday - 1],
  );
  const [endMode, setEndMode] = useState(
    initial?.recurrence?.until ? "date" : "count",
  );
  const [until, setUntil] = useState(initial?.recurrence?.until || "");
  const [count, setCount] = useState(initial?.recurrence?.count || 52);
  const [failure, setFailure] = useState<unknown>();
  const [deleting, setDeleting] = useState(false);
  async function remove() {
    if (
      !onDelete ||
      !window.confirm(
        occurrence
          ? a.confirmOccurrenceDelete
          : initial?.recurrence
            ? a.confirmSeriesDelete
            : a.confirmEventDelete,
      )
    )
      return;
    setDeleting(true);
    try {
      await onDelete();
    } catch (error) {
      setFailure(error);
    } finally {
      setDeleting(false);
    }
  }
  function toggleAllDay(value: boolean) {
    const day = start.slice(0, 10);
    setAllDay(value);
    setStart(value ? day : `${day}T09:00`);
    setEnd(value ? addDays(day, 1) : `${day}T10:00`);
  }
  return (
    <>
      <Notice error={failure} />
      <SubmitForm
        onSubmit={async () => {
          const sameClock =
            initial && tz === initial.timezone && allDay === initial.all_day;
          const left = DateTime.fromISO(
            sameClock && start === wall(initial.start_at, tz, allDay, base)
              ? initial.start_at
              : start,
            { zone: tz },
          );
          const right = DateTime.fromISO(
            sameClock && end === wall(initial.end_at, tz, allDay, base)
              ? initial.end_at
              : end,
            { zone: tz },
          );
          if (
            !left.isValid ||
            !right.isValid ||
            right.toMillis() <= left.toMillis()
          )
            throw new Error(a.invalidDates);
          const recurrence: Recurrence | null = repeats
            ? {
                frequency,
                interval,
                weekdays: frequency === "weekly" ? weekdays : [],
                until: endMode === "date" ? until : null,
                count: endMode === "count" ? count : null,
              }
            : null;
          await onSave({
            title,
            notes,
            start_at: left.toUTC().toISO(),
            end_at: right.toUTC().toISO(),
            timezone: tz,
            all_day: allDay,
            task_id: taskId || null,
            ...(!occurrence ? { recurrence } : {}),
          });
        }}
      >
        {(busy) => (
          <>
            <fieldset disabled={!online || busy || deleting}>
              <Field label={a.title}>
                <Input
                  autoFocus
                  required
                  maxLength={200}
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                />
              </Field>
              <Field label={a.notes}>
                <Textarea
                  rows={3}
                  maxLength={10000}
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                />
              </Field>
              <label className="checkbox">
                <input
                  type="checkbox"
                  checked={allDay}
                  onChange={(e) => toggleAllDay(e.target.checked)}
                />
                {a.allDay}
              </label>
              <div className="form-grid">
                <Field label={c.plan.start}>
                  <Input
                    type={allDay ? "date" : "datetime-local"}
                    required
                    value={start}
                    onChange={(e) => {
                      setStart(e.target.value);
                      if (frequency === "weekly") {
                        const day =
                          DateTime.fromISO(e.target.value, { zone: tz })
                            .weekday - 1;
                        if (Number.isFinite(day))
                          setWeekdays((days) =>
                            [...new Set([...days, day])].sort(),
                          );
                      }
                    }}
                  />
                </Field>
                <Field label={allDay ? a.endDate : c.plan.end}>
                  <Input
                    type={allDay ? "date" : "datetime-local"}
                    required
                    min={allDay && start ? addDays(start, 1) : start}
                    value={end}
                    onChange={(e) => setEnd(e.target.value)}
                  />
                </Field>
              </div>
              {allDay && <p className="form-hint">{a.allDayHint}</p>}
              <div className="form-grid">
                <Field label={a.timezone}>
                  <Input
                    required
                    value={tz}
                    onChange={(e) => setTz(e.target.value)}
                  />
                </Field>
                <Field label={a.linkedTask}>
                  <NativeSelect
                    value={taskId}
                    onChange={(e) => setTaskId(e.target.value)}
                  >
                    <option value="">{a.noTask}</option>
                    {tasks.map((task) => (
                      <option key={task.id} value={task.id}>
                        {task.title}
                      </option>
                    ))}
                  </NativeSelect>
                </Field>
              </div>
              {!occurrence && (
                <>
                  <label className="checkbox">
                    <input
                      type="checkbox"
                      checked={repeats}
                      onChange={(e) => setRepeats(e.target.checked)}
                    />
                    {a.repeats}
                  </label>
                  {repeats && (
                    <div className="agenda-recurrence">
                      <div className="form-grid">
                        <Field label={a.frequency}>
                          <NativeSelect
                            value={frequency}
                            onChange={(e) =>
                              setFrequency(
                                e.target.value as Recurrence["frequency"],
                              )
                            }
                          >
                            <option value="daily">{a.daily}</option>
                            <option value="weekly">{a.weekly}</option>
                            <option value="monthly">Monthly</option>
                            <option value="yearly">Yearly</option>
                          </NativeSelect>
                        </Field>
                        <Field label={a.interval}>
                          <Input
                            required
                            type="number"
                            min={1}
                            max={52}
                            value={interval}
                            onChange={(e) =>
                              setInterval(Number(e.target.value))
                            }
                          />
                        </Field>
                      </div>
                      {["monthly", "yearly"].includes(frequency) && (
                        <p className="form-hint">
                          Repeats on the same date. Months or years without that
                          date are skipped.
                        </p>
                      )}
                      {frequency === "weekly" && (
                        <fieldset className="agenda-weekdays">
                          <legend>{a.weekdays}</legend>
                          {c.settings.days.map((day, index) => (
                            <label key={day} className="checkbox">
                              <input
                                type="checkbox"
                                checked={weekdays.includes(index)}
                                onChange={(e) =>
                                  setWeekdays((days) =>
                                    e.target.checked
                                      ? [...new Set([...days, index])].sort()
                                      : days.filter((d) => d !== index),
                                  )
                                }
                              />
                              {day}
                            </label>
                          ))}
                        </fieldset>
                      )}
                      <div className="form-grid">
                        <Field label={a.recurrenceEnd}>
                          <NativeSelect
                            value={endMode}
                            onChange={(e) => setEndMode(e.target.value)}
                          >
                            <option value="count">{a.afterCount}</option>
                            <option value="date">{a.onDate}</option>
                          </NativeSelect>
                        </Field>
                        {endMode === "count" ? (
                          <Field label={a.count}>
                            <Input
                              required
                              type="number"
                              min={1}
                              max={500}
                              value={count}
                              onChange={(e) => setCount(Number(e.target.value))}
                            />
                          </Field>
                        ) : (
                          <Field label={a.until}>
                            <Input
                              required
                              type="date"
                              min={start.slice(0, 10)}
                              value={until}
                              onChange={(e) => setUntil(e.target.value)}
                            />
                          </Field>
                        )}
                      </div>
                    </div>
                  )}
                </>
              )}
            </fieldset>
            <div className="modal-actions">
              {onDelete && (
                <Button
                  type="button"
                  className="danger"
                  disabled={!online || busy || deleting}
                  onClick={() => void remove()}
                >
                  {occurrence
                    ? a.deleteOccurrence
                    : initial?.recurrence
                      ? a.deleteSeries
                      : a.deleteEvent}
                </Button>
              )}
              <Button type="button" onClick={close}>
                {c.cancel}
              </Button>
              <Button
                className="primary"
                disabled={!online || busy || deleting}
              >
                {busy ? c.saving : a.saveEvent}
              </Button>
            </div>
          </>
        )}
      </SubmitForm>
    </>
  );
}
function BlockEditor({
  selection,
  goals,
  timezone,
  online,
  close,
  onChange,
  onFocus,
}: Props & { selection: Extract<AgendaEditorSelection, { kind: "block" }> }) {
  const block = selection.block;
  const activeGoals = goals.filter((goal) => goal.status === "active");
  const [goalId, setGoalId] = useState(block?.goal_id || "");
  const goal = activeGoals.find((item) => item.id === goalId);
  const [actionId, setActionId] = useState(block?.action_id || "");
  const fallback = DateTime.now()
    .setZone(timezone)
    .startOf("hour")
    .plus({ hours: 1 });
  const [start, setStart] = useState(
    wall(block?.start_at || selection.start, timezone, false, fallback),
  );
  const [end, setEnd] = useState(
    wall(
      block?.end_at || selection.end,
      timezone,
      false,
      fallback.plus({ hours: 1 }),
    ),
  );
  const [notes, setNotes] = useState(block?.notes || "");
  const [error, setError] = useState<unknown>();
  const [changing, setChanging] = useState(false);
  const linked = !!block?.google_event_id || block?.status === "published";
  const canMove = !linked && block?.status !== "completed";
  const timesChanged =
    !!block &&
    (start !== wall(block.start_at, timezone, false, fallback) ||
      end !== wall(block.end_at, timezone, false, fallback));
  async function action(path: string, body: unknown, method = "POST") {
    setChanging(true);
    setError(undefined);
    try {
      await api(path, method, body);
      await onChange();
      close();
    } catch (error) {
      setError(error);
    } finally {
      setChanging(false);
    }
  }
  return (
    <Modal titleId="block-title" onClose={close}>
      <h2 id="block-title">{block?.title || a.scheduleAction}</h2>
      <Notice error={error} />
      {linked && <p className="form-hint">{a.publishedHint}</p>}
      {!block && !activeGoals.length ? (
        <Empty title={a.noGoals}>
          <Link className="button primary" to="/goals/new" onClick={close}>
            {c.goals.new}
          </Link>
        </Empty>
      ) : (
        <SubmitForm
          onSubmit={async () => {
            const left = DateTime.fromISO(start, { zone: timezone });
            const right = DateTime.fromISO(end, { zone: timezone });
            if (
              !left.isValid ||
              !right.isValid ||
              right.toMillis() <= left.toMillis()
            )
              throw new Error(a.invalidDates);
            if (!block) {
              await api("/blocks", "POST", {
                goal_id: goalId,
                action_id: actionId,
                start_at: left.toUTC().toISO(),
                end_at: right.toUTC().toISO(),
                notes,
              });
            } else {
              if (notes !== (block.notes || ""))
                await api(`/blocks/${block.id}`, "PATCH", { notes });
              if (
                start !== wall(block.start_at, timezone, false, fallback) ||
                end !== wall(block.end_at, timezone, false, fallback)
              ) {
                if (block.status === "proposed")
                  await api(`/blocks/${block.id}`, "PATCH", {
                    start_at: left.toUTC().toISO(),
                    end_at: right.toUTC().toISO(),
                  });
                else
                  await api("/plan/changes", "POST", {
                    block_id: block.id,
                    operation: "move",
                    start_at: left.toUTC().toISO(),
                    end_at: right.toUTC().toISO(),
                  });
              }
            }
            await onChange();
            close();
          }}
        >
          {(busy) => (
            <>
              {!block && (
                <div className="form-grid">
                  <Field label={a.chooseGoal}>
                    <NativeSelect
                      required
                      value={goalId}
                      onChange={(e) => {
                        setGoalId(e.target.value);
                        setActionId("");
                      }}
                    >
                      <option value="">{a.chooseGoal}</option>
                      {activeGoals.map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.title}
                        </option>
                      ))}
                    </NativeSelect>
                  </Field>
                  <Field label={a.chooseAction}>
                    <NativeSelect
                      required
                      value={actionId}
                      onChange={(e) => setActionId(e.target.value)}
                    >
                      <option value="">{a.chooseAction}</option>
                      {goal?.actions.map((item) => (
                        <option value={item.id} key={item.id}>
                          {item.title}
                        </option>
                      ))}
                    </NativeSelect>
                  </Field>
                </div>
              )}
              <fieldset disabled={!online || changing || (!!block && !canMove)}>
                <div className="form-grid">
                  <Field label={c.plan.start}>
                    <Input
                      required
                      type="datetime-local"
                      value={start}
                      onChange={(e) => setStart(e.target.value)}
                    />
                  </Field>
                  <Field label={c.plan.end}>
                    <Input
                      required
                      type="datetime-local"
                      min={start}
                      value={end}
                      onChange={(e) => setEnd(e.target.value)}
                    />
                  </Field>
                </div>
              </fieldset>
              <Field label={a.notes}>
                <Textarea
                  rows={4}
                  maxLength={10000}
                  disabled={!online}
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                />
              </Field>
              {block && (
                <>
                  <span className={`status-label status-${block.status}`}>
                    {c.plan[block.status as keyof typeof c.plan] ||
                      block.status}
                  </span>
                  <p className="form-hint">{block.reason}</p>
                </>
              )}
              <div className="modal-actions">
                <Button type="button" onClick={close}>
                  {c.cancel}
                </Button>
                <Button
                  className="primary"
                  disabled={!online || busy || changing}
                >
                  {busy
                    ? c.saving
                    : !block
                      ? a.scheduleAction
                      : block.status === "proposed"
                        ? c.save
                        : canMove && timesChanged
                          ? a.proposeMove
                          : a.saveNotes}
                </Button>
              </div>
              {block && (
                <div className="agenda-block-controls">
                  {block.status === "proposed" && (
                    <Button
                      type="button"
                      disabled={!online || busy || changing}
                      onClick={() =>
                        void action("/plan/accept", { block_ids: [block.id] })
                      }
                    >
                      {c.plan.acceptOne}
                    </Button>
                  )}
                  {["accepted", "published"].includes(block.status) && (
                    <Button
                      type="button"
                      disabled={!online || busy || changing}
                      onClick={() => {
                        setChanging(true);
                        void onFocus(block)
                          .catch(setError)
                          .finally(() => setChanging(false));
                      }}
                    >
                      {c.today.start}
                    </Button>
                  )}
                  {!linked &&
                    !["completed", "cancelled"].includes(block.status) && (
                      <Button
                        type="button"
                        className="danger"
                        disabled={!online || busy || changing}
                        onClick={() =>
                          void (block.status === "proposed"
                            ? action(`/blocks/${block.id}`, undefined, "DELETE")
                            : action("/plan/changes", {
                                block_id: block.id,
                                operation: "remove",
                              }))
                        }
                      >
                        {block.status === "proposed"
                          ? c.plan.discard
                          : a.proposeRemoval}
                      </Button>
                    )}
                </div>
              )}
            </>
          )}
        </SubmitForm>
      )}
    </Modal>
  );
}
