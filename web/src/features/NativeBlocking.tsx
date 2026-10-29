import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useLocation } from "react-router-dom";
import { Monitor } from "lucide-react";
import type { components } from "../api/schema";
import { api } from "../api/client";
import { useAuth } from "../lib/auth";
import { useOnline } from "../lib/hooks";
import { clock } from "../lib/time";
import { Badge } from "../components/primitives/badge";
import { Card, CardContent, CardHeader } from "../components/primitives/card";
import { Button } from "../components/ui/Button";
import { Notice } from "../components/ui/Forms";

export type NativeDevice = components["schemas"]["NativeDevice"];
export function useNativeDevices() {
  const { user } = useAuth();
  return useQuery({
    queryKey: [user!.id, "/native/devices"],
    queryFn: ({ signal }) =>
      api<NativeDevice[]>("/native/devices", "GET", undefined, signal),
    networkMode: "always",
    retry: false,
    refetchInterval: 5000,
  });
}
export function NativeBlockingStatus({
  showHeading = true,
}: { showHeading?: boolean } = {}) {
  const devices = useNativeDevices();
  const { user } = useAuth();
  const online = useOnline();
  const reports = Array.isArray(devices.data) ? devices.data : [];
  return (
    <section aria-label="Native app blocking" className="blocking-status">
      <div className="workflow-heading">
        {showHeading && (
          <h2>
            <Monitor size={15} aria-hidden="true" />
            Native app blocking
          </h2>
        )}
        <Badge variant="outline">
          {devices.isPending
            ? "Checking…"
            : !online || devices.error
              ? "Not verified"
              : reports.some((device) => device.connected)
                ? "Recent helper report"
                : "Not connected"}
        </Badge>
      </div>
      {reports.map((device) => (
        <div key={device.credential_id} className="native-device-report">
          <strong>{device.label}</strong>
          <p className="workflow-muted">
            {!online || devices.error || !device.connected
              ? "No recent verified report. Check the companion on this device."
              : device.mode === "blocking"
                ? `Last report: ${device.suspended_count} app ${device.suspended_count === 1 ? "process" : "processes"} paused.`
                : device.mode === "paused"
                  ? "Last report: app blocking paused."
                  : device.mode === "error"
                    ? device.suspended_count > 0
                      ? `Last report: recovery pending for ${device.suspended_count} app processes. Check the companion locally.`
                      : "Helper reported a problem. Check it locally."
                    : "Last report: ready for a focus session."}
          </p>
          <p className="workflow-muted">
            Reported{" "}
            {new Date(device.last_seen_at).toLocaleString(undefined, {
              timeZone: user!.timezone,
            })}
          </p>
        </div>
      ))}
      {!reports.length && (
        <p className="workflow-muted">
          Optional Linux companion. Choose apps locally; starting a focus
          session never installs or enables it.
        </p>
      )}
      {showHeading && (
        <Button asChild variant="link">
          <Link to="/settings#native-blocking">Set up native blocking</Link>
        </Button>
      )}
    </section>
  );
}
export function NativeBlockingSettings() {
  const location = useLocation();
  useEffect(() => {
    if (location.hash !== "#native-blocking") return;
    const target = document.getElementById("native-blocking");
    target?.scrollIntoView({ block: "start" });
    target?.focus({ preventScroll: true });
  }, [location.hash]);
  const { user } = useAuth();
  const online = useOnline();
  const [pair, setPair] = useState<{ code: string; expires_at: string } | null>(
    null,
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  return (
    <Card id="native-blocking" tabIndex={-1} className="scroll-mt-6">
      <CardHeader>
        <h2>Native app blocking</h2>
        <p className="workflow-muted">
          Suspend selected Linux apps during focus. The companion resumes them
          when focus ends or verification is lost.
        </p>
      </CardHeader>
      <CardContent>
        <NativeBlockingStatus showHeading={false} />
        <details className="native-setup">
          <summary>Linux setup</summary>
          <ol className="plain-list">
            <li>
              Run the companion on your desktop host with Python 3.11 or newer,
              not inside Docker.
            </li>
            <li>
              <Button
                type="button"
                disabled={!online || busy}
                onClick={() => {
                  setBusy(true);
                  setError(undefined);
                  void api<{ code: string; expires_at: string }>(
                    "/ext/pair",
                    "POST",
                    {},
                  )
                    .then(setPair)
                    .catch(setError)
                    .finally(() => setBusy(false));
                }}
              >
                {busy ? "Creating code…" : "Pair Linux companion"}
              </Button>
              {pair && (
                <p role="status">
                  Pairing code:{" "}
                  <strong className="tabular-nums">{pair.code}</strong> ·
                  Expires {clock(pair.expires_at, user!.timezone)}. Single use;
                  generating a code replaces any unused device pairing code.
                </p>
              )}
            </li>
            <li>
              From the Kairos repository, run{" "}
              <code>
                python3 native/kairos_native.py pair --api http://localhost:8000
              </code>
              . Enter the code at its private prompt. For another server, use
              its HTTPS API origin.
            </li>
            <li>
              Copy <code>native/config.example.json</code> to{" "}
              <code>~/.config/kairos-native.json</code>, set file permissions to{" "}
              <code>0600</code>, choose exact executable paths, and set{" "}
              <code>enabled</code> to <code>true</code>.
            </li>
            <li>
              Run <code>python3 native/kairos_native.py run</code>. Press Ctrl+C
              to stop and resume apps. The web app cannot change your local
              executable list or enable the helper.
            </li>
          </ol>
          <p className="workflow-muted">
            An independent watchdog handles helper failure. If both processes
            are forcibly stopped, run{" "}
            <code>python3 native/kairos_native.py recover</code>. Revoke “Linux
            native companion” in the paired-device list to disconnect it.
          </p>
        </details>
        <Notice error={error} />
      </CardContent>
    </Card>
  );
}
