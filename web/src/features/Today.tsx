import { Link, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Play, Plus,Target,CalendarDays,Clock3 } from "lucide-react";
import { copy as c } from "../copy/en";
import { useAuth } from "../lib/auth";
import { useData, useOnline } from "../lib/hooks";
import { api } from "../api/client";
import type {
  Block,
  Goal,
  Trajectory,
  FocusStats,
  FocusSession,
} from "../api/types";
import { dateKey, weekStart, clock, minutes,addDays } from "../lib/time";
import {MetricCard} from "../components/ui/MetricCard";
import { Button } from "../components/ui/Button";
import { Empty, Notice } from "../components/ui/Forms";
import { useState } from "react";
export function Today() {
  const { user } = useAuth();
  const timezone = user!.timezone;
  const today = dateKey(new Date(), timezone);
  const blocks = useData<Block[]>(`/plan/week?start=${weekStart(today)}`);
  const goals = useData<Goal[]>("/goals");
  const trajectories = useData<Trajectory[]>("/trajectory");
  const stats = useData<FocusStats>(`/focus/stats?from=${today}&to=${today}`);
  const active = useData<FocusSession | null>("/focus/active");
  const activeGoals=(goals.data||[]).filter(g=>g.status==="active");
  const navigate = useNavigate();
  const client = useQueryClient();
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(false);
  const online = useOnline();
  const dayBlocks = (blocks.data || [])
    .filter(
      (b) =>
        dateKey(new Date(b.start_at), timezone) === today &&
        !["proposed", "cancelled"].includes(b.status),
    )
    .sort((a, b) => a.start_at.localeCompare(b.start_at));
  async function start(block: Block) {
    setBusy(true);
    try {
      await api("/focus/start", "POST", {
        time_block_id: block.id,
        planned_minutes: block.planned_minutes,
      });
      await client.invalidateQueries();
      navigate("/focus");
    } catch (error) {
      setError(error);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <header className="content-header">
        <div>
          <h1>{c.today.title}</h1>
          <p>
            {new Intl.DateTimeFormat(undefined, {
              timeZone: timezone,
              weekday: "long",
              month: "long",
              day: "numeric",
            }).format(new Date())}
          </p>
        </div>
        <Link className="button" to="/goals/new">
          <Plus size={16} />
          {c.today.newGoal}
        </Link>
      </header>
      <Notice error={error || blocks.error || goals.error} />
      {active.data && (
        <div className="draft-toolbar">
          <span>{active.data.title || c.focus.title}</span>
          <Link className="button primary" to="/focus">
            {c.focus.resume}
          </Link>
        </div>
      )}
      <div className="stats-row today-metrics">
        <MetricCard label={c.today.goals} value={goals.data?.filter(g=>g.status==='active').length??'—'} icon={<Target size={20}/>} />
        <MetricCard label={c.today.planned} value={blocks.isPending?'—':minutes(dayBlocks.reduce((n,b)=>n+b.planned_minutes,0))} icon={<CalendarDays size={20}/>} tone="mint" />
        <MetricCard label={c.today.completed} value={stats.data?minutes(stats.data.total_minutes):'—'} icon={<Clock3 size={20}/>} tone="peach" />
      </div>
      <section className="week-overview" aria-label={c.today.week}>
        <div className="panel-heading"><h2>{c.today.week}</h2><span className="week-range">{weekStart(today)} — {addDays(weekStart(today),6)}</span></div>
        <div className="week-days">{Array.from({length:7},(_,i)=>{const key=addDays(weekStart(today),i);const date=new Date(`${key}T12:00:00`);const count=(blocks.data||[]).filter(b=>dateKey(new Date(b.start_at),timezone)===key&&!['proposed','cancelled','skipped'].includes(b.status)).length;return <Link to="/plan" key={key} className={`week-day ${key===today?'is-today':''}`} aria-current={key===today?'date':undefined} aria-label={`${new Intl.DateTimeFormat(undefined,{weekday:'long'}).format(date)} ${key}: ${c.today.blockCount(count)}`}><span className="weekday-label">{new Intl.DateTimeFormat(undefined,{weekday:'short'}).format(date)}</span><strong>{date.getDate()}</strong><span className="weekday-count">{count?c.today.blockCount(count):'—'}</span></Link>;})}</div>
      </section>
      <div className="today-layout">
      <section className="panel today-schedule">
        <div className="panel-heading">
          <h2>{c.today.upcoming}</h2>
          <Link to="/plan" className="text-link">
            {c.today.all}
            <ArrowRight size={15} />
          </Link>
        </div>
        {blocks.isPending ? (
          <p role="status">{c.loading}</p>
        ) : dayBlocks.length ? (
          <div className="schedule-list">
            {dayBlocks.map((block) => (
              <div
                key={block.id}
                className={`schedule-row ${block.status === "completed" ? "complete" : ""}`}
              >
                <div className="schedule-time">
                  {clock(block.start_at, timezone)}
                  <small>{clock(block.end_at, timezone)}</small>
                </div>
                <div className="block-line" />
                <div className="schedule-info">
                  <strong>{block.title}</strong>
                  <span>
                    {goals.data?.find((g) => g.id === block.goal_id)?.title}
                  </span>
                  <small>
                    {c.plan[block.status as keyof typeof c.plan] ||
                      block.status}{" "}
                    · {minutes(block.planned_minutes)}
                  </small>
                </div>
                {["accepted", "published"].includes(block.status) && (
                  <Button
                    onClick={() => void start(block)}
                    disabled={busy || !online}
                  >
                    <Play size={14} />
                    {c.today.start}
                  </Button>
                )}
              </div>
            ))}
          </div>
        ) : (
          <Empty title={c.today.empty} icon={<CalendarDays size={29} strokeWidth={1.4}/>}>
            <Link to="/plan" className="button primary">
              {c.today.plan}
              <ArrowRight size={15} />
            </Link>
          </Empty>
        )}
      </section>
      <section className="panel today-goals">
        <div className="panel-heading">
          <h2>{c.today.progress}</h2>
          <Link to="/goals" className="text-link">
            {c.goals.all}
            <ArrowRight size={15} />
          </Link>
        </div>
        {activeGoals.length ? (
          <div className="goal-rows">
            {activeGoals.map((goal) => (
                <GoalRow
                  key={goal.id}
                  goal={goal}
                  trajectory={trajectories.data?.find(
                    (t) => t.goal_id === goal.id,
                  )}
                />
              ))}
          </div>
        ) : (
          <Empty title={c.today.noGoals} icon={<Target size={29} strokeWidth={1.4}/>} />
        )}
      </section>
      </div>
    </>
  );
}
export function GoalRow({
  goal,
  trajectory,
}: {
  goal: Goal;
  trajectory?: Trajectory;
}) {
  const current = goal.checkins?.at(-1)?.metric_value ?? goal.metric_start;
  const fraction = Math.max(
    0,
    Math.min(
      1,
      (current - goal.metric_start) / (goal.metric_target - goal.metric_start),
    ),
  );
  return (
    <Link to={`/goals/${goal.id}`} className="goal-row">
      <div>
        <strong>{goal.title}</strong>
        <span>
          {current} / {goal.metric_target} {goal.metric_unit}
        </span>
      </div>
      <div className="goal-progress">
        <div className="progress-track">
          <i style={{ width: `${fraction * 100}%` }} />
        </div>
        <small>
          {trajectory ? c.goals[trajectory.status] : c.goals[goal.status]}
        </small>
      </div>
      <ArrowRight size={15} />
    </Link>
  );
}
