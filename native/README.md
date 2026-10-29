# Linux native focus companion

This optional local Python companion suspends explicitly selected Linux executables while your authenticated Kairos focus session is active. It sends `SIGSTOP` and later `SIGCONT`; it never terminates applications, changes hosts/firewall rules, installs a service, starts automatically, or measures attention/app activity. Browser domain blocking remains the separate extension.

Requires Linux with `/proc`, pidfds (Linux 5.3+), Python 3.11+ with `signal.pidfd_send_signal`, and normal same-user process permissions. Run as your desktop user; root execution is refused. No administrator privileges or third-party packages are needed. Windows/macOS support is not implemented. Containerized Kairos cannot suspend host applications; run this companion on the Linux desktop host.

## Explicit setup

Nothing in these instructions has been installed or enabled on your machine by the implementation tests.

1. In Kairos Settings, generate a fresh extension pairing code. Codes are single-use; create a separate one for this companion and for Chrome.
2. From the repository, run `python3 native/kairos_native.py pair --api http://localhost:8000`. Enter the code at the hidden prompt. The revocable bearer token stays in `~/.local/state/kairos-native/credential.json` with mode `0600`. The directory must be mode `0700`. Revoke **Linux native companion** in Settings to disconnect it.
3. Copy `native/config.example.json` to `~/.config/kairos-native.json` and set its permissions to `0600`. Set `api_origin` to the paired API origin. Add exact absolute executable paths you intentionally want suspended under `executables`, then set `enabled` to `true`. Resolve the executable itself, not a `.desktop` launcher, command arguments or wildcard. Keep work applications and applications with critical ongoing operations out of this list.
4. Run `python3 native/kairos_native.py run` in a terminal. This command is the explicit local opt-in. The companion scans only exact allowlisted executables owned by your UID. It also catches newly launched instances of those executables during focus.
5. Press Ctrl+C to stop and resume its suspended applications. `python3 native/kairos_native.py status` prints local status. Web Settings shows authenticated device heartbeats if the API supports `/api/v1/ext/native/status`; it cannot enable the companion or change the local executable list.

For an HTTPS API use its exact origin. HTTP is permitted only on loopback. Credentials are never forwarded through redirects or environment proxies. Keep this state directory private and do not commit credentials or application paths. `--state` and `--config` support explicit alternative local paths. CLI pairing/status output contains no bearer value.

## Recovery behavior

The controller reads `/api/v1/ext/state` with its paired bearer token. Only a live session with a future deadline bounded to four hours can suspend applications. A session ending, browser pause, expired/revoked pairing, API error or invalid response resumes applications. Network requests have a two-second timeout. A separate network-independent watchdog checks identity and deadlines every 100 ms and resumes applications if the controller dies, freezes past its eight-second lease, or the session deadline passes. If the watchdog exits, the controller resumes applications and stops.

Recovery intent is written atomically and fsynced **before** `SIGSTOP`. Failed or unverified resume attempts retain their journal records and are retried. A normal shutdown leaves the independent watchdog running when recovery is still pending; a manual `recover` command exits with a retry error until every recorded process is verified resumed or gone. Every signal uses a pidfd and verifies UID, PID, kernel start time, executable identity and boot ID. Self, ancestors, PID 1, the companion interpreter and protected shells/system executables are excluded. Already stopped processes are not adopted or later resumed. Only processes recorded by this companion are resumed. Multiple controllers cannot share the state directory.

If both controller and watchdog are forcibly killed or frozen together, independent recovery cannot run. Run `python3 native/kairos_native.py recover` with the same state directory to resume recorded processes, or restart the companion (which recovers first). Do not erase the journal before recovery. Linux reboot clears process suspension; boot identity prevents a stale journal from signaling unrelated processes after reboot. No user-space system can guarantee recovery while every recovery process is prevented from running.

Signals are asynchronous, and another same-user tool can change a process's state concurrently. Sandboxed applications, special executable launchers and multiple helper executables require manual desktop validation and explicit paths. The companion deliberately fails open on loss of verification. It does not claim universal OS-wide/cross-device blocking or proof that a user stayed focused.

## Status/reporting contract

Local `status.json` contains `running`, `session_id`, deadline epoch, `suspended_count`, `last_sync` epoch and a generic error. The independent watchdog sets stopped/recovered status after controller death. A local status file can be stale if all companion processes stop; treat fresh authenticated API heartbeats as reported status, not OS verification.

Optional heartbeat: `POST /api/v1/ext/native/status` with bearer auth and `{device_id, label:"Linux companion", mode:"idle"|"blocking"|"paused"|"error", suspended_count, session_id, ends_at}`. Device UUID is generated locally and persisted privately. Only a live session is reported as blocking; idle/error sends no session. No application names, paths, process IDs, usage history or attention measurements are transmitted. Reporting errors never prevent recovery; watchdog recovery uses no HTTP. Settings reads `/api/v1/native/devices`; missing/stale heartbeat means unverified, not running.

## Verification

Run `python3 -m unittest discover -s native/tests -v`. Tests use a loopback fake backend and a **unique temporary copy** of `sleep`; they never select a real installed application. They verify actual stop/continue signals on session end, API failure, controller SIGKILL, deadline while controller is frozen, lease expiry while controller is frozen, watchdog death, identity mismatch, pre-stopped exclusion and protected configuration. Injected transient SIGCONT and `/proc` identity failures verify that recovery intent survives, and a root/effective-root regression checks refusal before any state-directory mutation. Tests require local socket permissions in a sandbox.

Live pairing against the local Kairos API was verified using a unique disposable copied `sleep` process: focus start suspended it, the authenticated report appeared in the app API, and ending focus resumed it and produced an idle report. The test token, goal and processes were removed. Actual desktop application behavior and host packaging/autostart remain manual acceptance work. No native installation, autostart or real application suspension was performed for this implementation.
