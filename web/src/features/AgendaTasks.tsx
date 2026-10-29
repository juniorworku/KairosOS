import { Input } from "../components/primitives/input";
import { Textarea } from "../components/primitives/textarea";
import { NativeSelect } from "../components/primitives/native-select";
import { Card } from "../components/primitives/card";
import { useEffect, useState } from "react";
import { CalendarPlus, Check, Pencil, Plus } from "lucide-react";
import { api } from "../api/client";
import type { Task } from "../api/agenda";
import type { Goal } from "../api/types";
import { copy as c, agendaCopy as a } from "../copy/en";
import { Button } from "../components/ui/Button";
import { Empty, Field, Notice, SubmitForm } from "../components/ui/Forms";
import { Modal } from "../components/ui/Modal";

export function AgendaTasks({
  tasks,
  goals,
  online,
  pending,
  error,
  onChange,
  onSchedule,
  selectedTaskId,
}: {
  tasks: Task[];
  goals: Goal[];
  online: boolean;
  pending: boolean;
  error: unknown;
  onChange: () => Promise<void>;
  onSchedule: (task: Task) => void;
  selectedTaskId?: string;
}) {
  const [editing, setEditing] = useState<Task | "new" | null>(null);
  const [failure, setFailure] = useState<unknown>();
  const [changing, setChanging] = useState("");
  async function toggle(task: Task) {
    setChanging(task.id);
    setFailure(undefined);
    try {
      await api(`/tasks/${task.id}`, "PATCH", {
        status: task.status === "done" ? "todo" : "done",
      });
      await onChange();
    } catch (error) {
      setFailure(error);
    } finally {
      setChanging("");
    }
  }
  const selectedExists = tasks.some((task) => task.id === selectedTaskId);
  useEffect(() => {
    if (!selectedTaskId || !selectedExists) return;
    const target = document.getElementById(`agenda-task-${selectedTaskId}`);
    target?.scrollIntoView({ block: "nearest" });
    target?.focus({ preventScroll: true });
  }, [selectedTaskId, selectedExists]);
  const todo = tasks.filter((task) => task.status !== "done");
  function row(task: Task) {
    return (
      <div
        id={`agenda-task-${task.id}`}
        tabIndex={-1}
        aria-label={task.title}
        className={`agenda-task ${task.status === "done" ? "is-done" : ""} ${selectedTaskId === task.id ? "is-context-task" : ""}`}
        key={task.id}
      >
        <Button
          type="button"
          className="agenda-task-check icon-button"
          aria-label={`${task.status === "done" ? a.markTodo : a.markDone}: ${task.title}`}
          aria-pressed={task.status === "done"}
          disabled={!online || changing === task.id}
          onClick={() => void toggle(task)}
        >
          <Check size={14} />
        </Button>
        <div className="agenda-task-text">
          <strong>{task.title}</strong>
          {task.due_date && (
            <small>
              {a.due}: {task.due_date}
            </small>
          )}
          {task.notes && <p>{task.notes}</p>}
        </div>
        <div className="agenda-task-actions">
          <Button
            type="button"
            className="icon-button"
            aria-label={`${c.edit}: ${task.title}`}
            disabled={!online}
            onClick={() => setEditing(task)}
          >
            <Pencil size={14} />
          </Button>
          {task.status !== "done" && (
            <Button
              type="button"
              className="icon-button"
              aria-label={`${a.scheduleTask}: ${task.title}`}
              disabled={!online}
              onClick={() => onSchedule(task)}
            >
              <CalendarPlus size={15} />
            </Button>
          )}
        </div>
      </div>
    );
  }
  return (
    <Card asChild>
      <aside
        id="agenda-tasks"
        className="panel agenda-tasks"
        aria-label={a.tasks}
      >
        <div className="panel-heading">
          <h2>{a.tasks}</h2>
          <Button
            type="button"
            className="icon-button"
            aria-label={a.addTask}
            disabled={!online}
            onClick={() => setEditing("new")}
          >
            <Plus size={18} />
          </Button>
        </div>
        <Notice error={error || failure} />
        {pending ? (
          <p role="status">{c.loading}</p>
        ) : todo.length ? (
          <div className="agenda-task-list">{todo.map(row)}</div>
        ) : (
          <Empty title={a.noTasks} />
        )}
        {tasks.some((task) => task.status === "done") && (
          <details className="agenda-completed">
            <summary>{a.completedTasks}</summary>
            {tasks.filter((task) => task.status === "done").map(row)}
          </details>
        )}
        {editing && (
          <TaskEditor
            key={editing === "new" ? "new" : editing.id}
            task={editing === "new" ? undefined : editing}
            goals={goals}
            online={online}
            close={() => setEditing(null)}
            onChange={onChange}
          />
        )}
      </aside>
    </Card>
  );
}
function TaskEditor({
  task,
  goals,
  online,
  close,
  onChange,
}: {
  task?: Task;
  goals: Goal[];
  online: boolean;
  close: () => void;
  onChange: () => Promise<void>;
}) {
  const [title, setTitle] = useState(task?.title || "");
  const [notes, setNotes] = useState(task?.notes || "");
  const [due, setDue] = useState(task?.due_date || "");
  const [goal, setGoal] = useState(task?.goal_id || "");
  const [estimate, setEstimate] = useState(task?.estimated_minutes || 30);
  const [failure, setFailure] = useState<unknown>();
  const [deleting, setDeleting] = useState(false);
  async function remove() {
    if (!task || !window.confirm(a.confirmTaskDelete)) return;
    setDeleting(true);
    try {
      await api(`/tasks/${task.id}`, "DELETE");
      await onChange();
      close();
    } catch (error) {
      setFailure(error);
    } finally {
      setDeleting(false);
    }
  }
  return (
    <Modal titleId="task-title" onClose={close}>
      <h2 id="task-title">{task ? a.editTask : a.addTask}</h2>
      <Notice error={failure} />
      <SubmitForm
        onSubmit={async () => {
          if (!online) return;
          await api(
            task ? `/tasks/${task.id}` : "/tasks",
            task ? "PATCH" : "POST",
            {
              title,
              notes,
              due_date: due || null,
              goal_id: goal || null,
              estimated_minutes: estimate,
            },
          );
          await onChange();
          close();
        }}
      >
        {(busy) => (
          <>
            <Field label={a.title}>
              <Input
                autoFocus
                disabled={!online}
                required
                maxLength={200}
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            </Field>
            <Field label={a.notes}>
              <Textarea
                rows={4}
                disabled={!online}
                maxLength={10000}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
              />
            </Field>
            <div className="form-grid">
              <Field label={a.due}>
                <Input
                  type="date"
                  disabled={!online}
                  value={due}
                  onChange={(e) => setDue(e.target.value)}
                />
              </Field>
              <Field label={a.estimate}>
                <Input
                  type="number"
                  disabled={!online}
                  min={5}
                  max={1440}
                  step={1}
                  required
                  value={estimate}
                  onChange={(e) => setEstimate(Number(e.target.value))}
                />
              </Field>
            </div>
            <Field label={a.linkedGoal}>
              <NativeSelect
                disabled={!online}
                value={goal}
                onChange={(e) => setGoal(e.target.value)}
              >
                <option value="">{a.noGoal}</option>
                {goals.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.title}
                  </option>
                ))}
              </NativeSelect>
            </Field>
            <div className="modal-actions">
              {task && (
                <Button
                  type="button"
                  className="danger"
                  disabled={!online || busy || deleting}
                  onClick={() => void remove()}
                >
                  {a.deleteTask}
                </Button>
              )}
              <Button type="button" onClick={close}>
                {c.cancel}
              </Button>
              <Button
                className="primary"
                disabled={!online || busy || deleting}
              >
                {busy ? c.saving : a.saveTask}
              </Button>
            </div>
          </>
        )}
      </SubmitForm>
    </Modal>
  );
}
