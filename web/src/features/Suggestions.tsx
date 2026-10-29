import { workflowCopy as w } from "./workflow-copy";
import "./workflow.css";
import { Card } from "../components/primitives/card";
import { useState } from "react";
import { api } from "../api/client";
import type { components } from "../api/schema";
import type { Action, Goal } from "../api/types";
import { Button } from "../components/ui/Button";
import { Notice } from "../components/ui/Forms";
import { copy as c } from "../copy/en";
import { useData, useOnline } from "../lib/hooks";

type GoalSuggestion = components["schemas"]["GoalSuggestion"];
type ActionSuggestions = components["schemas"]["ActionSuggestions"];
type ObstacleSuggestions = components["schemas"]["ObstacleSuggestions"];
type Kind = "goal" | "actions" | "obstacles";
type Proposal =
  | { kind: "goal"; value: GoalSuggestion }
  | { kind: "actions"; value: ActionSuggestions }
  | { kind: "obstacles"; value: ObstacleSuggestions };

interface Props {
  kind: Kind;
  goal: Goal;
  onUse: (patch: Partial<Goal>) => void;
}

export function Suggestions({ kind, goal, onUse }: Props) {
  const status = useData<{ configured: boolean; enabled: boolean }>(
    "/coach/status",
  );
  const online = useOnline();
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [pending, setPending] = useState(false);
  const [source, setSource] = useState("");
  const [error, setError] = useState<unknown>();

  if (!status.data?.configured || !status.data.enabled) return null;

  async function request() {
    setSource(JSON.stringify(goal));
    setPending(true);
    setError(undefined);
    setProposal(null);
    const body = {
      text: JSON.stringify({
        title: goal.title,
        outcome_statement: goal.outcome_statement,
        metric_name: goal.metric_name,
        metric_unit: goal.metric_unit,
        metric_start: goal.metric_start,
        metric_target: goal.metric_target,
        start_date: goal.start_date,
        target_date: goal.target_date,
        actions: goal.actions.map((action) => ({
          title: action.title,
          kind: action.kind,
          weekly_minutes: action.weekly_minutes_target,
        })),
      }),
      include_context: false,
    };
    try {
      if (kind === "goal") {
        const value = await api<GoalSuggestion>(
          "/coach/goal-refine",
          "POST",
          body,
        );
        setProposal({ kind, value });
      } else if (kind === "actions") {
        const value = await api<ActionSuggestions>(
          "/coach/suggest-actions",
          "POST",
          body,
        );
        setProposal({ kind, value });
      } else {
        const value = await api<ObstacleSuggestions>(
          "/coach/suggest-obstacles",
          "POST",
          body,
        );
        setProposal({ kind, value });
      }
    } catch (error) {
      setError(error);
    } finally {
      setPending(false);
    }
  }

  function useProposal() {
    if (!proposal || source !== JSON.stringify(goal)) return;
    if (proposal.kind === "goal") {
      onUse({
        outcome_statement: proposal.value.outcome_statement,
        metric_name: proposal.value.metric_name,
        metric_unit: proposal.value.metric_unit,
        metric_target: proposal.value.suggested_target,
      });
    } else if (proposal.kind === "actions") {
      const actions: Action[] = proposal.value.actions.map((action) => ({
        id: "",
        title: action.title,
        kind: action.kind,
        total_minutes_estimate: null,
        preferred_block_minutes: 60,
        min_block_minutes: 30,
        max_block_minutes: 120,
        preferred_time_of_day: "any",
        requires_deep_focus: true,
        ...goal.actions.find(
          (existing) =>
            existing.title === action.title && existing.kind === action.kind,
        ),
        weekly_minutes_target: action.weekly_minutes,
      }));
      onUse({ actions });
    } else {
      onUse({
        obstacles: proposal.value.obstacles.map((obstacle) => ({
          risk_text: obstacle.risk,
          if_cue: obstacle.if_cue,
          then_response: obstacle.then_response,
        })),
      });
    }
    setProposal(null);
  }

  return (
    <div className="suggestions" aria-busy={pending}>
      <p className="form-hint">{c.coach.suggestionHint}</p>
      <Button
        type="button"
        disabled={pending || !online || !goal.title.trim()}
        onClick={() => void request()}
      >
        {pending
          ? c.loading
          : kind === "goal"
            ? c.coach.suggestGoal
            : kind === "actions"
              ? c.coach.suggestActions
              : c.coach.suggestObstacles}
      </Button>
      <Notice error={error} />
      {proposal && (
        <Card asChild>
          <section className="panel" aria-label={c.coach.suggestions}>
            <h3>{c.coach.suggestions}</h3>
            <details>
              <summary>{w.suggestionEvidence}</summary>
              <p>{goal.title}</p>
              <p>{goal.outcome_statement}</p>
              <p>
                {goal.metric_name}: {goal.metric_start} → {goal.metric_target}{" "}
                {goal.metric_unit}
              </p>
              <p>
                {goal.start_date} – {goal.target_date}
              </p>
              {goal.actions.map((action) => (
                <p key={action.id || action.title}>
                  {action.title}: {action.weekly_minutes_target} min/week
                </p>
              ))}
            </details>
            <p className="workflow-muted">
              {source !== JSON.stringify(goal)
                ? "The form changed. Request a new suggestion before using it."
                : w.localDraft}
            </p>
            {proposal.kind === "actions" && <p>{w.replacesActions}</p>}
            {proposal.kind === "obstacles" && <p>{w.replacesObstacles}</p>}
            {proposal.kind === "goal" && (
              <div className="suggestion-diff">
                <section>
                  <h4>{w.before}</h4>
                  <p>{goal.outcome_statement}</p>
                  <p>
                    {goal.metric_name}: {goal.metric_target} {goal.metric_unit}
                  </p>
                </section>
              </div>
            )}
            {proposal.kind === "goal" ? (
              <>
                <h4>{w.after}</h4>
                <p className="body-text">{proposal.value.outcome_statement}</p>
                <p>
                  {proposal.value.metric_name}:{" "}
                  {proposal.value.suggested_target} {proposal.value.metric_unit}
                </p>
                {proposal.value.clarifying_questions.length > 0 && (
                  <ul className="plain-list">
                    {proposal.value.clarifying_questions.map(
                      (question, index) => (
                        <li key={index}>{question}</li>
                      ),
                    )}
                  </ul>
                )}
              </>
            ) : proposal.kind === "actions" ? (
              <ul className="plain-list">
                {proposal.value.actions.map((action, index) => (
                  <li key={index}>
                    <strong>{action.title}</strong>
                    <p>
                      {c.goals.form.weekly}: {action.weekly_minutes}
                    </p>
                    <p className="body-text">{action.rationale}</p>
                  </li>
                ))}
              </ul>
            ) : (
              <ul className="plain-list">
                {proposal.value.obstacles.map((obstacle, index) => (
                  <li key={index}>
                    <strong>{obstacle.risk}</strong>
                    <p>
                      {c.goals.if} {obstacle.if_cue}
                    </p>
                    <p>
                      {c.goals.then} {obstacle.then_response}
                    </p>
                  </li>
                ))}
              </ul>
            )}
            <div className="button-row">
              <Button type="button" onClick={() => setProposal(null)}>
                {c.cancel}
              </Button>
              <Button
                type="button"
                className="primary"
                onClick={useProposal}
                disabled={source !== JSON.stringify(goal)}
              >
                {c.coach.useSuggestions}
              </Button>
            </div>
          </section>
        </Card>
      )}
    </div>
  );
}
