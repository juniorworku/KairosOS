import { NativeBlockingStatus } from "./NativeBlocking";
import { Link } from "react-router-dom";
import { Shield } from "lucide-react";
import { Badge } from "../components/primitives/badge";
import { Skeleton } from "../components/primitives/skeleton";
import { Button } from "../components/ui/Button";
import { useData } from "../lib/hooks";
import { clock } from "../lib/time";
import { workflowCopy as w } from "./workflow-copy";
interface Extension {
  id: string;
  label: string;
  last_used_at: string | null;
}
export function BlockingStatus({
  domains,
  timezone,
}: {
  domains: string[];
  timezone: string;
}) {
  const tokens = useData<Extension[]>("/ext/tokens");
  const last = (tokens.data ?? [])
    .map((token) => token.last_used_at)
    .filter((value): value is string => Boolean(value))
    .sort()
    .at(-1);
  return (
    <>
      <section className="blocking-status" aria-label={w.browserBlocking}>
        <div className="workflow-heading">
          <h2>
            <Shield size={15} aria-hidden="true" />
            {w.browserBlocking}
          </h2>
          {tokens.isPending ? (
            <Skeleton className="h-4 w-24" />
          ) : (
            <Badge variant="outline">
              {tokens.error
                ? w.blockingUnknown
                : tokens.data?.length
                  ? "Device paired"
                  : w.extensionUnpaired}
            </Badge>
          )}
        </div>
        <p className="workflow-muted">{w.blockingUnknown}</p>
        {last && (
          <p className="workflow-muted">
            {w.lastContact}: {clock(last, timezone)}
          </p>
        )}
        <div className="workflow-domain-list" aria-label={w.selectedSites}>
          {domains.length ? (
            domains.map((domain) => (
              <Badge variant="secondary" key={domain}>
                {domain}
              </Badge>
            ))
          ) : (
            <span className="workflow-muted">{w.noSites}</span>
          )}
        </div>
        <Button asChild variant="link">
          <Link to="/settings">{w.extensionSettings}</Link>
        </Button>
      </section>
      <NativeBlockingStatus />
    </>
  );
}
