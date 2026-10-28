import { useState } from "react";
import { api } from "../api/client";
import type { PlanChange, NotedBlock } from "../api/agenda";
import { copy as c, agendaCopy as a } from "../copy/en";
import { Button } from "../components/primitives/button";
import { Card, CardHeader, CardContent } from "../components/primitives/card";
import { Badge } from "../components/primitives/badge";
import { ArrowRight, Minus } from "lucide-react";
import { Notice } from "../components/ui/Forms";
import { clock, dateKey } from "../lib/time";

export function AgendaChanges({
  changes,
  additions = [],
  timezone,
  online,
  onChange,
}: {
  changes: PlanChange[];
  additions?: NotedBlock[];
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
  async function decideAddition(ids: string[], keep: boolean) {
    setPending(ids[0]);
    setError(undefined);
    try {
      if (keep) await api("/plan/accept", "POST", { block_ids: ids });
      else for (const id of ids) await api(`/blocks/${id}`, "DELETE");
      await onChange();
    } catch (error) {
      // A refresh also reconciles a partially completed multi-item discard.
      setError(error);
      await onChange();
    } finally {
      setPending("");
    }
  }
  function when(start: string, end: string) {
    return `${dateKey(new Date(start), timezone)} · ${clock(start, timezone)}–${clock(end, timezone)}`;
  }
  if (!changes.length && !additions.length && !error) return null;
  return (
    <Card
      role="region"
      className="agenda-changes"
      id="plan-changes"
      aria-label={a.changes}
    >
      <CardHeader>
        <div className="agenda-review-heading">
          <div>
            <h2>Review draft</h2>
            <p className="form-hint">
              {additions.length} added ·{" "}
              {changes.filter((change) => change.operation === "move").length}{" "}
              moved ·{" "}
              {changes.filter((change) => change.operation === "remove").length}{" "}
              removed
            </p>
          </div>
          {additions.length > 0 && (
            <Button
              variant="outline"
              disabled={!online || !!pending}
              onClick={() =>
                void decideAddition(
                  additions.map((block) => block.id),
                  true,
                )
              }
            >
              {c.plan.accept}
            </Button>
          )}
        </div>
        <p className="form-hint">
          Changes stay in preview until you keep them. Keeping a draft does not
          publish it to Google Calendar.
        </p>
      </CardHeader>
      <CardContent>
        <Notice error={error} />
        {additions.map((block) => (
          <article className="agenda-change" key={block.id}>
            <div>
              <Badge variant="outline">Added</Badge>
              <h3>{block.title}</h3>
              <p>{when(block.start_at, block.end_at)}</p>
              {block.reason && <p className="form-hint">{block.reason}</p>}
            </div>
            <div className="button-row">
              <Button
                variant="outline"
                disabled={!online || !!pending}
                aria-label={`Discard ${block.title}`}
                onClick={() => void decideAddition([block.id], false)}
              >
                Discard
              </Button>
              <Button
                disabled={!online || !!pending}
                aria-label={`Keep ${block.title}`}
                onClick={() => void decideAddition([block.id], true)}
              >
                {pending === block.id ? c.saving : "Keep"}
              </Button>
            </div>
          </article>
        ))}
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
                Discard
              </Button>
              <Button
                variant="default"
                type="button"
                disabled={!online || !!pending}
                onClick={() => void decide(change.id, "accept")}
              >
                {pending === change.id ? c.saving : "Keep change"}
              </Button>
            </div>
          </article>
        ))}
      </CardContent>
    </Card>
  );
}
