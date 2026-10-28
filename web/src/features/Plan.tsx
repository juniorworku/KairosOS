import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import FullCalendar from "@fullcalendar/react";
import timeGridPlugin from "@fullcalendar/timegrid";
import interactionPlugin from "@fullcalendar/interaction";
import luxonPlugin from "@fullcalendar/luxon3";
import { DateTime } from "luxon";
import { ChevronLeft, ChevronRight, Plus, X } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { copy as c, agendaCopy as a } from "../copy/en";
import { useAuth } from "../lib/auth";
import { useData, useOnline } from "../lib/hooks";
import { api } from "../api/client";
import type { Busy, Goal } from "../api/types";
import type {
  AgendaItem,
  DraftOutcome,
  NotedBlock,
  PlanChange,
  Task,
} from "../api/agenda";
import { addDays, clock, dateKey, weekStart } from "../lib/time";
import { Button } from "../components/ui/Button";
import { Empty, Field, Notice, SubmitForm } from "../components/ui/Forms";
import { AgendaEditor, type AgendaEditorSelection } from "./AgendaEditor";
import { AgendaTasks } from "./AgendaTasks";
import { AgendaChanges } from "./AgendaChanges";
import "./agenda.css";

export interface CalendarStatus {
  configured: boolean;
  connected: boolean;
  status: string;
  can_publish: boolean;
  last_synced_at: string | null;
  details_enabled?: boolean;
  can_read_events?: boolean;
  details_cached_from?: string | null;
  details_cached_to?: string | null;
  details_error?: string | null;
}
export function Plan() {
  const { user } = useAuth();
  const timezone = user!.timezone;
  const [day, setDay] = useState(dateKey(new Date(), timezone));
  const week = weekStart(day);
  const [view, setView] = useState<"calendar" | "list">("calendar");
  const [mobile, setMobile] = useState(window.innerWidth < 700);
  const calendarRef = useRef<FullCalendar>(null);
  const calendarContainer = useRef<HTMLElement>(null);
  useEffect(() => {
    const resize = () => setMobile(window.innerWidth < 700);
    window.addEventListener("resize", resize);
    return () => window.removeEventListener("resize", resize);
  }, []);
  useEffect(() => {
    calendarRef.current?.getApi().gotoDate(day);
  }, [day, mobile, view]);
  const feed = useData<AgendaItem[]>(
    `/agenda?start=${week}&end=${addDays(week, 7)}`,
  );
  const blocks = useData<NotedBlock[]>(`/plan/week?start=${week}`);
  const tasks = useData<Task[]>("/tasks");
  const goals = useData<Goal[]>("/goals");
  const proposals = useData<PlanChange[]>(`/plan/changes?start=${week}`);
  const busy = useData<Busy[]>("/busy");
  const googleBusy = useData<Omit<Busy, "id">[]>("/calendar/busy");
  const online = useOnline();
  const calendar = useData<CalendarStatus>("/calendar/status");
  const { refetch: refetchCalendarStatus } = calendar;
  useEffect(() => {
    if (online && feed.dataUpdatedAt) void refetchCalendarStatus();
  }, [feed.dataUpdatedAt, online, refetchCalendarStatus]);
  const client = useQueryClient();
  const navigate = useNavigate();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<unknown>();
  const [notice, setNotice] = useState("");
  const [draftResult, setDraftResult] = useState<DraftOutcome | null>(null);
  const [editing, setEditing] = useState<AgendaEditorSelection | null>(null);
  const [showBusy, setShowBusy] = useState(false);
  const changes = (proposals.data || []).filter(
    (change) => change.status === "pending",
  );
  const proposed = (blocks.data || []).filter(
    (block) => block.status === "proposed",
  );
  const accepted = (blocks.data || []).filter(
    (block) => block.status === "accepted",
  );
  async function refresh() {
    await client.invalidateQueries();
  }
  async function mutate(path: string, body?: unknown, method = "POST") {
    setError(undefined);
    setNotice("");
    setPending(true);
    try {
      const result = await api<DraftOutcome>(path, method, body);
      if (path === "/calendar/details" && method === "DELETE") {
        await client.resetQueries({
          predicate: (query) =>
            query.queryKey[0] === user!.id &&
            typeof query.queryKey[1] === "string" &&
            query.queryKey[1].startsWith("/agenda?"),
        });
      }
      await refresh();
      return result;
    } catch (error) {
      setError(error);
    } finally {
      setPending(false);
    }
  }
  async function draft() {
    setDraftResult(null);
    const result = await mutate("/plan/draft", { week_start: week });
    if (result) {
      setDraftResult(result);
      setNotice(
        result.message || (result.blocks.length ? a.drafted : a.noDraft),
      );
    }
  }
  async function focus(block: NotedBlock) {
    await api("/focus/start", "POST", {
      time_block_id: block.id,
      planned_minutes: block.planned_minutes,
    });
    await refresh();
    navigate("/focus");
  }
  function select(item: AgendaItem) {
    if (item.source === "block") {
      const block = blocks.data?.find((value) => value.id === item.source_id);
      if (block) setEditing({ kind: "block", block });
    } else setEditing({ kind: "event", item });
  }
  async function move(
    item: AgendaItem,
    start: string,
    end: string,
    allDay: boolean,
    revert: () => void,
  ) {
    if (!online || !item.editable) {
      revert();
      return;
    }
    setError(undefined);
    try {
      if (item.source === "block") {
        const block = blocks.data?.find((value) => value.id === item.source_id);
        if (!block) throw new Error(c.requestFailed);
        if (block.status === "proposed")
          await api(`/blocks/${block.id}`, "PATCH", {
            start_at: start,
            end_at: end,
          });
        else {
          await api("/plan/changes", "POST", {
            block_id: block.id,
            operation: "move",
            start_at: start,
            end_at: end,
          });
          revert();
          setNotice(a.proposalSaved);
        }
      } else if (item.source === "local") {
        const path =
          item.recurring && item.occurrence_date
            ? `/events/${item.source_id}/occurrences/${item.occurrence_date}`
            : `/events/${item.source_id}`;
        await api(path, "PATCH", {
          start_at: start,
          end_at: end,
          all_day: allDay,
          timezone: item.timezone,
        });
      } else revert();
      await refresh();
    } catch (error) {
      revert();
      setError(error);
    }
  }
  const pendingRemoval = new Set(
    changes
      .filter((change) => change.operation === "remove")
      .map((change) => change.block_id),
  );
  const events = (feed.data || []).map((item) => ({
    id: item.id,
    title: item.title,
    start: item.start_at,
    end: item.end_at,
    allDay: item.all_day,
    editable:
      online &&
      item.editable &&
      !(
        item.source === "block" &&
        ["completed", "published", "cancelled"].includes(item.status)
      ),
    classNames: [
      `agenda-source-${item.source}`,
      `event-${item.status}`,
      ...(pendingRemoval.has(item.source_id) ? ["agenda-pending-removal"] : []),
    ],
    extendedProps: { item },
  }));
  const ghosts = changes
    .filter((change) => change.operation === "move" && change.after)
    .map((change) => ({
      id: `change-${change.id}`,
      title: `${a.proposal}: ${change.after!.title}`,
      start: change.after!.start_at,
      end: change.after!.end_at,
      editable: false,
      classNames: ["agenda-proposed-move"],
      extendedProps: { change },
    }));
  const unavailable = [...(busy.data || []), ...(googleBusy.data || [])].map(
    (value, index) => ({
      id: `busy-${index}`,
      start: value.start_at,
      end: value.end_at,
      display: "background",
      editable: false,
      classNames: ["event-busy"],
    }),
  );
  return (
    <>
      <header className="content-header">
        <h1>{c.plan.title}</h1>
        <div className="header-actions agenda-header-actions">
          <Button
            type="button"
            disabled={!online || pending}
            onClick={() => setEditing({ kind: "event" })}
          >
            <Plus size={15} />
            {a.addEvent}
          </Button>
          <Button
            type="button"
            disabled={!online || pending}
            onClick={() => setEditing({ kind: "block" })}
          >
            {a.scheduleAction}
          </Button>
          <Button
            type="button"
            className="primary"
            disabled={!online || pending}
            onClick={() => void draft()}
          >
            {pending ? c.loading : c.plan.draft}
          </Button>
        </div>
      </header>
      <div className="plan-toolbar">
        <div className="week-nav">
          <Button
            type="button"
            aria-label={c.plan.previous}
            onClick={() => {
              setDay(addDays(day, -7));
              setDraftResult(null);
              setNotice("");
            }}
          >
            <ChevronLeft size={16} />
          </Button>
          <span>
            {week} — {addDays(week, 6)}
          </span>
          <Button
            type="button"
            aria-label={c.plan.next}
            onClick={() => {
              setDay(addDays(day, 7));
              setDraftResult(null);
              setNotice("");
            }}
          >
            <ChevronRight size={16} />
          </Button>
          <Button
            type="button"
            onClick={() => setDay(dateKey(new Date(), timezone))}
          >
            {c.today.title}
          </Button>
        </div>
        <div className="segmented">
          <Button
            type="button"
            aria-pressed={view === "calendar"}
            onClick={() => setView("calendar")}
          >
            {c.plan.calendar}
          </Button>
          <Button
            type="button"
            aria-pressed={view === "list"}
            onClick={() => setView("list")}
          >
            {c.plan.list}
          </Button>
        </div>
      </div>
      <Notice
        error={
          error || feed.error || blocks.error || goals.error || proposals.error
        }
      />
      {notice && (
        <div className="save-note agenda-outcome" role="status">
          <p>{notice}</p>
          {draftResult?.empty_reason === "no_goals" && (
            <Link className="button" to="/goals/new">
              {c.goals.new}
            </Link>
          )}
        </div>
      )}
      {draftResult?.capacity_warning && (
        <p className="warning-note" role="status">
          {draftResult.capacity_warning}
        </p>
      )}
      {proposed.length > 0 && (
        <div className="draft-toolbar">
          <span>
            {proposed.length} {c.plan.proposed.toLowerCase()}
          </span>
          <Button
            type="button"
            disabled={!online || pending}
            onClick={() =>
              void mutate("/plan/accept", {
                block_ids: proposed.map((block) => block.id),
              })
            }
          >
            {c.plan.accept}
          </Button>
        </div>
      )}
      {accepted.length > 0 && calendar.data?.can_publish && (
        <div className="draft-toolbar">
          <p>{c.plan.approval}</p>
          <Button
            type="button"
            disabled={!online || pending}
            onClick={() => {
              setPending(true);
              setError(undefined);
              void api<{ published: string[]; failed: string[] }>(
                "/calendar/publish",
                "POST",
                { block_ids: accepted.map((block) => block.id) },
              )
                .then(async (result) => {
                  setNotice(
                    result.failed.length
                      ? `${result.published.length} / ${accepted.length} ${c.plan.published.toLowerCase()}`
                      : c.plan.publishedNote,
                  );
                  await refresh();
                })
                .catch(setError)
                .finally(() => setPending(false));
            }}
          >
            {c.plan.publish}
          </Button>
        </div>
      )}
      <div className="agenda-layout">
        <section
          ref={calendarContainer}
          className="calendar-panel agenda-calendar"
          aria-label={c.plan.calendar}
        >
          {feed.isPending && (
            <p className="agenda-loading" role="status">
              {c.loading}
            </p>
          )}
          {view === "calendar" ? (
            <FullCalendar
              ref={calendarRef}
              key={mobile ? "day" : "week"}
              plugins={[timeGridPlugin, interactionPlugin, luxonPlugin]}
              initialView={mobile ? "timeGridDay" : "timeGridWeek"}
              initialDate={day}
              timeZone={timezone}
              firstDay={1}
              buttonIcons={false}
              buttonText={{ prev: a.previousDay, next: a.nextDay }}
              viewDidMount={(info) => prepareScrollRegion(info.el)}
              headerToolbar={
                mobile
                  ? { left: "prev,next", center: "title", right: "" }
                  : false
              }
              datesSet={(info) => {
                if (calendarContainer.current)
                  prepareScrollRegion(calendarContainer.current);
                const start = dateKey(info.start, timezone);
                if (mobile) {
                  if (start !== day) setDay(start);
                } else if (weekStart(start) !== week) setDay(start);
              }}
              allDaySlot
              allDayText={a.allDay}
              slotMinTime="00:00:00"
              slotMaxTime="24:00:00"
              scrollTime="08:00:00"
              height={mobile ? 650 : 730}
              nowIndicator
              weekends
              selectable={online}
              selectMirror
              editable={online}
              eventDurationEditable={online}
              eventResizableFromStart
              eventAllow={(drop, dragged) => {
                const item = dragged?.extendedProps.item as
                  AgendaItem | undefined;
                return item?.source !== "block" || !drop.allDay;
              }}
              events={[...events, ...ghosts, ...unavailable]}
              select={(info) => {
                if (online)
                  setEditing({
                    kind: "event",
                    start: info.startStr,
                    end: info.endStr,
                    allDay: info.allDay,
                  });
                info.view.calendar.unselect();
              }}
              eventClick={(info) => {
                const item = info.event.extendedProps.item as
                  AgendaItem | undefined;
                if (item) select(item);
                else if (info.event.extendedProps.change)
                  document
                    .getElementById("plan-changes")
                    ?.scrollIntoView({ behavior: "smooth", block: "nearest" });
              }}
              eventDrop={(info) => {
                const item = info.event.extendedProps.item as
                  AgendaItem | undefined;
                if (item && info.event.start && info.event.end)
                  void move(
                    item,
                    eventInstant(
                      info.event.start,
                      info.event.startStr,
                      info.event.allDay,
                      item.timezone,
                    ),
                    eventInstant(
                      info.event.end,
                      info.event.endStr,
                      info.event.allDay,
                      item.timezone,
                    ),
                    info.event.allDay,
                    info.revert,
                  );
                else info.revert();
              }}
              eventResize={(info) => {
                const item = info.event.extendedProps.item as
                  AgendaItem | undefined;
                if (item && info.event.start && info.event.end)
                  void move(
                    item,
                    eventInstant(
                      info.event.start,
                      info.event.startStr,
                      info.event.allDay,
                      item.timezone,
                    ),
                    eventInstant(
                      info.event.end,
                      info.event.endStr,
                      info.event.allDay,
                      item.timezone,
                    ),
                    info.event.allDay,
                    info.revert,
                  );
                else info.revert();
              }}
              dayHeaderFormat={{ weekday: "short", day: "numeric" }}
              slotLabelFormat={{
                hour: "numeric",
                minute: "2-digit",
                hour12: false,
              }}
            />
          ) : feed.data?.length ? (
            <div className="plan-list">
              {feed.data
                .slice()
                .sort((left, right) =>
                  left.start_at.localeCompare(right.start_at),
                )
                .map((item) => (
                  <button
                    type="button"
                    className="plan-list-row"
                    key={item.id}
                    onClick={() => select(item)}
                  >
                    <span>
                      {item.start_at.slice(0, 10)}
                      <small>
                        {item.all_day
                          ? a.allDay
                          : `${clock(item.start_at, timezone)}–${clock(item.end_at, timezone)}`}
                      </small>
                    </span>
                    <strong>{item.title}</strong>
                    <span className="status-label">
                      {item.source === "google"
                        ? a.google
                        : item.source === "local"
                          ? a.event
                          : c.plan[item.status as keyof typeof c.plan] ||
                            item.status}
                      {item.recurring ? ` · ${a.recurring}` : ""}
                    </span>
                  </button>
                ))}
            </div>
          ) : !feed.isPending ? (
            <Empty title={a.noItems}>
              <p>{a.emptyWeekHint}</p>
            </Empty>
          ) : null}
        </section>
        <AgendaTasks
          tasks={tasks.data || []}
          goals={goals.data || []}
          online={online}
          pending={tasks.isPending}
          error={tasks.error}
          onChange={refresh}
          onSchedule={(task) => setEditing({ kind: "event", task })}
        />
      </div>
      <AgendaChanges
        changes={changes}
        timezone={timezone}
        online={online}
        onChange={refresh}
      />
      <section className="panel agenda-calendar-permissions">
        <Notice error={calendar.error} />
        {(calendar.data?.details_enabled || calendar.data?.can_read_events) && (
          <Button
            type="button"
            disabled={!online || pending}
            onClick={() =>
              void mutate("/calendar/details", undefined, "DELETE")
            }
          >
            {pending ? c.saving : a.hideDetails}
          </Button>
        )}
        {calendar.data?.details_error && (
          <p className="warning-note" role="status">
            {a.detailsUnavailable}
          </p>
        )}
        {calendar.data?.configured &&
          !(calendar.data.details_enabled || calendar.data.can_read_events) && (
            <>
              <p className="form-hint">{a.detailsHint}</p>
              <a
                className={`button ${online ? "" : "disabled-link"}`}
                aria-disabled={!online}
                href={
                  online ? "/api/v1/calendar/connect?details=true" : undefined
                }
              >
                {a.detailsConsent}
              </a>
            </>
          )}
      </section>
      <section className="panel agenda-busy">
        <div className="panel-heading">
          <h2>{a.busy}</h2>
          <Button
            type="button"
            disabled={!online}
            onClick={() => setShowBusy(!showBusy)}
          >
            <Plus size={14} />
            {a.addBusy}
          </Button>
        </div>
        <Notice error={busy.error} />
        {showBusy && (
          <BusyForm
            timezone={timezone}
            online={online}
            onSave={async (body) => {
              await api("/busy", "POST", body);
              await refresh();
              setShowBusy(false);
            }}
          />
        )}
        {busy.data
          ?.filter(
            (item) =>
              new Date(item.end_at) >
                DateTime.fromISO(week, { zone: timezone }).toJSDate() &&
              new Date(item.start_at) <
                DateTime.fromISO(addDays(week, 7), {
                  zone: timezone,
                }).toJSDate(),
          )
          .map((item) => (
            <div className="busy-row" key={item.id}>
              <span>
                {dateKey(new Date(item.start_at), timezone)} ·{" "}
                {clock(item.start_at, timezone)}–{clock(item.end_at, timezone)}
              </span>
              <Button
                type="button"
                className="icon-button"
                disabled={!online || pending}
                aria-label={c.plan.clearBusy}
                onClick={() =>
                  void mutate(`/busy/${item.id}`, undefined, "DELETE")
                }
              >
                <X size={14} />
              </Button>
            </div>
          ))}
      </section>
      {editing && (
        <AgendaEditor
          selection={editing}
          timezone={timezone}
          goals={goals.data || []}
          tasks={tasks.data || []}
          online={online}
          close={() => setEditing(null)}
          onChange={refresh}
          onFocus={focus}
        />
      )}
    </>
  );
}
function BusyForm({
  timezone,
  online,
  onSave,
}: {
  timezone: string;
  online: boolean;
  onSave: (body: unknown) => Promise<void>;
}) {
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  return (
    <SubmitForm
      className="inline-form"
      onSubmit={async () => {
        const left = DateTime.fromISO(start, { zone: timezone });
        const right = DateTime.fromISO(end, { zone: timezone });
        if (!left.isValid || !right.isValid || right <= left)
          throw new Error(a.invalidDates);
        await onSave({
          start_at: left.toUTC().toISO(),
          end_at: right.toUTC().toISO(),
        });
      }}
    >
      {(pending) => (
        <>
          <Field label={c.plan.start}>
            <input
              type="datetime-local"
              required
              value={start}
              disabled={!online}
              onChange={(e) => setStart(e.target.value)}
            />
          </Field>
          <Field label={c.plan.end}>
            <input
              type="datetime-local"
              min={start}
              required
              value={end}
              disabled={!online}
              onChange={(e) => setEnd(e.target.value)}
            />
          </Field>
          <Button className="primary" disabled={!online || pending}>
            {c.add}
          </Button>
        </>
      )}
    </SubmitForm>
  );
}

function eventInstant(
  value: Date,
  raw: string,
  allDay: boolean,
  timezone: string,
) {
  return allDay
    ? DateTime.fromISO(raw.slice(0, 10), { zone: timezone })
        .startOf("day")
        .toUTC()
        .toISO() || value.toISOString()
    : value.toISOString();
}

function prepareScrollRegion(view: HTMLElement) {
  view
    .querySelectorAll<HTMLElement>(".fc-scroller-liquid-absolute")
    .forEach((scroller) => {
      scroller
        .querySelectorAll<HTMLElement>('.fc-timegrid-col[role="gridcell"]')
        .forEach((cell) => {
          cell.tabIndex = 0;
          cell.setAttribute(
            "title",
            `${a.timedAgenda} ${cell.dataset.date || ""}`,
          );
        });
    });
}
