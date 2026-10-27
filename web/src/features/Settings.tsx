import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { copy as c } from "../copy/en";
import { useAuth } from "../lib/auth";
import { useData, useOnline } from "../lib/hooks";
import { api, clearPrivateData } from "../api/client";
import type { User, Season } from "../api/types";
import type { Theme } from "../App";
import type { CalendarStatus } from "./Plan";
import { Button } from "../components/ui/Button";
import { Field, Notice, SubmitForm } from "../components/ui/Forms";
import { addDays, dateKey } from "../lib/time";
interface SessionInfo {
  id: string;
  user_agent: string;
  current: boolean;
  last_used_at: string;
}
interface ExtToken {
  id: string;
  label: string;
  created_at: string;
  last_used_at: string | null;
}
interface PlanInfo {
  id: string;
  name: string;
  key: string;
  quotas: Record<string, number>;
}
interface Invite {
  id: string;
  email: string;
  role: string;
  expires_at: string;
  revoked_at: string | null;
}
export function Settings({
  theme,
  setTheme,
}: {
  theme: Theme;
  setTheme: (theme: Theme) => void;
}) {
  const auth = useAuth();
  const user = auth.user!;
  const online = useOnline();
  const client = useQueryClient();
  const [profile, setProfile] = useState({ ...user });
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<unknown>();
  const [code, setCode] = useState("");
  const calendar = useData<CalendarStatus>("/calendar/status");
  const sessions = useData<SessionInfo[]>("/me/sessions");
  const tokens = useData<ExtToken[]>("/ext/tokens");
  const usage = useData<{plan:string;calls_used:number;calls_limit:number;output_tokens_used:number;output_tokens_limit:number;resets_at:string}>("/coach/usage");
  function set<K extends keyof User>(key: K, value: User[K]) {
    setProfile((p) => ({ ...p, [key]: value }));
    setSaved(false);
  }
  async function action(path: string, body?: unknown, method = "POST") {
    setError(undefined);
    try {
      const value = await api(path, method, body);
      await client.invalidateQueries();
      return value;
    } catch (error) {
      setError(error);
    }
  }
  return (
    <>
      <header className="content-header">
        <h1>{c.settings.title}</h1>
      </header>
      <Notice error={error} />
      <div className="settings-grid">
        <div>
          <SubmitForm
            className="panel"
            onSubmit={async () => {
              await api("/me", "PATCH", {
                name: profile.name,
                timezone: profile.timezone,
                work_days: profile.work_days,
                work_start: profile.work_start,
                work_end: profile.work_end,
                daily_max_focus_minutes: profile.daily_max_focus_minutes,
                energy_peak: profile.energy_peak,
                ai_enabled: profile.ai_enabled,
              });
              await auth.refresh();
              setSaved(true);
            }}
          >
            {(busy) => (
              <>
                <h2>{c.settings.profile}</h2>
                <Field label={c.settings.name}>
                  <input
                    value={profile.name}
                    onChange={(e) => set("name", e.target.value)}
                    maxLength={120}
                    disabled={!online}
                  />
                </Field>
                <Field label={c.settings.timezone}>
                  <input
                    list="timezones"
                    value={profile.timezone}
                    onChange={(e) => set("timezone", e.target.value)}
                    required
                    disabled={!online}
                  />
                  <datalist id="timezones">
                    {Intl.supportedValuesOf("timeZone").map((t) => (
                      <option value={t} key={t} />
                    ))}
                  </datalist>
                </Field>
                <h2 className="form-section">{c.settings.availability}</h2>
                <div className="field">
                  <span>{c.settings.workDays}</span>
                  <div className="day-picker">
                    {c.settings.days.map((day, i) => (
                      <Button
                        type="button"
                        aria-pressed={profile.work_days.includes(i)}
                        onClick={() =>
                          set(
                            "work_days",
                            profile.work_days.includes(i)
                              ? profile.work_days.filter((d) => d !== i)
                              : [...profile.work_days, i].sort(),
                          )
                        }
                        disabled={!online}
                        key={day}
                      >
                        {day}
                      </Button>
                    ))}
                  </div>
                </div>
                <div className="form-grid">
                  <Field label={c.settings.start}>
                    <input
                      type="time"
                      required
                      value={profile.work_start}
                      onChange={(e) => set("work_start", e.target.value)}
                      disabled={!online}
                    />
                  </Field>
                  <Field label={c.settings.end}>
                    <input
                      type="time"
                      required
                      value={profile.work_end}
                      onChange={(e) => set("work_end", e.target.value)}
                      disabled={!online}
                    />
                  </Field>
                </div>
                <Field label={c.settings.cap}>
                  <input
                    type="number"
                    min={30}
                    max={720}
                    step={15}
                    required
                    value={profile.daily_max_focus_minutes}
                    onChange={(e) =>
                      set("daily_max_focus_minutes", Number(e.target.value))
                    }
                    disabled={!online}
                  />
                </Field>
                <Field label={c.settings.peak}>
                  <select
                    value={profile.energy_peak}
                    onChange={(e) =>
                      set("energy_peak", e.target.value as User["energy_peak"])
                    }
                    disabled={!online}
                  >
                    {(["morning", "afternoon", "evening"] as const).map((t) => (
                      <option value={t} key={t}>
                        {c.goals.form[t]}
                      </option>
                    ))}
                  </select>
                </Field>
                <h2 className="form-section">{c.settings.ai}</h2>
                <label className="checkbox">
                  <input
                    type="checkbox"
                    checked={profile.ai_enabled}
                    onChange={(e) => set("ai_enabled", e.target.checked)}
                    disabled={!online}
                  />
                  {c.settings.aiEnabled}
                </label>
                <div className="form-footer">
                  <Button className="primary" disabled={busy || !online}>
                    {busy ? c.saving : c.settings.save}
                  </Button>
                  {saved && (
                    <span role="status" className="save-note">
                      {c.saved}
                    </span>
                  )}
                </div>
              </>
            )}
          </SubmitForm>
          <section className="panel">
            <h2>{c.settings.appearance}</h2>
            <Field label={c.settings.theme}>
              <select
                value={theme}
                onChange={(e) => setTheme(e.target.value as Theme)}
              >
                {(["system", "light", "dark"] as const).map((t) => (
                  <option value={t} key={t}>
                    {c.settings[t]}
                  </option>
                ))}
              </select>
            </Field>
          </section>
          <SeasonSettings />
        </div>
        <div>
          <section className="panel">
            <h2>{c.settings.calendar}</h2>
            <div className="connection-row">
              <span className="status-label">
                {calendar.data?.connected
                  ? calendar.data.status === "needs_reauth"
                    ? c.settings.reauth
                    : c.settings.connected
                  : c.settings.notConnected}
              </span>
              {calendar.data?.configured && online && (
                <a className="button" href="/api/v1/calendar/connect">
                  {calendar.data.connected
                    ? c.settings.reauth
                    : c.settings.connect}
                </a>
              )}
            </div>
            <p className="form-hint">
              {calendar.data?.configured
                ? c.settings.calendarHint
                : c.settings.unconfigured}
            </p>
            {calendar.data?.connected && (
              <div className="button-row">
                <Button
                  disabled={!online}
                  onClick={() => void action("/calendar/sync")}
                >
                  {c.settings.sync}
                </Button>
                {!calendar.data.can_publish && online && (
                  <a
                    className="button"
                    href="/api/v1/calendar/connect?write=true"
                  >
                    {c.settings.write}
                  </a>
                )}
                <Button
                  disabled={!online}
                  onClick={() => void action("/calendar/disconnect")}
                >
                  {c.settings.disconnect}
                </Button>
              </div>
            )}
          </section>
          <section className="panel">
            <h2>{c.settings.extension}</h2>
            <p className="form-hint">{c.settings.pairHint}</p>
            <Button
              onClick={() =>
                void api<{ code: string }>("/ext/pair", "POST")
                  .then((data) => setCode(data.code))
                  .catch(setError)
              }
              disabled={!online}
            >
              {c.settings.pair}
            </Button>
            {code && (
              <p role="status" className="pair-code">
                <span>{c.settings.pairCode}</span>
                {code}
              </p>
            )}
            {tokens.data?.map((t) => (
              <div className="device-row" key={t.id}>
                <span>{t.label || c.settings.extension}</span>
                <Button
                  disabled={!online}
                  onClick={() =>
                    void action(`/ext/tokens/${t.id}`, undefined, "DELETE")
                  }
                >
                  {c.settings.revoke}
                </Button>
              </div>
            ))}
          </section>
          <BlocklistSettings />
          <section className="panel">
            <h2>{c.settings.sessions}</h2>
            {sessions.data?.map((s) => (
              <div className="device-row" key={s.id}>
                <div>
                  <strong>
                    {s.current ? c.settings.profile : c.settings.sessions}
                  </strong>
                  <small>{s.user_agent.slice(0, 85)}</small>
                  <time>{new Date(s.last_used_at).toLocaleDateString()}</time>
                </div>
                <Button
                  disabled={!online}
                  onClick={() =>
                    void action(
                      `/me/sessions/${s.id}`,
                      undefined,
                      "DELETE",
                    ).then(() => {
                      if (s.current) window.location.assign("/welcome");
                    })
                  }
                >
                  {c.settings.revoke}
                </Button>
              </div>
            ))}
            <Button
              disabled={!online}
              onClick={() =>
                void action("/me/sessions/revoke-all").then(() =>
                  window.location.assign("/welcome"),
                )
              }
            >
              {c.settings.revokeAll}
            </Button>
          </section>
          {usage.data && (
            <section className="panel">
              <h2>{c.settings.usage}</h2>
              <div className="metric-line"><span>{c.coach.calls}</span><strong>{usage.data.calls_used} / {usage.data.calls_limit}</strong></div><div className="metric-line"><span>{c.coach.words}</span><strong>{usage.data.output_tokens_used} / {usage.data.output_tokens_limit}</strong></div>
              </section>
          )}
          <section className="panel">
            <h2>{c.settings.data}</h2>
            <div className="button-row">
              <Button
                disabled={!online}
                onClick={() =>
                  void api("/me/export")
                    .then((data) => {
                      const url = URL.createObjectURL(
                        new Blob([JSON.stringify(data, null, 2)], {
                          type: "application/json",
                        }),
                      );
                      const anchor = document.createElement("a");
                      anchor.href = url;
                      anchor.download = "kairos-data.json";
                      anchor.click();
                      URL.revokeObjectURL(url);
                    })
                    .catch(setError)
                }
              >
                {c.settings.export}
              </Button>
              <Button
                className="danger"
                disabled={!online}
                onClick={() => {
                  if (
                    window.confirm(c.settings.deleteWarning) &&
                    window.prompt(c.settings.deleteConfirm) === "DELETE"
                  )
                    void api("/me", "DELETE")
                      .then(async () => {
                        await clearPrivateData();
                        client.clear();
                        window.location.assign("/welcome");
                      })
                      .catch(setError);
                }}
              >
                {c.settings.delete}
              </Button>
            </div>
          </section>
        </div>
      </div>
    </>
  );
}
function SeasonSettings() {
  const seasons = useData<Season[]>("/seasons");
  const online = useOnline();
  const client = useQueryClient();
  const [name, setName] = useState("");
  const [start, setStart] = useState(dateKey());
  const [end, setEnd] = useState(addDays(dateKey(), 83));
  return (
    <section className="panel">
      <h2>{c.goals.form.season}</h2>
      {seasons.data?.map((s) => (
        <div className="metric-line" key={s.id}>
          <strong>{s.name}</strong>
          <span>
            {s.start_date} — {s.end_date}
          </span>
        </div>
      ))}
      <details className="settings-details">
        <summary>{c.goals.form.newSeason}</summary>
        <SubmitForm
          onSubmit={async () => {
            await api("/seasons", "POST", {
              name,
              start_date: start,
              end_date: end,
              status: "active",
            });
            await client.invalidateQueries();
            setName("");
          }}
        >
          {(busy) => (
            <>
              <Field label={c.goals.form.seasonName}>
                <input
                  value={name}
                  required
                  onChange={(e) => setName(e.target.value)}
                  disabled={!online}
                />
              </Field>
              <div className="form-grid">
                <Field label={c.goals.form.seasonStart}>
                  <input
                    type="date"
                    value={start}
                    required
                    onChange={(e) => setStart(e.target.value)}
                    disabled={!online}
                  />
                </Field>
                <Field label={c.goals.form.seasonEnd}>
                  <input
                    type="date"
                    value={end}
                    min={start}
                    required
                    onChange={(e) => setEnd(e.target.value)}
                    disabled={!online}
                  />
                </Field>
              </div>
              <Button disabled={busy || !online}>{c.add}</Button>
            </>
          )}
        </SubmitForm>
      </details>
    </section>
  );
}
function BlocklistSettings() {
  const lists =
    useData<
      { id: string; name: string; domains: string[]; is_default: boolean }[]
    >("/blocklists");
  const online = useOnline();
  const client = useQueryClient();
  const [text, setText] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const list = lists.data?.find((b) => b.is_default) || lists.data?.[0];
  return (
    <section className="panel">
      <h2>{c.focus.blocklist}</h2>
      <SubmitForm
        onSubmit={async () => {
          await api(
            list ? `/blocklists/${list.id}` : "/blocklists",
            list ? "PATCH" : "POST",
            {
              name: c.focus.blocklist,
              domains: (text ?? list?.domains.join("\n") ?? "")
                .split("\n")
                .map((s) => s.trim())
                .filter(Boolean),
              is_default: true,
            },
          );
          await client.invalidateQueries();
          setSaved(true);
        }}
      >
        {(busy) => (
          <>
            <Field label={c.focus.blocklist} hint={c.focus.blocklistHint}>
              <textarea
                rows={4}
                value={text ?? list?.domains.join("\n") ?? ""}
                onChange={(e) => {
                  setText(e.target.value);
                  setSaved(false);
                }}
                disabled={!online}
              />
            </Field>
            <Button disabled={busy || !online}>{c.save}</Button>
            {saved && (
              <span role="status" className="save-note">
                {c.saved}
              </span>
            )}
          </>
        )}
      </SubmitForm>
    </section>
  );
}
export function Admin() {
  const users =
    useData<(User & { disabled_at: string | null })[]>("/admin/users");
  const plans = useData<PlanInfo[]>("/admin/plans");
  const invites = useData<Invite[]>("/admin/invites");
  const audit =
    useData<
      { id: string; action: string; target_type: string; created_at: string }[]
    >("/admin/audit");
  const client = useQueryClient();
  const [email, setEmail] = useState("");
  const [error, setError] = useState<unknown>();
  const online = useOnline();
  async function update(userId: string, body: unknown) {
    try {
      await api(`/admin/users/${userId}`, "PATCH", body);
      await client.invalidateQueries();
    } catch (error) {
      setError(error);
    }
  }
  return (
    <>
      <header className="content-header">
        <h1>{c.admin.title}</h1>
      </header>
      <Notice error={error || users.error} />
      <section className="panel table-panel">
        <table>
          <thead>
            <tr>
              <th>{c.admin.email}</th>
              <th>{c.admin.role}</th>
              <th>{c.admin.plan}</th>
              <th>{c.admin.status}</th>
              <th>
                <span className="sr-only">{c.edit}</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {users.data?.map((user) => (
              <tr key={user.id}>
                <td>{user.email}</td>
                <td>{user.role}</td>
                <td>
                  <select
                    aria-label={`${c.admin.plan} ${user.email}`}
                    value={user.plan_id}
                    disabled={!online}
                    onChange={(e) =>
                      void update(user.id, { plan_id: e.target.value })
                    }
                  >
                    {plans.data?.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name}
                      </option>
                    ))}
                  </select>
                </td>
                <td>
                  <Button
                    disabled={!online}
                    onClick={() =>
                      void update(user.id, { disabled: !user.disabled_at })
                    }
                  >
                    {user.disabled_at ? c.admin.enable : c.admin.disable}
                  </Button>
                </td>
                <td>
                  <Button
                    disabled={!online}
                    onClick={() =>
                      void api(
                        `/admin/users/${user.id}/revoke-sessions`,
                        "POST",
                      ).catch(setError)
                    }
                  >
                    {c.admin.sessions}
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      <section className="panel">
        <h2>{c.admin.invites}</h2>
        <SubmitForm
          className="inline-form"
          onSubmit={async () => {
            await api("/admin/invites", "POST", { email });
            setEmail("");
            await client.invalidateQueries();
          }}
        >
          {(busy) => (
            <>
              <Field label={c.admin.inviteEmail}>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  disabled={!online}
                />
              </Field>
              <Button disabled={busy || !online} className="primary">
                {c.admin.invite}
              </Button>
            </>
          )}
        </SubmitForm>
        {invites.data
          ?.filter((i) => !i.revoked_at)
          .map((i) => (
            <div className="device-row" key={i.id}>
              <div>
                {i.email}
                <small>
                  {c.admin.expires} {i.expires_at.slice(0, 10)}
                </small>
              </div>
              <Button
                onClick={() =>
                  void api(`/admin/invites/${i.id}`, "DELETE")
                    .then(() => client.invalidateQueries())
                    .catch(setError)
                }
                disabled={!online}
              >
                {c.settings.revoke}
              </Button>
            </div>
          ))}
      </section>
      <section className="panel">
        <h2>{c.admin.audit}</h2>
        {audit.data?.map((item) => (
          <div key={item.id} className="metric-line">
            <span>
              {item.action} · {item.target_type}
            </span>
            <time>{item.created_at.slice(0, 10)}</time>
          </div>
        ))}
      </section>
      <Link to="/settings" className="text-link">
        {c.settings.title}
      </Link>
    </>
  );
}
