import { Moon, Sun } from "lucide-react";
import { Button } from "./Button";
export function ThemeToggle({
  resolved,
  onChange,
  compact = false,
}: {
  resolved: "light" | "dark";
  onChange: (theme: "light" | "dark") => void;
  compact?: boolean;
}) {
  return (
    <div
      className={`theme-toggle ${compact ? "is-compact" : ""}`}
      role="group"
      aria-label="Color theme"
    >
      {(["light", "dark"] as const).map((theme) => {
        const Icon = theme === "light" ? Sun : Moon;
        return (
          <Button
            key={theme}
            type="button"
            variant="ghost"
            size="sm"
            aria-label={`${theme === "light" ? "Light" : "Dark"} theme`}
            aria-pressed={resolved === theme}
            onClick={() => onChange(theme)}
          >
            <Icon size={15} aria-hidden="true" />
            {!compact && <span>{theme === "light" ? "Light" : "Dark"}</span>}
          </Button>
        );
      })}
    </div>
  );
}
