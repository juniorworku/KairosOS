import type { ReactNode } from "react";
export function MetricCard({
  label,
  value,
  icon,
  tone = "violet",
}: {
  label: string;
  value: ReactNode;
  icon: ReactNode;
  tone?: "violet" | "mint" | "peach";
}) {
  return (
    <div className={`metric-card metric-${tone}`}>
      <div className="metric-top">
        <span>{label}</span>
        <span className="metric-icon" aria-hidden="true">
          {icon}
        </span>
      </div>
      <strong>{value}</strong>
      <span className="metric-orbit" aria-hidden="true" />
    </div>
  );
}
