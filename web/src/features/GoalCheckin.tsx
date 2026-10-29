import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import type { Goal } from "../api/types";
import { api, queueWrite } from "../api/client";
import { useOnline } from "../lib/hooks";
import { Field, SubmitForm } from "../components/ui/Forms";
import { Button } from "../components/ui/Button";
import { Input } from "../components/primitives/input";
import { Textarea } from "../components/primitives/textarea";
import { Badge } from "../components/primitives/badge";
import { copy as c } from "../copy/en";
import { workflowCopy as w } from "./workflow-copy";
export function GoalCheckin({ goal }: { goal: Goal }) {
  const [value, setValue] = useState(
    String(goal.checkins.at(-1)?.metric_value ?? goal.metric_start),
  );
  const [note, setNote] = useState("");
  const [saved, setSaved] = useState<"saved" | "queued" | null>(null);
  const client = useQueryClient();
  const online = useOnline();
  return (
    <SubmitForm
      onSubmit={async () => {
        const body = { metric_value: Number(value), note };
        if (online) {
          await api("/goals/" + goal.id + "/checkins", "POST", body);
          await client.invalidateQueries();
          setSaved("saved");
        } else {
          await queueWrite("/goals/" + goal.id + "/checkins", body);
          setSaved("queued");
        }
        setNote("");
      }}
    >
      {(busy) => (
        <>
          <p className="workflow-muted">{w.outcomeHint}</p>
          <Field
            label={
              goal.metric_name +
              (goal.metric_unit ? " (" + goal.metric_unit + ")" : "")
            }
          >
            <Input
              type="number"
              step="any"
              required
              value={value}
              onChange={(event) => {
                setValue(event.target.value);
                setSaved(null);
              }}
            />
          </Field>
          <Field label={c.goals.note}>
            <Textarea
              rows={2}
              value={note}
              onChange={(event) => {
                setNote(event.target.value);
                setSaved(null);
              }}
            />
          </Field>
          <div className="workflow-actions">
            <Button disabled={busy}>{busy ? c.saving : w.logProgress}</Button>
            {saved && (
              <Badge variant="outline" role="status">
                {saved === "queued" ? c.queued : w.savedProgress}
              </Badge>
            )}
          </div>
        </>
      )}
    </SubmitForm>
  );
}
