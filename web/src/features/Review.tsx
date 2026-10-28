import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  ChevronLeft,
  ChevronRight,
  Send,
  Clock3,
  ListChecks,
  Star,
} from "lucide-react";
import { copy as c } from "../copy/en";
import { useAuth } from "../lib/auth";
import { useData, useOnline } from "../lib/hooks";
import { api, streamRequest } from "../api/client";
import type { FocusStats, Goal, Reflection, Trajectory } from "../api/types";
import { addDays, dateKey, minutes, weekStart } from "../lib/time";
import { Button } from "../components/ui/Button";
import { Field, Notice, SubmitForm } from "../components/ui/Forms";
import { GoalRow } from "./Today";
import { MetricCard } from "../components/ui/MetricCard";
import { Card, CardContent, CardHeader } from "../components/primitives/card";
import { Badge } from "../components/primitives/badge";
import { Skeleton } from "../components/primitives/skeleton";
import { Textarea } from "../components/primitives/textarea";
export function Review() {
  const { user } = useAuth();
  const [week, setWeek] = useState(
    weekStart(dateKey(new Date(), user!.timezone)),
  );
  const review = useData<Reflection | null>(`/reflection/${week}`);
  const stats = useData<FocusStats>(
    `/focus/stats?from=${week}&to=${addDays(week, 6)}`,
  );
  const goals = useData<Goal[]>("/goals");
  const trajectory = useData<Trajectory[]>("/trajectory");
  return (
    <>
      <header className="content-header">
        <h1>{c.review.title}</h1>
        <div className="week-nav">
          <Button
            aria-label={c.plan.previous}
            onClick={() => setWeek(addDays(week, -7))}
          >
            <ChevronLeft size={16} />
          </Button>
          <span>{week}</span>
          <Button
            aria-label={c.plan.next}
            onClick={() => setWeek(addDays(week, 7))}
          >
            <ChevronRight size={16} />
          </Button>
        </div>
      </header>
      <Notice
        error={review.error || stats.error || goals.error || trajectory.error}
      />
      <div className="stats-row">
        <MetricCard
          label={c.review.minutes}
          value={stats.data ? minutes(stats.data.total_minutes) : "—"}
          icon={<Clock3 size={20} />}
        />
        <MetricCard
          label={c.review.sessions}
          value={stats.data?.completed_sessions ?? "—"}
          icon={<ListChecks size={20} />}
        />
        <MetricCard
          label={c.focus.rating}
          value={
            stats.data?.average_rating
              ? `${stats.data.average_rating.toFixed(1)} / 5`
              : "—"
          }
          icon={<Star size={20} />}
        />
      </div>
      <div className="detail-columns">
        <Card>
          <CardContent className="pt-6">
            {review.isPending ? (
              <div role="status" aria-label={c.loading} className="space-y-4">
                <Skeleton className="h-24 w-full" />
                <Skeleton className="h-24 w-full" />
              </div>
            ) : (
              <ReflectionForm key={week} week={week} initial={review.data} />
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <h2>{c.review.trajectories}</h2>
          </CardHeader>
          <CardContent>
            {goals.data
              ?.filter((g) => g.status === "active")
              .map((goal) => (
                <GoalRow
                  key={goal.id}
                  goal={goal}
                  trajectory={trajectory.data?.find(
                    (t) => t.goal_id === goal.id,
                  )}
                />
              ))}
          </CardContent>
        </Card>
      </div>
    </>
  );
}
function ReflectionForm({
  week,
  initial,
}: {
  week: string;
  initial?: Reflection | null;
}) {
  const [values, setValues] = useState<Reflection>(
    initial || { wins: "", misses: "", adjustments: "" },
  );
  const [saved, setSaved] = useState(false);
  const online = useOnline();
  const client = useQueryClient();
  return (
    <SubmitForm
      onSubmit={async () => {
        await api(`/reflection/${week}`, "POST", values);
        await client.invalidateQueries();
        setSaved(true);
      }}
    >
      {(busy) => (
        <>
          {(["wins", "misses", "adjustments"] as const).map((key) => (
            <Field key={key} label={c.review[key]}>
              <Textarea
                rows={4}
                value={values[key]}
                onChange={(e) => {
                  setValues({ ...values, [key]: e.target.value });
                  setSaved(false);
                }}
                disabled={!online}
              />
            </Field>
          ))}
          <div className="form-footer">
            <Button className="primary" disabled={busy || !online}>
              {busy ? c.saving : c.review.save}
            </Button>
            {saved && (
              <Badge variant="outline" role="status">
                {c.saved}
              </Badge>
            )}
          </div>
        </>
      )}
    </SubmitForm>
  );
}
interface Message {
  role: "user" | "assistant";
  content: string;
}
export function Coach() {
  const status = useData<{ configured: boolean; enabled: boolean }>(
    "/coach/status",
  );
  const [messages, setMessages] = useState<Message[]>([]);
  const [text, setText] = useState("");
  const [consent, setConsent] = useState(false);
  const [error, setError] = useState<unknown>();
  const [pending, setPending] = useState(false);
  const online = useOnline();
  async function send() {
    setPending(true);
    setError(undefined);
    const next: Message[] = [...messages, { role: "user", content: text }];
    setMessages([...next, { role: "assistant", content: "" }]);
    setText("");
    try {
      const response = await streamRequest("/coach/chat", {
        messages: next.slice(-20),
        include_context: consent,
      });
      const reader = response.body?.getReader();
      if (!reader) throw new Error(c.requestFailed);
      const decoder = new TextDecoder();
      let buffer = "";
      let answer = "";
      for (;;) {
        const part = await reader.read();
        if (part.done) break;
        buffer += decoder.decode(part.value, { stream: true });
        const events = buffer.split("\n\n");
        buffer = events.pop() || "";
        for (const event of events) {
          const row = event
            .split("\n")
            .find((line) => line.startsWith("data: "));
          if (!row) continue;
          const data = JSON.parse(row.slice(6)) as {
            text?: string;
            message?: string;
          };
          if (event.includes("event: error"))
            throw new Error(data.message || c.requestFailed);
          if (data.text) {
            answer += data.text;
            setMessages([...next, { role: "assistant", content: answer }]);
          }
        }
      }
    } catch (error) {
      setError(error);
      setMessages(next);
    } finally {
      setPending(false);
    }
  }
  return (
    <>
      <header className="content-header">
        <h1>{c.coach.title}</h1>
      </header>
      <div className="coach-layout">
        <Card className="conversation">
          <CardContent className="pt-6">
            <Notice error={error || status.error} />
            {status.data && !status.data.enabled ? (
              <p className="muted">{c.coach.disabled}</p>
            ) : status.data && !status.data.configured ? (
              <p className="muted">{c.coach.unconfigured}</p>
            ) : null}
            <div className="messages" aria-live="polite">
              {messages.map((m, i) => (
                <div key={i} className={`message ${m.role}`}>
                  <span>{m.role === "user" ? c.coach.you : c.coach.title}</span>
                  <p>{m.content || c.loading}</p>
                </div>
              ))}
            </div>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void send();
              }}
            >
              <Field label={c.coach.prompt}>
                <Textarea
                  rows={3}
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  required
                  maxLength={4000}
                  placeholder={c.coach.placeholder}
                  disabled={
                    pending ||
                    !online ||
                    !status.data?.configured ||
                    !status.data?.enabled
                  }
                />
              </Field>
              <Button
                className="primary"
                disabled={
                  pending ||
                  !online ||
                  !status.data?.configured ||
                  !status.data?.enabled
                }
              >
                <Send size={15} />
                {c.coach.send}
              </Button>
            </form>
          </CardContent>
        </Card>
        <Card className="coach-privacy" role="complementary">
          <CardContent className="pt-6">
            <p>{c.coach.disclosure}</p>
            <label className="checkbox">
              <input
                type="checkbox"
                checked={consent}
                onChange={(e) => setConsent(e.target.checked)}
              />
              {c.coach.consent}
            </label>
          </CardContent>
        </Card>
      </div>
    </>
  );
}
