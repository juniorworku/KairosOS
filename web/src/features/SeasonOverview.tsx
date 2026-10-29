import { useEffect, useId, useState } from "react";
import { Link } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowRight, CalendarDays, Plus } from "lucide-react";
import { api } from "../api/client";
import type { Block, Goal, Season, Trajectory } from "../api/types";
import { copy as c } from "../copy/en";
import { workflowCopy as w } from "../copy/workflow";
import { addDays, clock, dateKey } from "../lib/time";
import { Button } from "../components/ui/Button";
import { Field, SubmitForm } from "../components/ui/Forms";
import { Modal } from "../components/ui/Modal";
import { Input } from "../components/primitives/input";
import { NativeSelect } from "../components/primitives/native-select";
import { Progress } from "../components/primitives/progress";
import { Badge } from "../components/primitives/badge";
import { Skeleton } from "../components/primitives/skeleton";
import {
  acceptedActions,
  calendarDays,
  outcomeEvidence,
  planDay,
  selectedSeason,
  shortDate,
} from "./workflow-data";
import "./season-workflow.css";

export function SeasonOverview({
  seasons,
  goals,
  trajectories,
  blocks,
  today,
  timezone,
  loading = false,
  online,
  through,
  initialSeason,
}: {
  seasons: Season[];
  goals: Goal[];
  trajectories: Trajectory[];
  blocks: Block[];
  today: string;
  timezone: string;
  loading?: boolean;
  online: boolean;
  through: string;
  initialSeason?: string;
}) {
  const heading = useId();
  const client = useQueryClient();
  const [selected, setSelected] = useState(initialSeason || "");
  const [created, setCreated] = useState<Season>();
  const [creating, setCreating] = useState(false);
  const [assigning, setAssigning] = useState(false);
  useEffect(() => {
    if (created && seasons.some((season) => season.id === created.id))
      setCreated(undefined);
  }, [created, seasons]);
  const list =
    created && !seasons.some((season) => season.id === created.id)
      ? [...seasons, created]
      : seasons;
  const current =
    list.find((season) => season.id === selected) ||
    selectedSeason(list, today);
  const inSeason = current
    ? goals.filter(
        (goal) => goal.season_id === current.id && goal.status !== "dropped",
      )
    : [];
  const available = goals.filter(
    (goal) => !goal.season_id && goal.status !== "dropped",
  );
  const total = current
    ? calendarDays(current.start_date, current.end_date) + 1
    : 0;
  const elapsed = current
    ? Math.max(0, Math.min(total, calendarDays(current.start_date, today)))
    : 0;
  const remaining = current ? calendarDays(today, current.end_date) : 0;
  const countdown = !current
    ? ""
    : current.status === "done"
      ? w.markedComplete
      : today < current.start_date
        ? w.startsIn(calendarDays(today, current.start_date))
        : remaining === 0
          ? w.endsToday
          : remaining > 0
            ? w.daysLeft(remaining)
            : w.endedOn(shortDate(current.end_date));
  const upcoming = acceptedActions(blocks).filter(
    (block) => Date.parse(block.end_at) > Date.now(),
  );
  return (
    <section className="season-overview" aria-labelledby={heading}>
      <header className="season-heading">
        <div>
          <p className="workflow-eyebrow">
            {current &&
            (today < current.start_date ||
              today > current.end_date ||
              current.status === "done")
              ? w.season
              : w.currentSeason}
          </p>
          <h2 id={heading}>{current?.name || w.noSeason}</h2>
        </div>
        <div className="season-controls">
          {list.length > 1 && (
            <Field label={w.chooseSeason}>
              <NativeSelect
                value={current?.id || ""}
                onChange={(event) => setSelected(event.target.value)}
              >
                {list.map((season) => (
                  <option key={season.id} value={season.id}>
                    {season.name}
                  </option>
                ))}
              </NativeSelect>
            </Field>
          )}
          <Button
            type="button"
            size="sm"
            disabled={!online}
            onClick={() => setCreating(true)}
          >
            <Plus size={14} />
            {w.createSeason}
          </Button>
        </div>
      </header>
      {loading ? (
        <div role="status" aria-label={w.loadingSeason}>
          <Skeleton className="h-20 w-full" />
        </div>
      ) : current ? (
        <>
          <div className="season-dates">
            <span>
              <CalendarDays size={14} />
              <time dateTime={current.start_date}>
                {shortDate(current.start_date)}
              </time>{" "}
              —{" "}
              <time dateTime={current.end_date}>
                {shortDate(current.end_date)}
              </time>
            </span>
            <strong>{countdown}</strong>
          </div>
          <div className="season-timeline">
            <Progress
              value={total ? (elapsed / total) * 100 : 0}
              aria-label={w.seasonTime}
            />
            <span>
              {today < current.start_date
                ? w.startsIn(calendarDays(today, current.start_date))
                : w.dayOf(Math.min(total, elapsed + 1), total)}
            </span>
          </div>
          {inSeason.length ? (
            <div className="season-goals">
              {inSeason.map((goal) => {
                const trajectory = trajectories.find(
                  (item) => item.goal_id === goal.id,
                );
                const evidence = outcomeEvidence(goal, trajectory);
                const next = upcoming.find(
                  (block) => block.goal_id === goal.id,
                );
                return (
                  <div className="season-goal" key={goal.id}>
                    <div className="season-goal-name">
                      <Link to={`/goals/${goal.id}`}>
                        {goal.title}
                        <ArrowRight size={13} />
                      </Link>
                      <span className="season-goal-measure">
                        {evidence.current} / {goal.metric_target}{" "}
                        {goal.metric_unit}
                      </span>
                      <Badge variant="outline">
                        {goal.status !== "active"
                          ? c.goals[goal.status]
                          : trajectory
                            ? c.goals[trajectory.status]
                            : c.goals.active}
                      </Badge>
                    </div>
                    <div className="season-goal-pace">
                      <div className="season-pace-track">
                        <Progress
                          value={evidence.fraction * 100}
                          aria-label={`${goal.title}: ${w.recorded}`}
                        />
                        {trajectory && (
                          <span
                            className="season-expected-marker"
                            style={{
                              left: `${Math.max(0, Math.min(1, trajectory.expected_fraction)) * 100}%`,
                            }}
                            aria-hidden="true"
                          />
                        )}
                      </div>
                      <p>
                        {evidence.checkin
                          ? `${w.recorded} ${Math.round(evidence.fraction * 100)}%`
                          : w.noCheckin}
                        {trajectory
                          ? ` · ${w.expected} ${Math.round(trajectory.expected_fraction * 100)}%`
                          : ` · ${w.paceUnavailable}`}
                      </p>
                    </div>
                    <div className="season-goal-next">
                      {next ? (
                        <Link
                          to={planDay(
                            dateKey(new Date(next.start_at), timezone),
                            goal.id,
                            next.id,
                          )}
                        >
                          {next.title}
                          <span>
                            {shortDate(
                              dateKey(new Date(next.start_at), timezone),
                            )}{" "}
                            · {clock(next.start_at, timezone)}
                          </span>
                        </Link>
                      ) : (
                        <>
                          <span>{w.noAcceptedThrough(shortDate(through))}</span>
                          <Link to={planDay(today)}>
                            {w.planTime}
                            <ArrowRight size={12} />
                          </Link>
                        </>
                      )}
                    </div>
                    <Link
                      className="season-checkin"
                      to={`/goals/${goal.id}#check-in`}
                    >
                      {w.recordProgress}
                    </Link>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="season-empty">
              <strong>{w.noSeasonGoals}</strong>
              <p>{w.seasonGoalsHint}</p>
            </div>
          )}
          <footer className="season-footer">
            <Link
              to={`/goals/new?season=${encodeURIComponent(current.id)}`}
              className="text-link"
            >
              {w.addSeasonGoal}
              <ArrowRight size={14} />
            </Link>
            {available.length > 0 && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                disabled={!online}
                onClick={() => setAssigning(true)}
              >
                {w.addExisting}
              </Button>
            )}
          </footer>
        </>
      ) : (
        <p className="season-empty-copy">{w.noSeasonBody}</p>
      )}
      {creating && (
        <CreateSeason
          today={today}
          onClose={() => setCreating(false)}
          onCreated={async (season) => {
            setCreated(season);
            setSelected(season.id);
            setCreating(false);
            await client.invalidateQueries();
          }}
        />
      )}
      {assigning && current && (
        <AssignGoal
          goals={available}
          season={current}
          onClose={() => setAssigning(false)}
          onSaved={async () => {
            await client.invalidateQueries();
            setAssigning(false);
          }}
        />
      )}
    </section>
  );
}

function CreateSeason({
  today,
  onClose,
  onCreated,
}: {
  today: string;
  onClose: () => void;
  onCreated: (season: Season) => Promise<void>;
}) {
  const [name, setName] = useState("");
  const [start, setStart] = useState(today);
  const [end, setEnd] = useState(addDays(today, 83));
  return (
    <Modal titleId="season-create-title" onClose={onClose}>
      <h2 id="season-create-title">{w.createSeason}</h2>
      <p className="form-hint">{w.seasonHint}</p>
      <SubmitForm
        onSubmit={async () => {
          const season = await api<Season>("/seasons", "POST", {
            name,
            start_date: start,
            end_date: end,
            status: start > today ? "planned" : end < today ? "done" : "active",
          });
          await onCreated(season);
        }}
      >
        {(busy) => (
          <>
            <Field label={w.seasonName}>
              <Input
                autoFocus
                required
                maxLength={200}
                value={name}
                onChange={(event) => setName(event.target.value)}
              />
            </Field>
            <div className="form-grid">
              <Field label={w.seasonStarts}>
                <Input
                  type="date"
                  required
                  value={start}
                  onChange={(event) => setStart(event.target.value)}
                />
              </Field>
              <Field label={w.seasonEnds}>
                <Input
                  type="date"
                  required
                  min={start}
                  value={end}
                  onChange={(event) => setEnd(event.target.value)}
                />
              </Field>
            </div>
            <div className="button-row">
              <Button type="button" disabled={busy} onClick={onClose}>
                {c.cancel}
              </Button>
              <Button type="submit" className="primary" disabled={busy}>
                {busy ? c.saving : w.createSeason}
              </Button>
            </div>
          </>
        )}
      </SubmitForm>
    </Modal>
  );
}

function AssignGoal({
  goals,
  season,
  onClose,
  onSaved,
}: {
  goals: Goal[];
  season: Season;
  onClose: () => void;
  onSaved: () => Promise<void>;
}) {
  const [selected, setSelected] = useState(goals[0]?.id || "");
  return (
    <Modal titleId="season-assign-title" onClose={onClose}>
      <h2 id="season-assign-title">{w.addExisting}</h2>
      <SubmitForm
        onSubmit={async () => {
          const goal = goals.find((item) => item.id === selected);
          if (!goal) return;
          await api(`/goals/${goal.id}`, "PATCH", {
            ...goal,
            season_id: season.id,
          });
          await onSaved();
        }}
      >
        {(busy) => (
          <>
            <Field label={w.chooseGoal}>
              <NativeSelect
                value={selected}
                required
                onChange={(event) => setSelected(event.target.value)}
              >
                {goals.map((goal) => (
                  <option key={goal.id} value={goal.id}>
                    {goal.title}
                  </option>
                ))}
              </NativeSelect>
            </Field>
            <div className="button-row">
              <Button type="button" onClick={onClose} disabled={busy}>
                {c.cancel}
              </Button>
              <Button
                type="submit"
                className="primary"
                disabled={busy || !selected}
              >
                {busy ? c.saving : w.assignGoal}
              </Button>
            </div>
          </>
        )}
      </SubmitForm>
    </Modal>
  );
}
