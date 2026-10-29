import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Play, Plus, Check } from "lucide-react";
import { copy as c, agendaCopy as a } from "../copy/en";
import { workflowCopy as w } from "../copy/workflow";
import { useAuth } from "../lib/auth";
import { useData, useOnline } from "../lib/hooks";
import { api } from "../api/client";
import type {
  Block,
  Goal,
  Trajectory,
  FocusStats,
  FocusSession,
  Season,
  Reflection,
} from "../api/types";
import type { CalendarStatus } from "./Plan";
import type { AgendaItem, Task } from "../api/agenda";
import { dateKey, weekStart, clock, minutes, addDays } from "../lib/time";
import { Button } from "../components/ui/Button";
import { Notice } from "../components/ui/Forms";
import { Badge } from "../components/primitives/badge";
import { Progress } from "../components/primitives/progress";
import { Skeleton } from "../components/primitives/skeleton";
import { SeasonOverview } from "./SeasonOverview";
import { nextAccepted, planDay, shortDate } from "./workflow-data";
import "./season-workflow.css";

export function Today() {
  const { user } = useAuth();
  const timezone = user!.timezone;
  const [now, setNow] = useState(Date.now());
  const today = dateKey(new Date(now), timezone);
  const week = weekStart(today);
  const blocks = useData<Block[]>(`/plan/week?start=${week}`);
  const following = useData<Block[]>(`/plan/week?start=${addDays(week, 7)}`);
  const agenda = useData<AgendaItem[]>(
    `/agenda?start=${today}&end=${addDays(today, 1)}`,
  );
  const tasks = useData<Task[]>("/tasks");
  const calendar = useData<CalendarStatus>("/calendar/status");
  const seasons = useData<Season[]>("/seasons");
  const goals = useData<Goal[]>("/goals");
  const trajectories = useData<Trajectory[]>("/trajectory");
  const stats = useData<FocusStats>(`/focus/stats?from=${today}&to=${today}`);
  const active = useData<FocusSession | null>("/focus/active");
  const review = useData<Reflection | null>(`/reflection/${week}`);
  const navigate = useNavigate();
  const client = useQueryClient();
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(false);
  const online = useOnline();
  const loadedBlocks = [...(blocks.data || []), ...(following.data || [])];
  const activeGoals = (goals.data || []).filter(
    (goal) => goal.status === "active",
  );
  const running =
    active.data && Date.parse(active.data.ends_at) > now ? active.data : null;
  const expired = Boolean(
    active.data && Date.parse(active.data.ends_at) <= now,
  );
  const next = nextAccepted(loadedBlocks, now, today, timezone);
  const proposed = loadedBlocks.filter(
    (block) => block.status === "proposed",
  ).length;
  const dayBlocks = (blocks.data || []).filter(
    (block) =>
      dateKey(new Date(block.start_at), timezone) === today &&
      !["proposed", "cancelled", "skipped"].includes(block.status),
  );
  const dayAgenda = [...(agenda.data || [])]
    .filter(
      (item) => !["cancelled", "proposed", "skipped"].includes(item.status),
    )
    .sort(
      (a, b) =>
        Number(b.all_day) - Number(a.all_day) ||
        a.start_at.localeCompare(b.start_at),
    );
  const dueTasks = (tasks.data || [])
    .filter(
      (task) =>
        task.status !== "done" && task.due_date && task.due_date <= today,
    )
    .sort((a, b) => (a.due_date || "").localeCompare(b.due_date || ""));
  const remaining = running
    ? Math.max(0, Math.ceil((Date.parse(running.ends_at) - now) / 1000))
    : 0;
  const { refetch } = active;
  const { refetch: refetchCalendar } = calendar;
  const isRunning = Boolean(running);
  useEffect(() => {
    if (online && agenda.dataUpdatedAt) void refetchCalendar();
  }, [online, agenda.dataUpdatedAt, refetchCalendar]);
  useEffect(() => {
    const timer = window.setInterval(
      () => setNow(Date.now()),
      isRunning ? 1000 : 60000,
    );
    return () => clearInterval(timer);
  }, [isRunning]);
  useEffect(() => {
    if (expired && online) void refetch();
  }, [expired, online, refetch]);
  async function start(block: Block) {
    setBusy(true);
    setError(undefined);
    try {
      await api("/focus/start", "POST", {
        time_block_id: block.id,
        planned_minutes: Math.min(240, Math.max(1, block.planned_minutes)),
      });
      await client.invalidateQueries();
      navigate("/focus");
    } catch (failure) {
      setError(failure);
    } finally {
      setBusy(false);
    }
  }
  const ownerGoal = running?.goal_id
    ? goals.data?.find((goal) => goal.id === running.goal_id)
    : next
      ? goals.data?.find((goal) => goal.id === next.goal_id)
      : undefined;
  return (
    <>
      <header className="content-header workflow-page-header">
        <div>
          <h1>{c.today.title}</h1>
          <p>
            {new Intl.DateTimeFormat(undefined, {
              timeZone: timezone,
              weekday: "long",
              month: "long",
              day: "numeric",
            }).format(new Date(now))}
          </p>
        </div>
        {online && (
          <Link className="button" to="/goals/new">
            <Plus size={15} />
            {c.today.newGoal}
          </Link>
        )}
      </header>
      <Notice
        error={
          error ||
          blocks.error ||
          following.error ||
          agenda.error ||
          tasks.error ||
          seasons.error ||
          goals.error ||
          trajectories.error ||
          stats.error ||
          active.error ||
          review.error ||
          calendar.error
        }
      />
      <section
        className={`today-action-hero ${running ? "is-running" : ""}`}
        aria-labelledby="today-action-title"
      >
        {active.isPending || blocks.isPending || goals.isPending ? (
          <div role="status" aria-label={c.loading}>
            <Skeleton className="h-7 w-48" />
            <Skeleton className="mt-3 h-12 w-full" />
          </div>
        ) : running ? (
          <>
            <div className="workflow-eyebrow">
              <span className="session-live-dot" />
              {w.resume}
            </div>
            <div className="today-action-body">
              <div>
                <h2 id="today-action-title">
                  {running.title || c.focus.title}
                </h2>
                {ownerGoal && (
                  <Link to={`/goals/${ownerGoal.id}`}>
                    {w.forGoal} {ownerGoal.title}
                  </Link>
                )}
              </div>
              <div className="today-live-clock" aria-label={w.remaining}>
                {Math.floor(remaining / 60)
                  .toString()
                  .padStart(2, "0")}
                :{(remaining % 60).toString().padStart(2, "0")}
                <span>{w.remaining}</span>
              </div>
            </div>
            <div className="today-action-controls">
              <Link className="button primary" to="/focus">
                <Play size={15} />
                {c.focus.resume}
              </Link>
              <Link className="text-link" to={planDay(today)}>
                {w.viewDay}
                <ArrowRight size={14} />
              </Link>
            </div>
          </>
        ) : next ? (
          <>
            <p className="workflow-eyebrow">
              {Date.parse(next.end_at) <= now ? w.earlierToday : w.nextAction}
            </p>
            <h2 id="today-action-title">{next.title}</h2>
            <div className="today-action-context">
              {ownerGoal && (
                <Link to={`/goals/${ownerGoal.id}`}>{ownerGoal.title}</Link>
              )}
              <span>
                {shortDate(dateKey(new Date(next.start_at), timezone))} ·{" "}
                {clock(next.start_at, timezone)}–{clock(next.end_at, timezone)}
              </span>
              <Badge variant="outline">
                {next.status === "published"
                  ? c.plan.published
                  : c.plan.accepted}
              </Badge>
            </div>
            <div className="today-action-controls">
              <Button
                className="primary"
                disabled={busy || !online}
                onClick={() => void start(next)}
              >
                <Play size={15} />
                {busy ? c.saving : c.today.start}
              </Button>
              <Link
                className="text-link"
                to={planDay(
                  dateKey(new Date(next.start_at), timezone),
                  next.goal_id,
                  next.id,
                )}
              >
                {w.viewDay}
                <ArrowRight size={14} />
              </Link>
              {ownerGoal && (
                <Link
                  className="text-link"
                  to={`/goals/${ownerGoal.id}#check-in`}
                >
                  {w.recordProgress}
                </Link>
              )}
            </div>
          </>
        ) : activeGoals.length ? (
          <>
            <p className="workflow-eyebrow">
              {proposed ? w.reviewDraft : w.scheduleFirst}
            </p>
            <h2 id="today-action-title">{w.noAccepted}</h2>
            <p>{proposed ? w.draftHint(proposed) : w.noAcceptedBody}</p>
            <Link className="button primary" to={planDay(today)}>
              {proposed ? w.reviewDraft : c.today.plan}
              <ArrowRight size={15} />
            </Link>
          </>
        ) : (
          <>
            <p className="workflow-eyebrow">{w.nextAction}</p>
            <h2 id="today-action-title">{w.firstGoal}</h2>
            <p>{w.firstGoalBody}</p>
            {online && (
              <Link className="button primary" to="/goals/new">
                <Plus size={15} />
                {c.today.newGoal}
              </Link>
            )}
            <p className="workflow-small">{w.calendarOptional}</p>
          </>
        )}
      </section>
      <dl className="today-evidence-strip">
        <div>
          <dt>{w.plannedToday}</dt>
          <dd>
            {blocks.isPending
              ? "—"
              : minutes(
                  dayBlocks.reduce(
                    (sum, block) => sum + block.planned_minutes,
                    0,
                  ),
                )}
          </dd>
        </div>
        <div>
          <dt>{w.loggedToday}</dt>
          <dd>{stats.data ? minutes(stats.data.total_minutes) : "—"}</dd>
        </div>
        <div>
          <dt>{w.completedBlocks}</dt>
          <dd>
            {blocks.isPending
              ? "—"
              : `${dayBlocks.filter((block) => block.status === "completed").length} / ${dayBlocks.length}`}
          </dd>
        </div>
        <div className="today-hours">
          <dt>{w.saveHours}</dt>
          <dd>
            <Link to="/settings">
              {user!.work_start}–{user!.work_end}
              <ArrowRight size={13} />
            </Link>
          </dd>
        </div>
      </dl>
      <nav className="workflow-week" aria-label={c.today.week}>
        {Array.from({ length: 7 }, (_, index) => {
          const day = addDays(week, index);
          const date = new Date(`${day}T12:00:00Z`);
          const count = (blocks.data || []).filter(
            (block) =>
              dateKey(new Date(block.start_at), timezone) === day &&
              !["proposed", "cancelled", "skipped"].includes(block.status),
          ).length;
          return (
            <Link
              to={planDay(day)}
              key={day}
              className={day === today ? "is-today" : ""}
              aria-current={day === today ? "date" : undefined}
              aria-label={`${new Intl.DateTimeFormat(undefined, { weekday: "long", timeZone: "UTC" }).format(date)} ${day}: ${c.today.blockCount(count)}`}
            >
              <span>
                {new Intl.DateTimeFormat(undefined, {
                  weekday: "short",
                  timeZone: "UTC",
                }).format(date)}
              </span>
              <strong>{date.getUTCDate()}</strong>
              <small>{count ? c.today.blockCount(count) : "—"}</small>
            </Link>
          );
        })}
      </nav>
      <div className="workflow-columns">
        <div className="workflow-main-column">
          <section
            className="today-agenda-section"
            aria-labelledby="today-schedule-title"
          >
            {calendar.data?.details_error && (
              <p className="warning-note" role="status">
                {a.detailsUnavailable}{" "}
                <Link className="text-link" to="/settings">
                  {c.settings.calendar}
                </Link>
              </p>
            )}
            <header className="workflow-section-heading">
              <h2 id="today-schedule-title">{c.today.upcoming}</h2>
              <Link to={planDay(today)} className="text-link">
                {c.today.all}
                <ArrowRight size={14} />
              </Link>
            </header>
            {agenda.isPending ? (
              <Skeleton className="h-20 w-full" />
            ) : dayAgenda.length ? (
              <div className="workflow-agenda-list">
                {dayAgenda.map((item) => {
                  const linked =
                    item.source === "block"
                      ? loadedBlocks.find(
                          (block) => block.id === item.source_id,
                        )
                      : undefined;
                  const startable =
                    linked && ["accepted", "published"].includes(linked.status);
                  return (
                    <div
                      className={`workflow-agenda-row ${item.status === "completed" || item.status === "done" ? "is-complete" : ""}`}
                      key={item.id}
                    >
                      <div className="workflow-agenda-time">
                        {item.all_day
                          ? w.allDay
                          : clock(item.start_at, timezone)}
                        {!item.all_day && (
                          <small>{clock(item.end_at, timezone)}</small>
                        )}
                      </div>
                      <div className="workflow-agenda-content">
                        <Link to={planDay(today, linked?.goal_id, linked?.id)}>
                          {item.title}
                        </Link>
                        <small>
                          {item.source === "google"
                            ? item.calendar_name || w.googleCalendar
                            : item.source === "local"
                              ? item.task_id
                                ? w.scheduledTask
                                : w.localEvent
                              : goals.data?.find(
                                  (goal) => goal.id === item.goal_id,
                                )?.title}
                        </small>
                      </div>
                      {startable && (
                        <Button
                          type="button"
                          size="sm"
                          disabled={busy || !online || Boolean(running)}
                          onClick={() => void start(linked)}
                        >
                          <Play size={13} />
                          {c.today.start}
                        </Button>
                      )}
                      {item.status === "completed" && (
                        <Check size={16} aria-label={c.goals.done} />
                      )}
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="workflow-empty-line">
                <p>{c.today.empty}</p>
                <Link to={planDay(today)} className="text-link">
                  {c.today.plan}
                  <ArrowRight size={14} />
                </Link>
              </div>
            )}
          </section>
          {dueTasks.length > 0 && (
            <section
              className="today-due-tasks"
              aria-labelledby="due-task-title"
            >
              <header className="workflow-section-heading">
                <h2 id="due-task-title">{w.dueTasks}</h2>
                <Link
                  className="text-link"
                  to={`${planDay(today)}#agenda-tasks`}
                >
                  {w.placeTasks}
                  <ArrowRight size={14} />
                </Link>
              </header>
              {dueTasks.slice(0, 3).map((task) => (
                <Link
                  className="today-due-row"
                  key={task.id}
                  to={`${planDay(today)}&task=${encodeURIComponent(task.id)}#agenda-tasks`}
                >
                  <span>{task.title}</span>
                  <small>
                    {task.due_date! < today ? w.overdue : w.dueToday}
                    {task.due_date! < today &&
                      ` · ${shortDate(task.due_date!)}`}
                  </small>
                  <ArrowRight size={13} />
                </Link>
              ))}
            </section>
          )}
          <section
            className="today-feedback"
            aria-labelledby="daily-feedback-title"
          >
            <header className="workflow-section-heading">
              <h2 id="daily-feedback-title">{w.progressLoop}</h2>
            </header>
            <p className="workflow-small">{w.progressHint}</p>
            {activeGoals.length ? (
              activeGoals.slice(0, 3).map((goal) => (
                <Link
                  className="today-checkin-link"
                  key={goal.id}
                  to={`/goals/${goal.id}#check-in`}
                >
                  <span>
                    <strong>{goal.title}</strong>
                    <small>
                      {goal.checkins?.length
                        ? `${w.latestCheckin}: ${goal.checkins.at(-1)!.metric_value} ${goal.metric_unit}`
                        : w.noCheckin}
                    </small>
                  </span>
                  <span>
                    {w.recordProgress}
                    <ArrowRight size={13} />
                  </span>
                </Link>
              ))
            ) : (
              <p className="workflow-small">{w.noActiveGoals}</p>
            )}
            <div className="today-review-link">
              <div>
                <strong>
                  {review.data?.week_start ? w.openReview : w.weeklyReview}
                </strong>
                <p>{review.data?.week_start ? w.reviewSaved : w.reviewHint}</p>
              </div>
              <Link className="button" to="/review">
                <ArrowRight size={15} />
                {review.data?.week_start ? w.openReview : w.weeklyReview}
              </Link>
            </div>
          </section>
        </div>
        <SeasonOverview
          seasons={seasons.data || []}
          goals={goals.data || []}
          trajectories={trajectories.data || []}
          blocks={loadedBlocks}
          today={today}
          timezone={timezone}
          loading={seasons.isPending || goals.isPending}
          online={online}
          through={addDays(week, 13)}
        />
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
  const range = goal.metric_target - goal.metric_start;
  const fraction = range
    ? Math.max(0, Math.min(1, (current - goal.metric_start) / range))
    : 0;
  return (
    <Link to={`/goals/${goal.id}`} className="goal-row">
      <div>
        <strong>{goal.title}</strong>
        <span>
          {current} / {goal.metric_target} {goal.metric_unit}
        </span>
      </div>
      <div className="goal-progress">
        <Progress
          value={fraction * 100}
          aria-label={goal.title}
          className="h-1.5"
        />
        <Badge variant="outline">
          {trajectory ? c.goals[trajectory.status] : c.goals[goal.status]}
        </Badge>
      </div>
      <ArrowRight size={15} />
    </Link>
  );
}
