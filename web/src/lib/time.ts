export function dateKey(date = new Date(), timezone?: string): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(date);
}
export function weekStart(value = dateKey()): string {
  const day = new Date(`${value}T12:00:00`);
  const offset = (day.getDay() + 6) % 7;
  day.setDate(day.getDate() - offset);
  return dateKey(day);
}
export function addDays(value: string, days: number): string {
  const day = new Date(`${value}T12:00:00`);
  day.setDate(day.getDate() + days);
  return dateKey(day);
}
export function clock(value: string, timezone: string): string {
  return new Intl.DateTimeFormat(undefined, {
    timeZone: timezone,
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}
export function minutes(value: number): string {
  const amount = Math.round(value);
  return amount >= 60
    ? `${Math.floor(amount / 60)}h${amount % 60 ? ` ${amount % 60}m` : ""}`
    : `${amount}m`;
}
export function localInput(value: string, timezone?: string): string {
  const parts = new Intl.DateTimeFormat("sv-SE", {
    timeZone: timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(value));
  return parts.replace(" ", "T");
}
