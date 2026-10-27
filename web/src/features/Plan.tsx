import { useState, useEffect } from "react";
import FullCalendar from "@fullcalendar/react";
import timeGridPlugin from "@fullcalendar/timegrid";
import interactionPlugin from "@fullcalendar/interaction";
import luxonPlugin from "@fullcalendar/luxon3";
import { DateTime } from "luxon";
import { useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Plus, X } from "lucide-react";
import { copy as c } from "../copy/en";
import { useAuth } from "../lib/auth";
import { useData, useOnline } from "../lib/hooks";
import { api } from "../api/client";
import type { Block, Busy, Draft } from "../api/types";
import {
  addDays,
  clock,
  dateKey,
  localInput,
  minutes,
  weekStart,
} from "../lib/time";
import { Button } from "../components/ui/Button";
import { Empty, Field, Notice, SubmitForm } from "../components/ui/Forms";
export interface CalendarStatus {
  configured: boolean;
  connected: boolean;
  status: string;
  can_publish: boolean;
  last_synced_at: string | null;
}
export function Plan() {
  const { user } = useAuth();
  const timezone = user!.timezone;
  const [week, setWeek] = useState(weekStart(dateKey(new Date(), timezone)));
  const [view, setView] = useState<"calendar" | "list">("calendar");
  const [mobile, setMobile] = useState(window.innerWidth < 700);
  useEffect(() => {
    const change = () => setMobile(window.innerWidth < 700);
    window.addEventListener("resize", change);
    return () => window.removeEventListener("resize", change);
  }, []);
  const blocks = useData<Block[]>(`/plan/week?start=${week}`);
  const busy = useData<Busy[]>("/busy");
  const googleBusy = useData<Omit<Busy, "id">[]>("/calendar/busy");
  const calendar = useData<CalendarStatus>("/calendar/status");
  const online = useOnline();
  const client = useQueryClient();
  const [error, setError] = useState<unknown>();
  const [warning, setWarning] = useState("");
  const [pending, setPending] = useState(false);
  const [selected, setSelected] = useState<Block | null>(null);
  const [showBusy, setShowBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const proposed = blocks.data?.filter((b) => b.status === "proposed") || [];
  const accepted = blocks.data?.filter((b) => b.status === "accepted") || [];
  async function mutate(path: string, body?: unknown, method = "POST") {
    setError(undefined);
    setNotice("");
    setPending(true);
    try {
      const value = await api<Draft>(path, method, body);
      await client.invalidateQueries();
      return value;
    } catch (error) {
      setError(error);
    } finally {
      setPending(false);
    }
  }
  async function move(
    blockId: string,
    start: string,
    end: string,
    revert: () => void,
  ) {
    if (!online) {
      revert();
      return;
    }
    try {
      await api(`/blocks/${blockId}`, "PATCH", {
        start_at: start,
        end_at: end,
      });
      await client.invalidateQueries();
    } catch (error) {
      revert();
      setError(error);
    }
  }
  const selectedBlock =
    blocks.data?.find((b) => b.id === selected?.id) || selected;
  const events = (blocks.data || [])
    .filter((b) => b.status !== "cancelled")
    .map((b) => ({
      id: b.id,
      title: b.title || "",
      start: b.start_at,
      end: b.end_at,
      classNames: [`event-${b.status}`],
      editable: online && b.status !== "published" && b.status !== "completed",
      extendedProps: { block: b },
    }));
  const unavailable = [...(busy.data || []), ...(googleBusy.data || [])].map(
    (b, i) => ({
      id: `busy-${i}`,
      start: b.start_at,
      end: b.end_at,
      display: "background",
      classNames: ["event-busy"],
      editable: false,
    }),
  );
  return (
    <>
      <header className="content-header">
        <h1>{c.plan.title}</h1>
        <div className="header-actions">
          <Button
            disabled={!online || pending}
            className="primary"
            onClick={() =>
              void mutate("/plan/draft", { week_start: week }).then(
                (result) => {
                  if (result) setWarning(result.capacity_warning || "");
                },
              )
            }
          >
            {pending ? c.loading : c.plan.draft}
          </Button>
        </div>
      </header>
      <div className="plan-toolbar">
        <div className="week-nav">
          <Button
            aria-label={c.plan.previous}
            onClick={() => {
              setWeek(addDays(week, -7));
              setSelected(null);
            }}
          >
            <ChevronLeft size={16} />
          </Button>
          <span>
            {week} — {addDays(week, 6)}
          </span>
          <Button
            aria-label={c.plan.next}
            onClick={() => {
              setWeek(addDays(week, 7));
              setSelected(null);
            }}
          >
            <ChevronRight size={16} />
          </Button>
        </div>
        <div className="segmented">
          <Button
            aria-pressed={view === "calendar"}
            onClick={() => setView("calendar")}
          >
            {c.plan.calendar}
          </Button>
          <Button
            aria-pressed={view === "list"}
            onClick={() => setView("list")}
          >
            {c.plan.list}
          </Button>
        </div>
      </div>
      <Notice error={error || blocks.error} />
      {warning && (
        <p className="warning-note" role="status">
          {warning}
        </p>
      )}
      {notice && (
        <p className="save-note" role="status">
          {notice}
        </p>
      )}
      {proposed.length > 0 && (
        <div className="draft-toolbar">
          <span>
            {proposed.length} {c.plan.proposed.toLowerCase()}
          </span>
          <Button
            disabled={!online || pending}
            onClick={() =>
              void mutate("/plan/accept", {
                block_ids: proposed.map((b) => b.id),
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
            disabled={!online || pending}
            onClick={() =>
              void api<{ published: string[]; failed: string[] }>(
                "/calendar/publish",
                "POST",
                { block_ids: accepted.map((b) => b.id) },
              )
                .then(async (result) => {
                  setNotice(
                    result.failed.length
                      ? `${result.published.length} / ${accepted.length} ${c.plan.published.toLowerCase()}`
                      : c.plan.publishedNote,
                  );
                  await client.invalidateQueries();
                })
                .catch(setError)
            }
          >
            {c.plan.publish}
          </Button>
        </div>
      )}
      <div className={`plan-layout ${selectedBlock ? "has-selection" : ""}`}>
        <section className="calendar-panel">
          {view === "calendar" ? (
            <FullCalendar
              key={`${week}-${mobile}`}
              plugins={[timeGridPlugin, interactionPlugin, luxonPlugin]}
              initialView={mobile ? "timeGridDay" : "timeGridWeek"}
              initialDate={
                mobile && week === weekStart(dateKey(new Date(), timezone))
                  ? dateKey(new Date(), timezone)
                  : week
              }
              firstDay={1}
              timeZone={timezone}
              headerToolbar={
                mobile
                  ? { left: "prev,next", center: "title", right: "" }
                  : false
              }
              allDaySlot={false}
              slotMinTime="06:00:00"
              slotMaxTime="23:00:00"
              height="auto"
              nowIndicator
              weekends
              editable={online}
              eventDurationEditable={online}
              events={[...events, ...unavailable]}
              eventClick={(info) => {
                const block = info.event.extendedProps.block as
                  Block | undefined;
                if (block) setSelected(block);
              }}
              eventDrop={(info) => {
                if (info.event.start && info.event.end)
                  void move(
                    info.event.id,
                    info.event.start.toISOString(),
                    info.event.end.toISOString(),
                    info.revert,
                  );
                else info.revert();
              }}
              eventResize={(info) => {
                if (info.event.start && info.event.end)
                  void move(
                    info.event.id,
                    info.event.start.toISOString(),
                    info.event.end.toISOString(),
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
          ) : blocks.data?.length ? (
            <div className="plan-list">
              {blocks.data
                .slice()
                .sort((a, b) => a.start_at.localeCompare(b.start_at))
                .map((block) => (
                  <button
                    key={block.id}
                    onClick={() => setSelected(block)}
                    className="plan-list-row"
                  >
                    <span>
                      {dateKey(new Date(block.start_at), timezone)}
                      <small>
                        {clock(block.start_at, timezone)} –{" "}
                        {clock(block.end_at, timezone)}
                      </small>
                    </span>
                    <strong>{block.title}</strong>
                    <span className={`status-label status-${block.status}`}>
                      {c.plan[block.status as keyof typeof c.plan] ||
                        block.status}
                    </span>
                  </button>
                ))}
            </div>
          ) : (
            <Empty title={c.plan.empty} />
          )}
        </section>
        {selectedBlock && (
          <BlockDetails
            key={`${selectedBlock.id}-${selectedBlock.start_at}`}
            block={selectedBlock}
            timezone={timezone}
            online={online}
            close={() => setSelected(null)}
            save={async (path, body, method) => {
              await api(path, method, body);
              await client.invalidateQueries();
              if (method === "DELETE") setSelected(null);
            }}
          />
        )}
      </div>
      <section className="panel">
        <div className="panel-heading">
          <h2>{c.plan.busy}</h2>
          <Button onClick={() => setShowBusy(!showBusy)} disabled={!online}>
            <Plus size={14} />
            {c.plan.addBusy}
          </Button>
        </div>
        <p className="form-hint">{c.plan.busyHint}</p>
        {showBusy && (
          <BusyForm
            timezone={timezone}
            onSave={async (body) => {
              await api("/busy", "POST", body);
              await client.invalidateQueries();
              setShowBusy(false);
            }}
          />
        )}
        {busy.data
          ?.filter(
            (b) =>
              dateKey(new Date(b.start_at), timezone) >= week &&
              dateKey(new Date(b.start_at), timezone) <= addDays(week, 6),
          )
          .map((b) => (
            <div className="busy-row" key={b.id}>
              <span>
                {dateKey(new Date(b.start_at), timezone)} ·{" "}
                {clock(b.start_at, timezone)}–{clock(b.end_at, timezone)}
              </span>
              <Button
                className="icon-button"
                disabled={!online}
                aria-label={c.plan.clearBusy}
                onClick={() =>
                  void mutate(`/busy/${b.id}`, undefined, "DELETE")
                }
              >
                <X size={14} />
              </Button>
            </div>
          ))}
      </section>
    </>
  );
}
function BusyForm({
  timezone,
  onSave,
}: {
  timezone: string;
  onSave: (body: unknown) => Promise<void>;
}) {
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  return (
    <SubmitForm
      className="inline-form"
      onSubmit={async () => {
        await onSave({
          start_at: DateTime.fromISO(start, { zone: timezone }).toUTC().toISO(),
          end_at: DateTime.fromISO(end, { zone: timezone }).toUTC().toISO(),
        });
      }}
    >
      {(busy) => (
        <>
          <Field label={c.plan.start}>
            <input
              type="datetime-local"
              required
              value={start}
              onChange={(e) => setStart(e.target.value)}
            />
          </Field>
          <Field label={c.plan.end}>
            <input
              type="datetime-local"
              required
              min={start}
              value={end}
              onChange={(e) => setEnd(e.target.value)}
            />
          </Field>
          <Button disabled={busy} className="primary">
            {c.add}
          </Button>
        </>
      )}
    </SubmitForm>
  );
}
function BlockDetails({
  block,
  timezone,
  online,
  close,
  save,
}: {
  block: Block;
  timezone: string;
  online: boolean;
  close: () => void;
  save: (path: string, body: unknown, method: string) => Promise<void>;
}) {
  const [actionError, setActionError] = useState<unknown>();
  const [start, setStart] = useState(localInput(block.start_at, timezone));
  const [end, setEnd] = useState(localInput(block.end_at, timezone));
  return (
    <aside className="panel block-details">
      <div className="panel-heading">
        <h2>{c.plan.selectBlock}</h2>
        <Button className="icon-button" aria-label={c.close} onClick={close}>
          <X size={17} />
        </Button>
      </div>
      <Notice error={actionError} />
      <h3>{block.title}</h3>
      <span className={`status-label status-${block.status}`}>
        {c.plan[block.status as keyof typeof c.plan] || block.status} ·{" "}
        {minutes(block.planned_minutes)}
      </span>
      <h4>{c.plan.reason}</h4>
      <p className="body-text">{block.reason}</p>
      <SubmitForm
        onSubmit={() =>
          save(
            `/blocks/${block.id}`,
            {
              start_at: DateTime.fromISO(start, { zone: timezone })
                .toUTC()
                .toISO(),
              end_at: DateTime.fromISO(end, { zone: timezone }).toUTC().toISO(),
            },
            "PATCH",
          )
        }
      >
        {(busy) => (
          <>
            <fieldset
              disabled={
                !online ||
                block.status === "published" ||
                block.status === "completed"
              }
            >
              <Field label={c.plan.start}>
                <input
                  type="datetime-local"
                  value={start}
                  required
                  onChange={(e) => setStart(e.target.value)}
                />
              </Field>
              <Field label={c.plan.end}>
                <input
                  type="datetime-local"
                  value={end}
                  min={start}
                  required
                  onChange={(e) => setEnd(e.target.value)}
                />
              </Field>
              <Button type="submit" disabled={busy}>
                {c.plan.move}
              </Button>
            </fieldset>
          </>
        )}
      </SubmitForm>
      <SubmitForm
        onSubmit={() =>
          block.status === "proposed"
            ? save("/plan/accept", { block_ids: [block.id] }, "POST")
            : save(`/blocks/${block.id}`, { status: "skipped" }, "PATCH")
        }
      >
        {(busy) => (
          <div className="block-controls">
            {!["completed", "skipped", "cancelled"].includes(block.status) && (
              <Button className="primary" disabled={busy || !online}>
                {block.status === "proposed" ? c.plan.acceptOne : c.today.skip}
              </Button>
            )}
            {block.status !== "published" && (
              <Button
                type="button"
                disabled={busy || !online}
                onClick={() =>
                  void save(`/blocks/${block.id}`, undefined, "DELETE").catch(
                    setActionError,
                  )
                }
              >
                {c.plan.discard}
              </Button>
            )}
          </div>
        )}
      </SubmitForm>
    </aside>
  );
}
