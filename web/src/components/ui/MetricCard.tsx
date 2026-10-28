import type { ReactNode } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
} from "../primitives/card";

export function MetricCard({
  label,
  value,
  icon,
}: {
  label: string;
  value: ReactNode;
  icon: ReactNode;
  tone?: "violet" | "mint" | "peach";
}) {
  return (
    <Card className="metric-card min-w-0 p-0">
      <CardHeader className="metric-top min-w-0 flex-row items-center justify-between space-y-0 px-3 pb-2 pt-4 sm:px-5 sm:pt-5">
        <CardDescription className="metric-label min-w-0">
          {label}
        </CardDescription>
        <span
          className="metric-icon shrink-0 text-muted-foreground"
          aria-hidden="true"
        >
          {icon}
        </span>
      </CardHeader>
      <CardContent className="metric-content min-w-0 px-3 pb-4 pt-0 sm:px-5 sm:pb-5">
        <strong className="metric-value block break-words font-semibold tracking-tight tabular-nums">
          {value}
        </strong>
      </CardContent>
    </Card>
  );
}
