import { useEffect, useState, useRef } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { GoalCheckin } from "./GoalCheckin";
import { BlockingStatus } from "./BlockingStatus";
import { planHref, reviewHref, sessionGoal } from "./workflow";
import { workflowCopy as w } from "./workflow-copy";
import "./workflow.css";
import { Play, Square } from "lucide-react";
import { copy as c } from "../copy/en";
import { useAuth } from "../lib/auth";
import { useData, useOnline } from "../lib/hooks";
import { api, queueWrite } from "../api/client";
import type { FocusSession, Goal } from "../api/types";
import { clock, minutes, dateKey } from "../lib/time";
import { Button } from "../components/ui/Button";
import { Modal } from "../components/ui/Modal";
import { Empty, Field, Notice, SubmitForm } from "../components/ui/Forms";
import { Card, CardContent, CardHeader } from "../components/primitives/card";
import { Badge } from "../components/primitives/badge";
import { Progress } from "../components/primitives/progress";
import { Input } from "../components/primitives/input";
import { NativeSelect } from "../components/primitives/native-select";
export function FocusPage() {
  const { user } = useAuth();
  const [params] = useSearchParams();
  const [completed, setCompleted] = useState<FocusSession | null>(null);
  const online = useOnline();
  const client = useQueryClient();
  const active = useQuery({
    queryKey: [user!.id, "/focus/active"],
    queryFn: ({ signal }) =>
      api<FocusSession | null>("/focus/active", "GET", undefined, signal),
    networkMode: "always",
    refetchInterval: 15000,
    retry: false,
  });
  const history = useData<{
    items: FocusSession[];
    next_cursor: string | null;
  }>("/focus/sessions?limit=50");
  const goals = useData<Goal[]>("/goals");
  const blocklists =
    useData<{ id: string; domains: string[]; is_default: boolean }[]>(
      "/blocklists",
    );
  const [action, setAction] = useState(params.get("action") || "");
  const [duration, setDuration] = useState(25);
  const [ending, setEnding] = useState<FocusSession | null>(null);
  const [stopTime, setStopTime] = useState("");
  const [rating, setRating] = useState(0);
  const [now, setNow] = useState(Date.now());
  const [queued, setQueued] = useState(false);
  const [error, setError] = useState<unknown>();
  const [stopping, setStopping] = useState(false);
  const previous = useRef<FocusSession | null>(null);
  const notified = useRef("");
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  const session = active.data;
  useEffect(() => {
    if (session) previous.current = session;
    const last = session || previous.current;
    if (
      last &&
      new Date(last.ends_at).getTime() <= now &&
      notified.current !== last.id
    ) {
      notified.current = last.id;
      setStopTime(last.ends_at);
      setEnding(last);
      setCompleted(last);
      void client.invalidateQueries({
        predicate: (q) =>
          String(q.queryKey[1]).startsWith("/focus/") &&
          q.queryKey[1] !== "/focus/active",
      });
    }
  }, [now, session, client]);
  async function stop(s: FocusSession) {
    setStopping(true);
    setError(undefined);
    const stoppedAt = new Date(
      Math.min(Date.now(), new Date(s.ends_at).getTime()),
    ).toISOString();
    try {
      const body = { ended_at: stoppedAt };
      let ended: FocusSession = { ...s, ended_at: stoppedAt };
      if (online) {
        ended = await api<FocusSession>(`/focus/${s.id}/end`, "POST", body);
      } else {
        await queueWrite(`/focus/${s.id}/end`, body);
        setQueued(true);
      }
      notified.current = s.id;
      previous.current = null;
      client.setQueryData([user!.id, "/focus/active"], null);
      setStopTime(stoppedAt);
      setEnding(ended);
      setCompleted(ended);
      if (online) await client.invalidateQueries();
    } catch (error) {
      setError(error);
    } finally {
      setStopping(false);
    }
  }
  const remaining = session
    ? Math.max(0, Math.ceil((new Date(session.ends_at).getTime() - now) / 1000))
    : duration * 60;
  const time = `${Math.floor(remaining / 60)
    .toString()
    .padStart(2, "0")}:${(remaining % 60).toString().padStart(2, "0")}`;
  const linkedGoal = sessionGoal(completed, goals.data || []);
  const currentGoal = sessionGoal(session, goals.data || []);
  return (
    <div className="focus-workspace">
      <header className="content-header">
        <h1>{c.focus.title}</h1>
      </header>
      <Notice error={error || active.error || history.error || goals.error} />
      <div className="sr-only" aria-live="polite">
        {ending && new Date(ending.ends_at).getTime() <= now
          ? c.focus.complete
          : ""}
      </div>
      {completed && !session && (
        <Card className="focus-completion">
          <CardHeader>
            <h2>{w.sessionEnded}</h2>
            <p>{completed.title || c.focus.unlinked}</p>
          </CardHeader>
          <CardContent>
            <div className="workflow-actions">
              {linkedGoal && (
                <Button asChild>
                  <Link to={"/goals/" + linkedGoal.id}>{w.viewGoal}</Link>
                </Button>
              )}
              <Button asChild>
                <Link
                  to={planHref(
                    dateKey(new Date(completed.started_at), user!.timezone),
                    linkedGoal?.id,
                    completed.time_block_id,
                  )}
                >
                  {w.planSession}
                </Link>
              </Button>
              <Button asChild>
                <Link to={reviewHref(completed, user!.timezone)}>
                  {w.reviewSession}
                </Link>
              </Button>
            </div>
            {linkedGoal && (
              <GoalCheckin key={linkedGoal.id} goal={linkedGoal} />
            )}
          </CardContent>
        </Card>
      )}
      <div className="focus-layout">
        <Card className="timer-panel">
          <CardContent className="flex flex-col items-center gap-6 pt-6">
            <div className="timer-context focus-current-action">
              {session
                ? session.title ||
                  goals.data
                    ?.flatMap((g) => g.actions)
                    .find((a) => a.id === session.action_id)?.title ||
                  c.focus.unlinked
                : c.focus.title}
            </div>
            {currentGoal && (
              <Link to={"/goals/" + currentGoal.id}>{currentGoal.title}</Link>
            )}
            <div className="focus-clock">
              <div
                className={`timer ${session ? "running" : ""}`}
                role="timer"
                aria-label={c.focus.remaining}
              >
                {time}
              </div>
              <span className="timer-dial-label">{c.focus.remaining}</span>
            </div>
            {session && (
              <Progress
                value={Math.min(
                  100,
                  (remaining / (session.planned_minutes * 60)) * 100,
                )}
                aria-label={c.focus.remaining}
                className="h-1.5 w-full max-w-xs"
              />
            )}
            {session ? (
              <Button
                className="primary"
                onClick={() => void stop(session)}
                disabled={stopping}
              >
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
                        <NativeSelect
                          value={action}
                          onChange={(e) => setAction(e.target.value)}
                        >
                          <option value="">{c.focus.unlinked}</option>
                          {goals.data
                            ?.filter(
                              (g) =>
                                g.status === "active" &&
                                (!params.get("goal") ||
                                  g.id === params.get("goal")),
                            )
                            .map((g) => (
                              <optgroup label={g.title} key={g.id}>
                                {g.actions.map((a) => (
                                  <option value={a.id} key={a.id}>
                                    {a.title}
                                  </option>
                                ))}
                              </optgroup>
                            ))}
                        </NativeSelect>
                      </Field>
                      <Field label={c.focus.duration}>
                        <Input
                          type="number"
                          required
                          min={1}
                          max={240}
                          value={duration}
                          onChange={(e) => setDuration(Number(e.target.value))}
                        />
                      </Field>
                    </div>
                    <Button
                      className="primary"
                      disabled={busy || !online || active.isPending}
                    >
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
          </CardContent>
        </Card>
        <div className="focus-session-aside">
          <Card>
            <CardContent className="pt-6">
              <BlockingStatus
                timezone={user!.timezone}
                domains={
                  session
                    ? session.blocklist_snapshot || []
                    : blocklists.data?.find((list) => list.is_default)
                        ?.domains || []
                }
              />
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <h2>{c.focus.history}</h2>
            </CardHeader>
            <CardContent>
              {history.data?.items.length ? (
                <div className="session-history focus-history">
                  {history.data.items.map((s) => (
                    <div key={s.id} className="session-row">
                      <div>
                        <strong>{s.title || c.focus.unlinked}</strong>
                        <small>
                          {new Date(s.started_at).toLocaleDateString(
                            undefined,
                            {
                              timeZone: user!.timezone,
                            },
                          )}{" "}
                          · {clock(s.started_at, user!.timezone)}
                        </small>
                      </div>
                      <span>{minutes(s.actual_minutes ?? 0)}</span>
                      <Button
                        onClick={() => {
                          setEnding(s);
                          setStopTime(s.ended_at || s.ends_at);
                          setRating(s.self_rating || 0);
                        }}
                        className="rating-button"
                      >
                        <Badge variant="outline">
                          {s.self_rating
                            ? `${s.self_rating} / 5`
                            : c.focus.noRating}
                        </Badge>
                      </Button>
                    </div>
                  ))}
                </div>
              ) : (
                <Empty title={c.focus.none} />
              )}
            </CardContent>
          </Card>
        </div>
      </div>
      {ending && (
        <Modal
          titleId="rating-title"
          onClose={() => {
            setEnding(null);
            setRating(0);
          }}
        >
          <h2 id="rating-title">{c.focus.rate}</h2>
          <p className="workflow-muted">{w.selfRatingNote}</p>
          <SubmitForm
            onSubmit={async () => {
              const body = {
                self_rating: rating || null,
                ended_at: stopTime || ending.ends_at,
              };
              if (online) {
                await api(`/focus/${ending.id}/end`, "POST", body);
                await client.invalidateQueries();
              } else {
                await queueWrite(`/focus/${ending.id}/end`, body);
                client.setQueryData([user!.id, "/focus/active"], null);
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
                  <Button
                    type="button"
                    onClick={() => {
                      setEnding(null);
                      setRating(0);
                    }}
                  >
                    {c.focus.skipRating}
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
    </div>
  );
}
