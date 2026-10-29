export interface GoogleCalendar {
  id: string;
  name: string;
  timezone: string;
  primary: boolean;
  access_role: string;
  selected: boolean;
  can_read: boolean;
  can_select: boolean;
  can_write: boolean;
}
export interface CalendarList {
  configured: boolean;
  connected: boolean;
  selection_enabled: boolean;
  write_enabled: boolean;
  calendars: GoogleCalendar[];
}
export interface GoogleEvent {
  id: string;
  source_id: string;
  calendar_id: string;
  etag: string;
  title: string;
  notes: string;
  start_at: string;
  end_at: string;
  timezone: string;
  all_day: boolean;
  recurring?: boolean;
  recurring_event_id?: string | null;
}
export function googleEventPath(calendarId: string, eventId: string) {
  return `/calendar/events/${encodeURIComponent(eventId)}?calendar_id=${encodeURIComponent(calendarId)}`;
}
