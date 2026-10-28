import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { Focus } from "lucide-react";
import type { FocusSession } from "../../api/types";
import { useData } from "../../lib/hooks";

/** Keep the running session reachable when planning or recording progress. */
export function ActiveSessionBar() {
  const session = useData<FocusSession | null>("/focus/active");
  const location = useLocation();
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (!session.data) return;
    setNow(Date.now());
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [session.data]);
  if (!session.data || location.pathname === "/focus") return null;
  const remaining = Math.max(
    0,
    Math.ceil((Date.parse(session.data.ends_at) - now) / 1000),
  );
  const duration = `${Math.floor(remaining / 60)}:${String(remaining % 60).padStart(2, "0")}`;
  return (
    <aside aria-label="Current focus session" className="active-session-bar">
      <Focus size={16} aria-hidden="true" />
      <Link to="/focus" className="active-session-title">
        {session.data.title || "Focus session"}
      </Link>
      <span
        className="tabular-nums"
        aria-label={remaining ? "Time remaining" : "Session ready to finish"}
      >
        {remaining ? duration : "Ready to finish"}
      </span>
      <Link to="/focus" className="text-link">
        {remaining ? "Return to session" : "Finish session"}
      </Link>
    </aside>
  );
}
