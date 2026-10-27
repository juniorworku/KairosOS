import { useEffect, useState, lazy, Suspense } from "react";
import {
  NavLink,
  Navigate,
  Route,
  Routes,
  Link,
  useLocation,
} from "react-router-dom";
import {
  CalendarDays,
  Compass,
  Flag,
  Focus,
  Menu,
  MessageCircle,
  Settings as SettingsIcon,
  X,
  LogOut,
  Users,
  ClipboardList,
} from "lucide-react";
import { copy as c } from "./copy/en";
import { useAuth } from "./lib/auth";
import { useOnline, useReplay } from "./lib/hooks";
import { Button } from "./components/ui/Button";
import { Notice } from "./components/ui/Forms";
import { Welcome, Confirm } from "./features/Auth";
import { Today } from "./features/Today";
import { Goals, GoalDetail, GoalEditor } from "./features/Goals";
const Plan=lazy(()=>import("./features/Plan").then(module=>({default:module.Plan})));
import { FocusPage } from "./features/Focus";
import { Review, Coach } from "./features/Review";
import { Settings, Admin } from "./features/Settings";
import { PwaPrompt } from "./pwa/Prompt";
export type Theme = "light" | "dark" | "system";
const navigation = [
  ["today", Compass],
  ["goals", Flag],
  ["plan", CalendarDays],
  ["focus", Focus],
  ["review", ClipboardList],
  ["coach", MessageCircle],
] as const;
function initialTheme(): Theme {
  try {
    const value = localStorage.getItem("kairos.theme");
    return value === "light" || value === "dark" ? value : "system";
  } catch {
    return "system";
  }
}
export default function App() {
  const auth = useAuth();
  const [open, setOpen] = useState(false);
  const [theme, setTheme] = useState<Theme>(initialTheme);
  const online = useOnline();
  const replay = useReplay();
  const[actionError,setActionError]=useState<unknown>();
  const location = useLocation();
  useEffect(() => setOpen(false), [location.pathname]);
  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const apply = () => {
      document.documentElement.dataset.theme =
        theme === "system" ? (media.matches ? "dark" : "light") : theme;
    };
    apply();
    media.addEventListener("change", apply);
    try {
      localStorage.setItem("kairos.theme", theme);
    } catch {
      /* Continue without persistence. */
    }
    return () => media.removeEventListener("change", apply);
  }, [theme]);
  if (location.pathname === "/welcome") return <Welcome />;
  if (location.pathname === "/auth/confirm") return <Confirm />;
  if (auth.loading)
    return (
      <div className="center-state" role="status">
        {c.loading}
      </div>
    );
  if (auth.error)
    return (
      <div className="center-state">
        <Notice error={auth.error} />
        <Button onClick={() => void auth.refresh()}>{c.retry}</Button>
      </div>
    );
  if (!auth.user) return <Navigate to="/welcome" replace />;
  const user = auth.user;
  return (
    <div className="app">
      <a className="skip" href="#content">
        {c.skip}
      </a>
      <div className="mobile-bar">
        <Link to="/today" className="brand">
          <span className="brand-mark">k</span>
          {c.brand}
        </Link>
        <Button
          aria-label={open ? c.closeMenu : c.menu}
          aria-expanded={open}
          onClick={() => setOpen(!open)}
        >
          {open ? <X size={20} /> : <Menu size={20} />}
        </Button>
      </div>
      <aside className={`sidebar ${open ? "open" : ""}`}>
        <Link to="/today" className="brand">
          <span className="brand-mark">k</span>
          {c.brand}
        </Link>
        <nav aria-label={c.brand}>
          {navigation.map(([key, Icon]) => (
            <NavLink
              key={key}
              to={`/${key}`}
              className={({ isActive }) =>
                `nav-item ${isActive ? "active" : ""}`
              }
            >
              <Icon size={18} strokeWidth={1.6} />
              {c.nav[key]}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-bottom">
          {user.role !== "user" && (
            <NavLink to="/admin" className="nav-item">
              <Users size={18} />
              {c.nav.admin}
            </NavLink>
          )}
          <NavLink
            to="/settings"
            className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}
          >
            <SettingsIcon size={18} />
            {c.nav.settings}
          </NavLink>
          <div className="local-user">
            <span className="user-avatar">
              {(user.name || user.email).slice(0, 1).toUpperCase()}
            </span>
            <div>
              {user.name || user.email.split("@")[0]}
              <small>{user.email}</small>
            </div>
            <Button
              className="icon-button"
              aria-label={c.signOut}
              onClick={() => void auth.logout().catch(setActionError)}
              disabled={!online}
            >
              <LogOut size={15} />
            </Button>
          </div>
        </div>
      </aside>
      <main id="content" className="main" tabIndex={-1}>
        {!online && (
          <div className="offline-banner" role="status">
            {c.offline}
          </div>
        )}
        <Notice error={actionError}/>{replay.error?<div className="sync-issue"><Notice error={replay.error}/><div className="button-row"><Button onClick={()=>void replay.retry()}>{c.retry}</Button><Button onClick={()=>{if(window.confirm(c.discardUnsynced))void replay.discard();}}>{c.discardUpdates}</Button></div></div>:null}
        <Suspense fallback={<p role="status">{c.loading}</p>}><Routes>
          <Route path="/today" element={<Today />} />
          <Route path="/goals" element={<Goals />} />
          <Route path="/goals/new" element={<GoalEditor />} />
          <Route path="/goals/:id" element={<GoalDetail />} />
          <Route path="/goals/:id/edit" element={<GoalEditor />} />
          <Route path="/onboarding" element={<GoalEditor />} />
          <Route path="/plan" element={<Plan />} />
          <Route path="/focus" element={<FocusPage />} />
          <Route path="/review" element={<Review />} />
          <Route path="/coach" element={<Coach />} />
          <Route
            path="/settings"
            element={<Settings theme={theme} setTheme={setTheme} />}
          />
          <Route
            path="/admin"
            element={
              user.role === "user" ? <Navigate to="/today" /> : <Admin />
            }
          />
          <Route path="*" element={<Navigate to="/today" replace />} />
        </Routes></Suspense>
        <PwaPrompt />
      </main>
    </div>
  );
}
