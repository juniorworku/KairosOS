import { useEffect, useState, useRef } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Play, Square } from "lucide-react";
import { copy as c } from "../copy/en";
import { useAuth } from "../lib/auth";
import { useData, useOnline } from "../lib/hooks";
import { api, queueWrite } from "../api/client";
import type { FocusSession, Goal } from "../api/types";
import { clock, minutes } from "../lib/time";
import { Button } from "../components/ui/Button";
import { Modal } from "../components/ui/Modal";
import { Empty, Field, SubmitForm } from "../components/ui/Forms";
export function FocusPage() {
  const { user } = useAuth();
  const online = useOnline();
  const client = useQueryClient();
  const active = useQuery({
    queryKey: ["/focus/active"],
    queryFn: () => api<FocusSession | null>("/focus/active"),
    refetchInterval: 15000,
    retry: false,
  });
  const history = useData<{
    items: FocusSession[];
    next_cursor: string | null;
  }>("/focus/sessions?limit=50");
  const goals = useData<Goal[]>("/goals");
  const [action, setAction] = useState("");
  const [duration, setDuration] = useState(25);
  const [ending, setEnding] = useState<FocusSession | null>(null);
  const [rating, setRating] = useState(0);
  const [now, setNow] = useState(Date.now());
  const [queued, setQueued] = useState(false);
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  const session = active.data;
  const notified = useRef<string>();
  useEffect(() => {
    if (
      session &&
      new Date(session.ends_at).getTime() <= now &&
      notified.current !== session.id
    ) {
      notified.current = session.id;
      setEnding(session);
    }
  }, [now, session, ending]);
  const remaining = session
    ? Math.max(0, Math.ceil((new Date(session.ends_at).getTime() - now) / 1000))
    : duration * 60;
  const time = `${Math.floor(remaining / 60)
    .toString()
    .padStart(2, "0")}:${(remaining % 60).toString().padStart(2, "0")}`;
  return (
    <>
      <header className="content-header">
        <h1>{c.focus.title}</h1>
      </header>
      <div className="focus-layout">
        <section className="panel timer-panel">
          <div className="timer-context">
            {session
              ? goals.data
                  ?.flatMap((g) => g.actions)
                  .find((a) => a.id === session.action_id)?.title ||
                c.focus.unlinked
              : c.focus.title}
          </div>
          <div
            className={`timer ${session ? "running" : ""}`}
            role="timer"
            aria-label={c.focus.remaining}
          >
            {time}
          </div>
          {session ? (
            <Button className="primary" onClick={() => setEnding(session)}>
              <Square size={14} />
              {c.focus.end}
            </Button>
          ) : (
            <SubmitForm
              onSubmit={async () => {
                await api("/focus/start", "POST", {
                  action_id: action || null,
                  planned_minutes: duration,
                });
                setQueued(false);
                await client.invalidateQueries();
              }}
            >
              {(busy) => (
                <>
                  <div className="form-grid">
                    <Field label={c.focus.action}>
                      <select
                        value={action}
                        onChange={(e) => setAction(e.target.value)}
                      >
                        <option value="">{c.focus.unlinked}</option>
                        {goals.data
                          ?.filter((g) => g.status === "active")
                          .map((g) => (
                            <optgroup label={g.title} key={g.id}>
                              {g.actions.map((a) => (
                                <option value={a.id} key={a.id}>
                                  {a.title}
                                </option>
                              ))}
                            </optgroup>
                          ))}
                      </select>
                    </Field>
                    <Field label={c.focus.duration}>
                      <input
                        type="number"
                        required
                        min={1}
                        max={240}
                        value={duration}
                        onChange={(e) => setDuration(Number(e.target.value))}
                      />
                    </Field>
                  </div>
                  <Button className="primary" disabled={busy || !online}>
                    <Play size={14} />
                    {c.focus.start}
                  </Button>
                </>
              )}
            </SubmitForm>
          )}
          {queued && (
            <p role="status" className="save-note">
              {c.queued}
            </p>
          )}
        </section>
        <section className="panel">
          <h2>{c.focus.history}</h2>
          {history.data?.items.length ? (
            <div className="session-history">
              {history.data.items.map((s) => (
                <div key={s.id} className="session-row">
                  <div>
                    <strong>
                      {goals.data
                        ?.flatMap((g) => g.actions)
                        .find((a) => a.id === s.action_id)?.title ||
                        c.focus.unlinked}
                    </strong>
                    <small>
                      {new Date(s.started_at).toLocaleDateString(undefined, {
                        timeZone: user!.timezone,
                      })}{" "}
                      · {clock(s.started_at, user!.timezone)}
                    </small>
                  </div>
                  <span>{minutes(s.actual_minutes ?? 0)}</span>
                  <Button
                    onClick={() => {
                      setEnding(s);
                      setRating(s.self_rating || 0);
                    }}
                    className="rating-button"
                  >
                    {s.self_rating ? `${s.self_rating} / 5` : c.focus.noRating}
                  </Button>
                </div>
              ))}
            </div>
          ) : (
            <Empty title={c.focus.none} />
          )}
        </section>
      </div>
      {ending && (
        <Modal titleId="rating-title" onClose={() => setEnding(null)}>
          <h2 id="rating-title">{c.focus.rate}</h2>
          <SubmitForm
            onSubmit={async () => {
              const body = {
                self_rating: rating || null,
                ended_at: new Date(
                  Math.min(Date.now(), new Date(ending.ends_at).getTime()),
                ).toISOString(),
              };
              if (online) {
                await api(`/focus/${ending.id}/end`, "POST", body);
                await client.invalidateQueries();
              } else {
                await queueWrite(`/focus/${ending.id}/end`, body);
                client.setQueryData(["/focus/active"], null);
                setQueued(true);
              }
              setEnding(null);
              setRating(0);
            }}
          >
            {(busy) => (
              <>
                <div
                  className="rating-options"
                  role="group"
                  aria-label={c.focus.rating}
                >
                  {[1, 2, 3, 4, 5].map((n) => (
                    <Button
                      type="button"
                      aria-pressed={rating === n}
                      onClick={() => setRating(n)}
                      key={n}
                    >
                      {n}
                    </Button>
                  ))}
                </div>
                <div className="modal-actions">
                  <Button type="button" onClick={() => setEnding(null)}>
                    {c.cancel}
                  </Button>
                  <Button className="primary" disabled={busy}>
                    {c.focus.save}
                  </Button>
                </div>
              </>
            )}
          </SubmitForm>
        </Modal>
      )}
    </>
  );
}
