import { useState } from "react";
import { api } from "../api/client";
import type { PlanChange } from "../api/agenda";
import { copy as c, agendaCopy as a } from "../copy/en";
import { Button } from "../components/ui/Button";
import { Notice } from "../components/ui/Forms";
import { clock, dateKey } from "../lib/time";

export function AgendaChanges({
  changes,
  timezone,
  online,
  onChange,
}: {
  changes: PlanChange[];
  timezone: string;
  online: boolean;
  onChange: () => Promise<void>;
}) {
  const [pending, setPending] = useState("");
  const [error, setError] = useState<unknown>();
  async function decide(id: string, action: "accept" | "dismiss") {
    setPending(id);
    setError(undefined);
    try {
      await api(`/plan/changes/${id}/${action}`, "POST", {});
      await onChange();
    } catch (error) {
      setError(error);
    } finally {
      setPending("");
    }
  }
  function when(start: string, end: string) {
    return `${dateKey(new Date(start), timezone)} · ${clock(start, timezone)}–${clock(end, timezone)}`;
  }
  if (!changes.length && !error) return null;
  return (
    <section
      className="panel agenda-changes"
      id="plan-changes"
      aria-label={a.changes}
    >
      <h2>{a.changes}</h2>
      <Notice error={error} />
      {changes.map((change) => (
        <article className="agenda-change" key={change.id}>
          <div>
            <span className={`status-label agenda-change-${change.operation}`}>
              {change.operation === "move" ? a.move : a.remove}
            </span>
            <h3>{change.before.title}</h3>
            {change.reason && <p className="form-hint">{change.reason}</p>}
            <dl>
              <div>
                <dt>{a.before}</dt>
                <dd>{when(change.before.start_at, change.before.end_at)}</dd>
              </div>
              {change.after && (
                <div>
                  <dt>{a.after}</dt>
                  <dd>{when(change.after.start_at, change.after.end_at)}</dd>
                </div>
              )}
            </dl>
          </div>
          <div className="button-row">
            <Button
              type="button"
              disabled={!online || !!pending}
              onClick={() => void decide(change.id, "dismiss")}
            >
              {a.dismiss}
            </Button>
            <Button
              type="button"
              className="primary"
              disabled={!online || !!pending}
              onClick={() => void decide(change.id, "accept")}
            >
              {pending === change.id ? c.saving : a.apply}
            </Button>
          </div>
        </article>
      ))}
    </section>
  );
}
