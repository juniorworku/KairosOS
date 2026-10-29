import { useState } from "react";
import { Link } from "react-router-dom";
import type { components } from "../api/schema";
import type { FocusStats, Reflection, Goal } from "../api/types";
import { api } from "../api/client";
import { useData, useOnline } from "../lib/hooks";
import { Button } from "../components/ui/Button";
import { Notice } from "../components/ui/Forms";
import { Card, CardContent, CardHeader } from "../components/primitives/card";
import { recommendationHref } from "./workflow";
import { workflowCopy as w } from "./workflow-copy";
type Result = components["schemas"]["WeeklyReview"];
export function WeekSuggestions({
  week,
  stats,
  reflection,
  goal,
}: {
  week: string;
  stats?: FocusStats;
  reflection?: Reflection | null;
  goal?: Goal;
}) {
  const status = useData<{ configured: boolean; enabled: boolean }>(
    "/coach/status",
  );
  const online = useOnline();
  const [consent, setConsent] = useState(false);
  const [pending, setPending] = useState(false);
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState<unknown>();
  if (!status.data?.configured || !status.data.enabled) return null;
  return (
    <Card className="coach-review-suggestions">
      <CardHeader>
        <h2>{w.recommendationTitle}</h2>
      </CardHeader>
      <CardContent>
        <details>
          <summary>{w.reviewEvidence}</summary>
          <p>
            {week}: {stats?.total_minutes ?? 0} min ·{" "}
            {stats?.completed_sessions ?? 0} sessions
          </p>
          <p>{reflection?.wins}</p>
          <p>{reflection?.misses}</p>
          <p>{reflection?.adjustments}</p>
          {goal && (
            <p>
              {goal.title}: {goal.metric_name}{" "}
              {goal.checkins.at(-1)?.metric_value ?? goal.metric_start} /{" "}
              {goal.metric_target} {goal.metric_unit} (current)
            </p>
          )}
        </details>
        <p className="workflow-muted">{w.noMeasuredPatterns}</p>
        <label className="checkbox">
          <input
            type="checkbox"
            checked={consent}
            onChange={(event) => setConsent(event.target.checked)}
          />
          {w.shareReview}
        </label>
        <Button
          disabled={!consent || !stats || pending || !online}
          onClick={() => {
            setPending(true);
            setError(undefined);
            setResult(null);
            void api<Result>("/coach/weekly-review", "POST", {
              include_context: false,
              text: JSON.stringify({
                instruction: w.recommendationPrompt,
                week,
                focus: {
                  total_minutes: stats?.total_minutes,
                  completed_sessions: stats?.completed_sessions,
                  self_rating: stats?.average_rating,
                },
                reflection: reflection
                  ? {
                      wins: reflection.wins,
                      misses: reflection.misses,
                      adjustments: reflection.adjustments,
                    }
                  : null,
                goal: goal
                  ? {
                      title: goal.title,
                      metric_name: goal.metric_name,
                      current:
                        goal.checkins.at(-1)?.metric_value ?? goal.metric_start,
                      target: goal.metric_target,
                      unit: goal.metric_unit,
                    }
                  : null,
              }),
            })
              .then(setResult)
              .catch(setError)
              .finally(() => setPending(false));
          }}
        >
          {pending ? "Loading…" : w.requestReview}
        </Button>
        <Notice error={error} />
        {result && (
          <section aria-label={w.recommendationTitle}>
            <p>{result.summary}</p>
            <div className="coach-review-list">
              {result.suggestions.map((item, index) => (
                <article className="coach-review-item" key={index}>
                  <p>{item.text}</p>
                  <Button asChild variant="outline">
                    <Link to={recommendationHref(item.type, week, goal)}>
                      {item.type === "planning"
                        ? w.reviewPlan
                        : item.type === "goal"
                          ? w.openGoals
                          : item.type === "focus"
                            ? w.openFocus
                            : w.openReflection}
                    </Link>
                  </Button>
                </article>
              ))}
            </div>
            <p className="workflow-muted">{w.previewHint}</p>
          </section>
        )}
      </CardContent>
    </Card>
  );
}
