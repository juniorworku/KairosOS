import { useState } from "react";
import { api } from "../api/client";
import type { PlanChange } from "../api/agenda";
import { copy as c, agendaCopy as a } from "../copy/en";
import { Button } from "../components/primitives/button";
import { Card, CardHeader, CardContent } from "../components/primitives/card";
import { Badge } from "../components/primitives/badge";
import { ArrowRight, Minus } from "lucide-react";
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
    <Card
      role="region"
      className="agenda-changes"
      id="plan-changes"
      aria-label={a.changes}
    >
      <CardHeader>
        <h2>{a.changes}</h2>
      </CardHeader>
      <CardContent>
        <Notice error={error} />
        {changes.map((change) => (
          <article className="agenda-change" key={change.id}>
            <div>
              <Badge
                variant="outline"
                className={`agenda-change-badge agenda-change-${change.operation}`}
              >
                {change.operation === "move" ? (
                  <ArrowRight size={12} aria-hidden="true" />
                ) : (
                  <Minus size={12} aria-hidden="true" />
                )}
                {change.operation === "move" ? a.move : a.remove}
              </Badge>
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
                variant="outline"
                type="button"
                disabled={!online || !!pending}
                onClick={() => void decide(change.id, "dismiss")}
              >
                {a.dismiss}
              </Button>
              <Button
                variant="default"
                type="button"
                disabled={!online || !!pending}
                onClick={() => void decide(change.id, "accept")}
              >
                {pending === change.id ? c.saving : a.apply}
              </Button>
            </div>
          </article>
        ))}
      </CardContent>
    </Card>
  );
}
