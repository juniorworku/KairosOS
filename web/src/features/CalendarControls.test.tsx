import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CalendarSettings } from "./CalendarSettings";
import { GoogleEventForm, GoogleEventEditor } from "./GoogleEventEditor";
import { AgendaEditor } from "./AgendaEditor";
import { api } from "../api/client";
import {
  googleEventPath,
  type CalendarList,
  type GoogleEvent,
} from "../api/calendar";
import type { AgendaItem } from "../api/agenda";
const data = vi.hoisted(() => ({
  values: {} as Record<string, unknown>,
  online: true,
}));
vi.mock("../lib/hooks", () => ({
  useData: (path: string) => ({
    data: data.values[path],
    isPending: false,
    error: null,
    refetch: vi.fn(),
  }),
  useOnline: () => data.online,
}));
vi.mock("../lib/auth", () => ({ useAuth: () => ({ user: { id: "owner" } }) }));
vi.mock("../api/client", () => ({ api: vi.fn() }));
const calendars: CalendarList = {
  configured: true,
  connected: true,
  selection_enabled: true,
  write_enabled: true,
  calendars: [
    {
      id: "owner/calendar",
      name: "Personal",
      timezone: "UTC",
      primary: true,
      access_role: "owner",
      selected: true,
      can_select: true,
      can_read: true,
      can_write: true,
    },
    {
      id: "shared",
      name: "Team",
      timezone: "UTC",
      primary: false,
      access_role: "reader",
      selected: false,
      can_select: true,
      can_read: false,
      can_write: false,
    },
  ],
};
const event: GoogleEvent = {
  id: "google:display:composite",
  source_id: "raw_google_id",
  calendar_id: "owner/calendar",
  etag: '"version-1"',
  title: "Writing",
  notes: "Keep this note",
  start_at: "2026-11-02T09:00:00Z",
  end_at: "2026-11-02T10:00:00Z",
  timezone: "UTC",
  all_day: false,
  recurring: true,
};
const close = vi.fn();
const onChange = vi.fn(async () => {});
function wrap(child: React.ReactNode, client = new QueryClient()) {
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>{child}</MemoryRouter>
    </QueryClientProvider>,
  );
}
beforeEach(() => {
  data.values = { "/calendar/calendars": calendars };
  data.online = true;
  close.mockReset();
  onChange.mockClear();
  vi.mocked(api).mockReset();
  vi.mocked(api).mockResolvedValue({});
});
afterEach(cleanup);
describe("calendar selection and consent", () => {
  it("clears the current account's old agenda before returning to the plan", async () => {
    const client = new QueryClient();
    const path = "/agenda?start=2026-10-26&end=2026-11-02";
    client.setQueryData(["owner", path], [{ title: "Deselected calendar" }]);
    client.setQueryData(["another", path], [{ title: "Other account" }]);
    wrap(<CalendarSettings />, client);
    fireEvent.click(
      screen.getByRole("button", { name: "Save calendar selection" }),
    );
    await screen.findByText("Saved");
    expect(client.getQueryData(["owner", path])).toBeUndefined();
    expect(client.getQueryData(["another", path])).toEqual([
      { title: "Other account" },
    ]);
  });
  it("saves explicit selection including availability-only shared calendars", async () => {
    wrap(<CalendarSettings />);
    expect(api).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("checkbox", { name: /Team/ }));
    fireEvent.click(
      screen.getByRole("button", { name: "Save calendar selection" }),
    );
    await waitFor(() =>
      expect(api).toHaveBeenCalledWith("/calendar/calendars", "PUT", {
        calendar_ids: ["owner/calendar", "shared"],
      }),
    );
  });
  it("offers calendar-list and event-write consent separately without requesting either automatically", () => {
    data.values["/calendar/calendars"] = {
      ...calendars,
      selection_enabled: false,
      write_enabled: false,
      calendars: [],
    };
    wrap(<CalendarSettings />);
    expect(
      screen.getByRole("link", { name: "Choose Google calendars" }),
    ).toHaveAttribute("href", "/api/v1/calendar/connect?calendars=true");
    expect(
      screen.getByRole("link", { name: "Allow Google event editing" }),
    ).toHaveAttribute("href", "/api/v1/calendar/connect?edit=true");
    expect(api).not.toHaveBeenCalled();
  });
});
describe("Google event mutations", () => {
  it("sends the loaded etag and raw event ID only after explicit Save", async () => {
    wrap(
      <GoogleEventForm
        calendarId="owner/calendar"
        calendars={calendars}
        timezone="UTC"
        initial={event}
        online
        close={close}
        onChange={onChange}
      />,
    );
    expect(api).not.toHaveBeenCalled();
    expect(screen.getByText(/This occurrence only/)).toBeVisible();
    fireEvent.change(screen.getByRole("textbox", { name: "Title" }), {
      target: { value: "Revised writing" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Save Google occurrence" }),
    );
    await waitFor(() =>
      expect(api).toHaveBeenCalledWith(
        googleEventPath("owner/calendar", "raw_google_id"),
        "PATCH",
        expect.objectContaining({
          calendar_id: "owner/calendar",
          etag: '"version-1"',
          title: "Revised writing",
        }),
      ),
    );
    expect(close).toHaveBeenCalled();
  });
  it("requires confirmation and the current etag before occurrence deletion", async () => {
    wrap(
      <GoogleEventForm
        calendarId="owner/calendar"
        calendars={calendars}
        timezone="UTC"
        initial={event}
        online
        close={close}
        onChange={onChange}
      />,
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Delete Google occurrence" }),
    );
    expect(api).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Confirm delete" }));
    await waitFor(() =>
      expect(api).toHaveBeenCalledWith(
        googleEventPath("owner/calendar", "raw_google_id") +
          "&etag=%22version-1%22",
        "DELETE",
      ),
    );
  });
  it("keeps failed stale edits open and does not retry", async () => {
    vi.mocked(api).mockRejectedValue(
      new Error("The Google event changed. Reload it before editing."),
    );
    wrap(
      <GoogleEventForm
        calendarId="owner/calendar"
        calendars={calendars}
        timezone="UTC"
        initial={event}
        online
        close={close}
        onChange={onChange}
      />,
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Save Google occurrence" }),
    );
    expect(
      await screen.findByText(
        "The Google event changed. Reload it before editing.",
      ),
    ).toBeVisible();
    expect(api).toHaveBeenCalledTimes(1);
    expect(close).not.toHaveBeenCalled();
    expect(onChange).not.toHaveBeenCalled();
  });
  it("keeps a read-only Google feed item out of all mutation forms", () => {
    wrap(
      <GoogleEventEditor
        item={
          {
            ...event,
            source: "google",
            editable: false,
            calendar_name: "Shared",
            source_id: event.source_id,
            recurring: true,
          } as AgendaItem
        }
        timezone="UTC"
        online
        close={close}
        onChange={onChange}
      />,
    );
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Calendar settings" }),
    ).toHaveAttribute("href", "/settings");
    expect(api).not.toHaveBeenCalled();
  });
  it("creates on the selected calendar with a stable retry identifier", async () => {
    wrap(
      <AgendaEditor
        selection={{
          kind: "event",
          start: "2026-11-02T09:00:00Z",
          end: "2026-11-02T10:00:00Z",
        }}
        timezone="UTC"
        goals={[]}
        tasks={[]}
        online
        close={close}
        onChange={onChange}
        onFocus={vi.fn()}
      />,
    );
    fireEvent.change(screen.getByRole("combobox", { name: "Calendar" }), {
      target: { value: "owner/calendar" },
    });
    fireEvent.change(screen.getByRole("textbox", { name: "Title" }), {
      target: { value: "Planning" },
    });
    vi.mocked(api).mockRejectedValueOnce(new Error("Try again"));
    fireEvent.click(screen.getByRole("button", { name: "Save Google event" }));
    await screen.findByText("Try again");
    fireEvent.click(screen.getByRole("button", { name: "Save Google event" }));
    await waitFor(() => expect(api).toHaveBeenCalledTimes(2));
    const first = vi.mocked(api).mock.calls[0];
    const second = vi.mocked(api).mock.calls[1];
    expect(first[0]).toBe("/calendar/events");
    expect(first[1]).toBe("POST");
    expect(first[2]).toMatchObject({
      calendar_id: "owner/calendar",
      title: "Planning",
      client_event_id: expect.any(String),
    });
    expect(second[2]).toEqual(first[2]);
  });
});

it("preserves Google all-day dates over a daylight-saving boundary", async () => {
  const allDay = {
    ...event,
    recurring: false,
    all_day: true,
    timezone: "America/New_York",
    start_at: "2026-03-08",
    end_at: "2026-03-09",
  };
  wrap(
    <GoogleEventForm
      calendarId="owner/calendar"
      calendars={calendars}
      timezone="UTC"
      initial={allDay}
      online
      close={close}
      onChange={onChange}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: "Save Google event" }));
  await waitFor(() =>
    expect(api).toHaveBeenCalledWith(
      googleEventPath("owner/calendar", "raw_google_id"),
      "PATCH",
      expect.objectContaining({
        start_at: "2026-03-08T05:00:00.000Z",
        end_at: "2026-03-09T04:00:00.000Z",
        all_day: true,
        timezone: "America/New_York",
      }),
    ),
  );
});
it("keeps exact Google event instants during a title-only edit", async () => {
  wrap(
    <GoogleEventForm
      calendarId="owner/calendar"
      calendars={calendars}
      timezone="UTC"
      initial={{
        ...event,
        start_at: "2026-11-02T09:00:37Z",
        end_at: "2026-11-02T10:00:42Z",
      }}
      online
      close={close}
      onChange={onChange}
    />,
  );
  fireEvent.change(screen.getByRole("textbox", { name: "Title" }), {
    target: { value: "New title" },
  });
  fireEvent.click(
    screen.getByRole("button", { name: "Save Google occurrence" }),
  );
  await waitFor(() =>
    expect(api).toHaveBeenCalledWith(
      googleEventPath("owner/calendar", "raw_google_id"),
      "PATCH",
      expect.objectContaining({
        start_at: "2026-11-02T09:00:37.000Z",
        end_at: "2026-11-02T10:00:42.000Z",
      }),
    ),
  );
});
