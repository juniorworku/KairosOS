import { useEffect, useState } from "react";
import { NavLink, Navigate, Route, Routes, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowUpRight,
  ArrowRight,
  CalendarDays,
  Check,
  Circle,
  Compass,
  Flag,
  Focus,
  Leaf,
  Menu,
  MessageCircle,
  Moon,
  Settings,
  Sparkles,
  Sun,
  Target,
  X,
} from "lucide-react";
import { copy as c } from "./copy/en";
import { Button } from "./components/ui/Button";
import type { paths } from "./api/schema";

type Theme = "light" | "dark" | "system";
const navigation = [
  ["today", Compass],
  ["goals", Flag],
  ["plan", CalendarDays],
  ["focus", Focus],
  ["review", Leaf],
  ["coach", MessageCircle],
] as const;
function getTheme(): Theme {
  try {
    const value = localStorage.getItem("kairos.theme");
    return value === "light" || value === "dark" ? value : "system";
  } catch {
    return "system";
  }
}
export default function App() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [theme, setTheme] = useState<Theme>(getTheme);
  useEffect(() => {
    const query = window.matchMedia("(prefers-color-scheme: dark)");
    const apply = () => {
      document.documentElement.dataset.theme =
        theme === "system" ? (query.matches ? "dark" : "light") : theme;
    };
    apply();
    query.addEventListener("change", apply);
    try {
      localStorage.setItem("kairos.theme", theme);
    } catch {
      /* Appearance remains available without storage. */
    }
    return () => query.removeEventListener("change", apply);
  }, [theme]);
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
          aria-label={menuOpen ? c.closeMenu : c.menu}
          aria-expanded={menuOpen}
          onClick={() => setMenuOpen(!menuOpen)}
        >
          {menuOpen ? <X size={20} /> : <Menu size={20} />}
        </Button>
      </div>
      <aside className={`sidebar ${menuOpen ? "open" : ""}`}>
        <Link to="/today" className="brand">
          <span className="brand-mark">k</span>
          {c.brand}
          <span className="brand-dot">.</span>
        </Link>
        <p className="brand-caption">{c.tagline}</p>
        <nav aria-label={c.brand}>
          <div className="nav-label">{c.today}</div>
          {navigation.map(([key, Icon]) => (
            <NavLink
              key={key}
              to={`/${key}`}
              onClick={() => setMenuOpen(false)}
              className={({ isActive }) =>
                `nav-item ${isActive ? "active" : ""}`
              }
            >
              <Icon size={19} strokeWidth={1.65} />
              <span>{c.nav[key]}</span>
              {key === "coach" && <Sparkles size={13} className="nav-spark" />}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="build-note">
            <span className="status-dot" />
            {c.foundation}
            <p>{c.foundationBody}</p>
          </div>
          <NavLink
            to="/settings"
            onClick={() => setMenuOpen(false)}
            className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}
          >
            <Settings size={19} strokeWidth={1.65} />
            {c.nav.settings}
          </NavLink>
          <div className="local-user">
            <span className="user-avatar">
              <Leaf size={18} />
            </span>
            <div>
              {c.local}
              <small>{c.noData}</small>
            </div>
          </div>
        </div>
      </aside>
      <main id="content" className="main" tabIndex={-1}>
        <Routes>
          <Route path="/today" element={<Today />} />
          {(Object.keys(c.pages) as (keyof typeof c.pages)[]).map((key) => (
            <Route
              key={key}
              path={`/${key}`}
              element={<FeaturePage page={key} />}
            />
          ))}
          <Route
            path="/settings"
            element={<SettingsPage theme={theme} setTheme={setTheme} />}
          />
          <Route path="*" element={<Navigate to="/today" replace />} />
        </Routes>
        <footer>
          <span className="footer-logo">{c.brand}</span>
          <span>{c.made}</span>
          <span className="footer-version">M0 · 0.1.0</span>
        </footer>
      </main>
    </div>
  );
}
function Today() {
  return (
    <>
      <header className="page-header">
        <span>
          <span className="tiny-dot" />
          {new Intl.DateTimeFormat(undefined, c.dateOptions).format(new Date())}
        </span>
        <span className="preview-tag">{c.foundation}</span>
      </header>
      <section className="hero">
        <div className="eyebrow">
          <span className="hero-line" />
          {c.today}
        </div>
        <h1>{c.greeting}</h1>
        <p>{c.intro}</p>
        <div className="hero-actions">
          <Link className="button primary" to="/goals">
            {c.start}
            <ArrowUpRight size={17} />
          </Link>
          <Link className="text-link" to="/plan">
            {c.viewPlan}
            <ArrowRight size={16} />
          </Link>
        </div>
        <div className="orbit-art" aria-hidden="true">
          <div className="orbit o1" />
          <div className="orbit o2" />
          <div className="orbit o3" />
          <div className="orbit-core">
            <Sparkles size={31} strokeWidth={1.1} />
          </div>
          <span className="planet p1" />
          <span className="planet p2" />
          <span className="planet p3" />
          <span className="orbit-cross">+</span>
        </div>
      </section>
      <section className="day-section">
        <div className="section-heading">
          <div>
            <h2>{c.today}</h2>
            <p>{c.todaySub}</p>
          </div>
          <span className="soft-badge">
            <Circle size={11} />
            {c.emptyLabel}
          </span>
        </div>
        <div className="empty-card">
          <div className="empty-icon">
            <Target size={30} strokeWidth={1.2} />
            <span className="icon-spark">+</span>
          </div>
          <h3>{c.emptyTitle}</h3>
          <p>{c.emptyBody}</p>
          <Link to="/goals" className="text-link">
            {c.start}
            <ArrowRight size={16} />
          </Link>
          <div className="card-grid" aria-hidden="true" />
        </div>
      </section>
      <section className="loop-section">
        <div className="eyebrow">{c.next}</div>
        <h2>{c.loopHeading}</h2>
        <div className="loop-grid">
          {c.loop.map((step, i) => (
            <Link
              key={step.title}
              to={["/goals", "/plan", "/focus"][i]}
              className="loop-card"
            >
              <div className={`loop-icon tone-${i}`}>
                {i === 0 ? (
                  <Flag size={21} />
                ) : i === 1 ? (
                  <CalendarDays size={21} />
                ) : (
                  <Focus size={21} />
                )}
              </div>
              <span className="step-label">{step.label}</span>
              <h3>
                {step.title}
                <ArrowUpRight size={16} />
              </h3>
              <p>{step.text}</p>
            </Link>
          ))}
        </div>
      </section>
      <aside className="attention-note">
        <div className="note-art" aria-hidden="true">
          <Leaf size={29} strokeWidth={1} />
        </div>
        <div>
          <span className="eyebrow">{c.intention}</span>
          <h3>{c.intentionTitle}</h3>
          <p>{c.intentionBody}</p>
        </div>
      </aside>
      <p className="research-note">{c.note}</p>
    </>
  );
}
function FeaturePage({ page }: { page: keyof typeof c.pages }) {
  const data = c.pages[page];
  return (
    <>
      <header className="page-header">
        <span>{c.nav[page]}</span>
        <span className="preview-tag">{c.foundation}</span>
      </header>
      <section className="feature-page">
        <span className="eyebrow">{data.milestone}</span>
        <h1>{data.title}</h1>
        <p className="feature-description">{data.description}</p>
        <div className="feature-panel">
          <span className="feature-symbol">
            <Sparkles size={27} strokeWidth={1.3} />
          </span>
          <span className="soft-badge">{c.unavailable}</span>
          <h2>{c.roadmap}</h2>
          <ul>
            {data.items.map((item) => (
              <li key={item}>
                <Circle size={12} />
                {item}
              </li>
            ))}
          </ul>
          <p>{c.foundationNote}</p>
          <Link to="/today" className="button primary">
            {c.back}
            <ArrowRight size={16} />
          </Link>
        </div>
      </section>
    </>
  );
}
function SettingsPage({
  theme,
  setTheme,
}: {
  theme: Theme;
  setTheme: (value: Theme) => void;
}) {
  const health = useQuery({
    queryKey: ["health"],
    queryFn: async () => {
      const response = await fetch("/healthz", {
        signal: AbortSignal.timeout(5000),
      });
      if (!response.ok) throw new Error("API unavailable");
      const data: paths["/healthz"]["get"]["responses"][200]["content"]["application/json"] =
        await response.json();
      return data;
    },
    retry: false,
    refetchOnWindowFocus: false,
  });
  return (
    <>
      <header className="page-header">
        <span>{c.nav.settings}</span>
        <span className="preview-tag">{c.foundation}</span>
      </header>
      <section className="feature-page settings-page">
        <h1>{c.settings.title}</h1>
        <p className="feature-description">{c.settings.description}</p>
        <div className="settings-panel">
          <h2>{c.settings.appearance}</h2>
          <label htmlFor="theme">{c.settings.themeLabel}</label>
          <div className="select-wrap">
            <Sun size={18} />
            <select
              id="theme"
              value={theme}
              onChange={(e) => setTheme(e.target.value as Theme)}
            >
              <option value="system">{c.settings.system}</option>
              <option value="light">{c.settings.light}</option>
              <option value="dark">{c.settings.dark}</option>
            </select>
            <Moon size={16} />
          </div>
        </div>
        <div className="settings-panel">
          <h2>{c.settings.connections}</h2>
          <div className="connection-row">
            <span>
              <CalendarDays size={19} />
              {c.settings.google}
            </span>
            <span className="soft-badge">{c.settings.notConnected}</span>
          </div>
          <p>{c.settings.connectionNote}</p>
        </div>
        <div className="settings-panel">
          <h2>{c.settings.backend}</h2>
          <div className="connection-row">
            <span role="status">
              {health.isFetching ? (
                <Circle size={15} />
              ) : health.isSuccess ? (
                <Check size={17} />
              ) : (
                <Circle size={15} />
              )}{" "}
              {health.isFetching
                ? c.settings.checking
                : health.isSuccess
                  ? c.settings.online
                  : c.settings.offline}
            </span>
            <Button
              onClick={() => void health.refetch()}
              disabled={health.isFetching}
            >
              {c.settings.retry}
            </Button>
          </div>
          <p>{c.settings.privacy}</p>
        </div>
      </section>
    </>
  );
}
