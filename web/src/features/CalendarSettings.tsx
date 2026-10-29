import { useAuth } from "../lib/auth";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import type { CalendarList } from "../api/calendar";
import { api } from "../api/client";
import { useData, useOnline } from "../lib/hooks";
import { Button } from "../components/ui/Button";
import { Notice, SubmitForm } from "../components/ui/Forms";
import { Badge } from "../components/primitives/badge";
import { Skeleton } from "../components/primitives/skeleton";
import "./calendar-controls.css";
export function CalendarSettings() {
  const query = useData<CalendarList>("/calendar/calendars");
  const online = useOnline();
  if (query.isPending)
    return <Skeleton className="h-12 w-full" aria-label="Loading calendars" />;
  return (
    <section className="calendar-selection" aria-label="Google calendars">
      <Notice error={query.error} />
      {query.data?.configured && query.data.connected && (
        <>
          {!query.data.selection_enabled ? (
            <>
              <p className="form-hint">
                Choose which Google calendars appear in your plan. This asks
                Google for calendar-list and event-reading access.
              </p>
              <Button asChild disabled={!online}>
                <a
                  href={
                    online
                      ? "/api/v1/calendar/connect?calendars=true"
                      : undefined
                  }
                  aria-disabled={!online}
                >
                  Choose Google calendars
                </a>
              </Button>
            </>
          ) : (
            <CalendarSelection
              key={JSON.stringify(query.data.calendars)}
              data={query.data}
              online={online}
            />
          )}
          {!query.data.write_enabled && (
            <div className="calendar-write-consent">
              <p className="form-hint">
                Editing Google events needs separate permission. Access is
                limited to calendars you own; shared calendars stay read-only.
              </p>
              <Button asChild disabled={!online}>
                <a
                  href={
                    online ? "/api/v1/calendar/connect?edit=true" : undefined
                  }
                  aria-disabled={!online}
                >
                  Allow Google event editing
                </a>
              </Button>
            </div>
          )}
          {query.data.write_enabled && (
            <p className="form-hint">
              Google event editing is enabled for calendars you own. Each save
              or delete changes Google Calendar directly. Publishing goal blocks
              uses its separate permission.
            </p>
          )}
        </>
      )}
    </section>
  );
}
function CalendarSelection({
  data,
  online,
}: {
  data: CalendarList;
  online: boolean;
}) {
  const { user } = useAuth();
  const [selected, setSelected] = useState(
    data.calendars.filter((item) => item.selected).map((item) => item.id),
  );
  const [saved, setSaved] = useState(false);
  const client = useQueryClient();
  return (
    <SubmitForm
      onSubmit={async () => {
        const affected = {
          predicate: (query: { queryKey: readonly unknown[] }) =>
            query.queryKey[0] === user!.id &&
            typeof query.queryKey[1] === "string" &&
            (query.queryKey[1].startsWith("/agenda?") ||
              query.queryKey[1] === "/calendar/busy"),
        };
        await client.cancelQueries(affected);
        await api("/calendar/calendars", "PUT", { calendar_ids: selected });
        await client.resetQueries(affected);
        await client.invalidateQueries();
        setSaved(true);
      }}
    >
      {(busy) => (
        <>
          <h3>Calendars in your plan</h3>
          <p className="form-hint">
            Only selected calendars contribute event details and availability.
            Local events stay in Kairos.
          </p>
          <fieldset disabled={!online || busy} className="calendar-options">
            <legend className="sr-only">Select calendars</legend>
            {data.calendars.map((item) => (
              <label className="calendar-option" key={item.id}>
                <input
                  type="checkbox"
                  checked={selected.includes(item.id)}
                  disabled={!item.can_select}
                  onChange={(event) => {
                    setSaved(false);
                    setSelected((ids) =>
                      event.target.checked
                        ? [...ids, item.id]
                        : ids.filter((id) => id !== item.id),
                    );
                  }}
                />
                <span>
                  <strong>{item.name}</strong>
                  <small>
                    {item.timezone}
                    {item.primary ? " · Primary" : ""}
                  </small>
                </span>
                <Badge variant="outline">
                  {item.can_write
                    ? "Editable"
                    : item.can_read
                      ? "Read-only"
                      : "Availability only"}
                </Badge>
              </label>
            ))}
          </fieldset>
          {!data.calendars.length && (
            <p className="form-hint">
              No available calendars were returned. Reconnect Google to refresh
              access.
            </p>
          )}
          <div className="button-row">
            <Button disabled={!online || busy}>
              {busy ? "Saving…" : "Save calendar selection"}
            </Button>
            <Button type="button" asChild>
              <a
                href={
                  online ? "/api/v1/calendar/connect?calendars=true" : undefined
                }
                aria-disabled={!online}
              >
                Refresh calendar access
              </a>
            </Button>
            {saved && <span role="status">Saved</span>}
          </div>
        </>
      )}
    </SubmitForm>
  );
}
