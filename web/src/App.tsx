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
  LogOut,
  ClipboardList,
  ArrowUpRight,
} from "lucide-react";
import { copy as c } from "./copy/en";
import { useAuth } from "./lib/auth";
import { useOnline, useReplay } from "./lib/hooks";
import { Button } from "./components/ui/Button";
import { Skeleton } from "./components/primitives/skeleton";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "./components/primitives/sheet";
import { Separator } from "./components/primitives/separator";
import type { User } from "./api/types";
import { Notice } from "./components/ui/Forms";
import { Welcome, Confirm } from "./features/Auth";
import { Today } from "./features/Today";
import { Goals, GoalDetail, GoalEditor } from "./features/Goals";
const Plan = lazy(() =>
  import("./features/Plan").then((module) => ({ default: module.Plan })),
);
import { FocusPage } from "./features/Focus";
import { Review, Coach } from "./features/Review";
import { Settings } from "./features/Settings";
import { ActiveSessionBar } from "./components/ui/ActiveSessionBar";
import "./components/ui/active-session.css";
import { ThemeToggle } from "./components/ui/ThemeToggle";
import "./components/ui/theme-toggle.css";
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
    return value === "light" || value === "dark" || value === "system"
      ? value
      : "light";
  } catch {
    return "light";
  }
}
export default function App() {
  const auth = useAuth();
  const [open, setOpen] = useState(false);
  const [theme, setTheme] = useState<Theme>(initialTheme);
  const [resolvedTheme, setResolvedTheme] = useState<"light" | "dark">(
    theme === "dark" ? "dark" : "light",
  );
  const online = useOnline();
  const replay = useReplay();
  const [actionError, setActionError] = useState<unknown>();
  const location = useLocation();
  useEffect(() => setOpen(false), [location.pathname]);
  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const apply = () => {
      const resolved =
        theme === "system" ? (media.matches ? "dark" : "light") : theme;
      setResolvedTheme(resolved);
      document
        .querySelector('meta[name="theme-color"]')
        ?.setAttribute("content", resolved === "dark" ? "#161512" : "#f7f4ef");
      document.documentElement.dataset.theme = resolved;
      document.documentElement.classList.toggle("dark", resolved === "dark");
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
        <span className="sr-only">{c.loading}</span>
        <Skeleton className="h-6 w-32" />
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
      <Sheet open={open} onOpenChange={setOpen}>
        <div className="mobile-bar">
          <Link to="/today" className="brand">
            <span className="brand-mark" aria-hidden="true">
              k
            </span>
            {c.brand}
          </Link>
          <div className="mobile-bar-actions">
            <ThemeToggle compact resolved={resolvedTheme} onChange={setTheme} />
            <SheetTrigger asChild>
              <Button aria-label={c.menu} aria-expanded={open}>
                <Menu size={20} />
              </Button>
            </SheetTrigger>
          </div>
        </div>
        <SheetContent
          side="left"
          closeLabel={c.closeMenu}
          className="mobile-nav-sheet"
          aria-describedby={undefined}
        >
          <SheetHeader>
            <SheetTitle className="sr-only">{c.brand}</SheetTitle>
          </SheetHeader>
          <Navigation
            user={user}
            resolvedTheme={resolvedTheme}
            onThemeChange={setTheme}
            online={online}
            onNavigate={() => setOpen(false)}
            onLogout={() => void auth.logout().catch(setActionError)}
          />
        </SheetContent>
      </Sheet>
      <aside className="sidebar">
        <Navigation
          user={user}
          resolvedTheme={resolvedTheme}
          onThemeChange={setTheme}
          online={online}
          onLogout={() => void auth.logout().catch(setActionError)}
        />
      </aside>
      <main id="content" className="main" tabIndex={-1}>
        {!online && (
          <div className="offline-banner" role="status">
            {c.offline}
          </div>
        )}
        <Notice error={actionError} />
        {replay.error ? (
          <div className="sync-issue">
            <Notice error={replay.error} />
            <div className="button-row">
              <Button onClick={() => void replay.retry()}>{c.retry}</Button>
              <Button
                onClick={() => {
                  if (window.confirm(c.discardUnsynced)) void replay.discard();
                }}
              >
                {c.discardUpdates}
              </Button>
            </div>
          </div>
        ) : null}
        <ActiveSessionBar />
        <Suspense
          fallback={
            <div role="status" aria-label={c.loading}>
              <Skeleton className="mt-8 h-40 w-full" />
            </div>
          }
        >
          <Routes>
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
            <Route path="/admin/*" element={<Navigate to="/today" replace />} />
            <Route path="*" element={<Navigate to="/today" replace />} />
          </Routes>
        </Suspense>
        <PwaPrompt />
      </main>
    </div>
  );
}

function Navigation({
  user,
  online,
  onLogout,
  onNavigate,
  resolvedTheme,
  onThemeChange,
}: {
  user: User;
  online: boolean;
  onLogout: () => void;
  onNavigate?: () => void;
  resolvedTheme: "light" | "dark";
  onThemeChange: (theme: Theme) => void;
}) {
  return (
    <>
      <Link to="/today" className="brand" onClick={onNavigate}>
        <span className="brand-mark" aria-hidden="true">
          k
        </span>
        {c.brand}
      </Link>
      <nav aria-label={c.brand}>
        {navigation.map(([key, Icon]) => (
          <NavLink
            key={key}
            to={`/${key}`}
            onClick={onNavigate}
            className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}
          >
            <Icon size={18} strokeWidth={1.6} />
            {c.nav[key]}
          </NavLink>
        ))}
      </nav>
      <div className="sidebar-bottom">
        <Link to="/focus" className="sidebar-focus-card" onClick={onNavigate}>
          <span className="sidebar-focus-icon" aria-hidden="true">
            <Focus size={21} />
          </span>
          <span>{c.focus.start}</span>
          <ArrowUpRight size={16} aria-hidden="true" />
        </Link>
        <ThemeToggle resolved={resolvedTheme} onChange={onThemeChange} />
        <NavLink
          to="/settings"
          onClick={onNavigate}
          className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}
        >
          <SettingsIcon size={18} />
          {c.nav.settings}
        </NavLink>
        <Separator className="mt-5" />
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
            onClick={onLogout}
            disabled={!online}
          >
            <LogOut size={15} />
          </Button>
        </div>
      </div>
    </>
  );
}
