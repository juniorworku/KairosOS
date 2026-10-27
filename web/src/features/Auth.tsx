import { useState, useEffect } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { copy as c } from "../copy/en";
import { useAuth } from "../lib/auth";
import { useData } from "../lib/hooks";
import { Button } from "../components/ui/Button";
import { Field, SubmitForm } from "../components/ui/Forms";
export function Welcome() {
  const auth = useAuth();
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [cooldown, setCooldown] = useState(0);
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  const config = useData<{
    google_enabled: boolean;
    email_enabled: boolean;
    development_owner_email?: string;
  }>("/auth/config");
  if (auth.user) return <Navigate to="/today" replace />;
  return (
    <div className="auth-screen">
      <div className="auth-brand">
        <span className="brand-mark">k</span>
        {c.brand}
      </div>
      <div className="auth-card">
        <h1>{sent ? c.sent : c.welcome}</h1>
        {sent ? (
          <>
            <p>{c.sentBody}</p>
            <Button disabled={now < cooldown} onClick={() => setSent(false)}>
              {c.resend}
            </Button>
          </>
        ) : (
          <>
            {config.data?.google_enabled && (
              <>
                <a
                  className="button google-button"
                  href="/api/v1/auth/google/login"
                >
                  {c.google}
                </a>
                <div className="auth-or">{c.or}</div>
              </>
            )}
            <SubmitForm
              onSubmit={async () => {
                await api("/auth/magic/request", "POST", { email });
                setCooldown(Date.now() + 60000);
                setSent(true);
              }}
            >
              {(busy) => (
                <>
                  <Field label={c.email}>
                    <input
                      type="email"
                      autoComplete="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      required
                      autoFocus
                    />
                  </Field>
                  <Button
                    type="submit"
                    className="primary full"
                    disabled={busy || config.isLoading}
                  >
                    {busy ? c.saving : c.emailLink}
                  </Button>
                </>
              )}
            </SubmitForm>
          </>
        )}
        {config.data?.development_owner_email && (
          <div className="local-inbox">
            <p>
              {c.localOwner}: <code>{config.data.development_owner_email}</code>
            </p>
            <a href="http://localhost:8025" target="_blank" rel="noreferrer">
              {c.mailpit}
            </a>
          </div>
        )}
        {config.isError && <p role="alert">{c.authUnavailable}</p>}
      </div>
    </div>
  );
}
export function Confirm() {
  const [params] = useSearchParams();
  const auth = useAuth();
  const navigate = useNavigate();
  const token = params.get("token");
  return (
    <div className="auth-screen">
      <div className="auth-brand">
        <span className="brand-mark">k</span>
        {c.brand}
      </div>
      <div className="auth-card">
        <h1>{c.confirm}</h1>
        <p>{c.confirmBody}</p>
        {token ? (
          <SubmitForm
            onSubmit={async () => {
              await api("/auth/magic/verify", "POST", { token });
              await auth.refresh();
              navigate("/today", { replace: true });
            }}
          >
            {(busy) => (
              <Button type="submit" className="primary full" disabled={busy}>
                {busy ? c.saving : c.confirm}
              </Button>
            )}
          </SubmitForm>
        ) : (
          <p role="alert">{c.invalidLink}</p>
        )}
        <Link className="text-link" to="/welcome">
          {c.back}
        </Link>
      </div>
    </div>
  );
}
