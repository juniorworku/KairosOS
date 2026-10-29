#!/usr/bin/env python3
"""Opt-in Linux focus suspension, with a separate fail-open recovery watchdog."""

from __future__ import annotations

import argparse
import fcntl
import getpass
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from uuid import uuid4
from datetime import datetime

PROTECTED = {
    "systemd",
    "init",
    "sshd",
    "sudo",
    "su",
    "login",
    "bash",
    "sh",
    "dash",
    "zsh",
    "fish",
    "dbus-daemon",
    "dbus-broker",
    "gnome-shell",
    "kwin_wayland",
    "Xorg",
    "Xwayland",
    "loginctl",
    "polkitd",
}
LEASE = 8.0
POLL = 1.0


def private_dir(path: Path) -> None:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if (
        path.is_symlink()
        or path.stat().st_uid != os.getuid()
        or path.stat().st_mode & 0o077
    ):
        raise ValueError("State directory must be owned by you with mode 0700")


def write_json(path: Path, value: object) -> None:
    temporary = path.with_name(path.name + ".tmp." + str(os.getpid()))
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w") as stream:
            json.dump(value, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def read_private(path: Path) -> dict:
    if (
        path.is_symlink()
        or path.stat().st_uid != os.getuid()
        or path.stat().st_mode & 0o077
    ):
        raise ValueError("Private file must be owned by you with mode 0600")
    return json.loads(path.read_text())


def identity(pid: int) -> dict | None:
    try:
        directory = Path(f"/proc/{pid}")
        if directory.stat().st_uid != os.getuid():
            return None
        stat = (directory / "stat").read_text()
        tail = stat[stat.rfind(")") + 2 :].split()
        executable = os.readlink(directory / "exe")
        return {
            "pid": pid,
            "start": tail[19],
            "exe": executable,
            "state": tail[0],
            "ppid": int(tail[1]),
            "boot": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
        }
    except (OSError, ValueError, IndexError):
        return None


def same_process(record: dict) -> bool:
    current = identity(record["pid"])
    return current is not None and all(
        current.get(key) == record.get(key) for key in ("pid", "start", "exe", "boot")
    )


def send(record: dict, command: signal.Signals) -> bool:
    # pidfd binds the signal to the inspected process, preventing PID reuse races.
    try:
        descriptor = os.pidfd_open(record["pid"])
    except (OSError, AttributeError):
        return False
    try:
        if not same_process(record):
            return False
        signal.pidfd_send_signal(descriptor, command)
        return True
    except (OSError, ProcessLookupError):
        return False
    finally:
        os.close(descriptor)


def protected_pids() -> set[int]:
    result = {1}
    pid = os.getpid()
    while pid > 1 and pid not in result:
        result.add(pid)
        current = identity(pid)
        if not current:
            break
        pid = current["ppid"]
    return result


def targets(executables: list[str], excluded: set[int]) -> list[dict]:
    allowed = set(executables)
    result = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit() or int(entry.name) in excluded:
            continue
        record = identity(int(entry.name))
        if (
            record
            and record["exe"] in allowed
            and Path(record["exe"]).name not in PROTECTED
            and record["state"] not in {"T", "t", "Z"}
        ):
            result.append(record)
    return result


def record_state(record: dict) -> str:
    current = identity(record["pid"])
    if current is None:
        return "unknown" if Path(f"/proc/{record['pid']}").exists() else "gone"
    if any(
        current.get(key) != record.get(key) for key in ("pid", "start", "exe", "boot")
    ):
        return "gone"
    return "stopped" if current["state"] in {"T", "t"} else "running"


def resume(journal: dict) -> list[dict]:
    pending = []
    for record in journal.get("processes", []):
        before = record_state(record)
        if before in {"gone", "running"}:
            continue
        send(record, signal.SIGCONT)
        # Signal delivery is asynchronous; never discard the only recovery intent
        # merely because dispatch succeeded, or a transient pidfd/proc read failed.
        if record_state(record) in {"stopped", "unknown"}:
            pending.append(record)
    return pending


def recover(directory: Path) -> list[dict]:
    path = directory / "journal.json"
    if path.exists():
        value = read_private(path)
        pending = resume(value)
        write_json(path, {"processes": pending})
        return pending
    return []


def watchdog(directory: Path, controller: dict) -> None:
    """No network dependency. Parent loss or a missed lease always resumes targets."""
    retired: set[tuple] = set()
    generation = None
    while True:
        try:
            journal = read_private(directory / "journal.json")
            lease = journal.get("lease_until")
            if lease != generation:
                retired.clear()
                generation = lease
            expired = time.monotonic() >= journal.get(
                "lease_until", 0
            ) or time.time() >= journal.get("deadline", 0)
            if not same_process(controller):
                # Serialize crash recovery against a replacement controller's startup.
                with (directory / "controller.lock").open("a") as recovery_lock:
                    try:
                        fcntl.flock(recovery_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError:
                        return  # Replacement controller owns recovery now.
                    pending = recover(directory)
                    write_json(
                        directory / "status.json",
                        {
                            "running": False,
                            "suspended_count": len(pending),
                            "error": "Recovery pending; retrying"
                            if pending
                            else "Controller stopped; recovery resumed apps",
                        },
                    )
                if not pending:
                    return
            if expired:
                candidates = [
                    record
                    for record in journal.get("processes", [])
                    if (
                        record["pid"],
                        record["start"],
                        record["exe"],
                        record.get("boot"),
                    )
                    not in retired
                ]
                pending = resume({"processes": candidates})
                remaining = {record["pid"] for record in pending}
                retired.update(
                    (record["pid"], record["start"], record["exe"], record.get("boot"))
                    for record in candidates
                    if record["pid"] not in remaining
                )
        except (OSError, ValueError, json.JSONDecodeError):
            pass
        time.sleep(0.1)


def base_url(value: str) -> str:
    parsed = urllib.parse.urlparse(value)
    if (
        parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise ValueError(
            "Use an API origin without credentials, path, query or fragment"
        )
    if parsed.scheme != "https" and not (
        parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    ):
        raise ValueError("API requires HTTPS, except loopback development servers")
    return value.rstrip("/")


def request(origin: str, path: str, token: str = "", body: dict | None = None) -> dict:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        origin + "/api/v1/ext/" + path, data=data, headers=headers
    )

    # Do not forward bearer credentials through redirects or environment HTTP proxies.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args):
            return None

    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open(req, timeout=2) as response:
        return json.loads(response.read(65537))


def validate_config(value: dict) -> tuple[str, list[str]]:
    origin = base_url(value["api_origin"])
    executables = value.get("executables", [])
    if not isinstance(executables, list) or not all(
        isinstance(item, str) for item in executables
    ):
        raise ValueError("executables must be a list of absolute executable paths")
    result = []
    own_executable = os.path.realpath(sys.executable)
    for item in executables:
        path = Path(item)
        if not path.is_absolute() or not path.is_file() or not os.access(path, os.X_OK):
            raise ValueError(
                "Allowlist entries must be existing absolute executable paths"
            )
        resolved = str(path.resolve())
        if (
            path.name in PROTECTED
            or Path(resolved).name in PROTECTED
            or resolved == own_executable
        ):
            raise ValueError(
                "Protected system or companion executable cannot be blocked"
            )
        result.append(resolved)
    return origin, result


def refuse_root() -> None:
    if os.getuid() == 0 or os.geteuid() == 0:
        raise RuntimeError("Run as your desktop user, never as root")


def run(directory: Path, config_path: Path) -> None:
    refuse_root()
    if (
        sys.platform != "linux"
        or not hasattr(signal, "pidfd_send_signal")
        or not hasattr(os, "pidfd_open")
    ):
        raise RuntimeError("Linux with Python pidfd support is required")
    private_dir(directory)
    lock = (directory / "controller.lock").open("a")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise RuntimeError("A companion already owns this state directory") from None
    config = read_private(config_path)
    origin, executables = validate_config(config)
    if config.get("enabled") is not True:
        raise ValueError(
            "Explicit enabled:true is required; no processes were suspended"
        )
    credential = read_private(directory / "credential.json")
    if credential["api_origin"] != origin:
        raise ValueError("Pairing belongs to a different API origin")
    device_path = directory / "device.json"
    if not device_path.exists():
        write_json(device_path, {"id": str(uuid4())})
    device_id = read_private(device_path)["id"]

    def report(mode: str, count: int = 0, state: dict | None = None) -> None:
        state = state or {}
        try:
            request(
                origin,
                "native/status",
                credential["token"],
                {
                    "device_id": device_id,
                    "label": "Linux companion",
                    "mode": mode,
                    "suspended_count": count,
                    "session_id": state.get("active_session", {}).get("id")
                    if state.get("active_session")
                    else None,
                    "ends_at": state.get("ends_at"),
                },
            )
        except Exception:
            pass  # Reporting never delays local recovery or controls the watchdog.

    pending_recovery = recover(directory)
    write_json(directory / "journal.json", {"processes": pending_recovery})
    controller = identity(os.getpid())
    guard = subprocess.Popen(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "_watchdog",
            "--state",
            str(directory),
            "--controller",
            json.dumps(controller),
        ],
        start_new_session=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
    )
    excluded = protected_pids() | {guard.pid}
    journal = {"processes": pending_recovery}
    recovery_only = bool(pending_recovery)
    stopping = False

    def stop(_number, _frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        while not stopping:
            if guard.poll() is not None:
                raise RuntimeError("Recovery watchdog exited; suspension disabled")
            error = None
            state = {}
            try:
                state = request(origin, "state", credential["token"])
                deadline = (
                    datetime.fromisoformat(
                        state["ends_at"].replace("Z", "+00:00")
                    ).timestamp()
                    if state.get("ends_at")
                    else 0
                )
                paused = (
                    datetime.fromisoformat(
                        state["pause_until"].replace("Z", "+00:00")
                    ).timestamp()
                    > time.time()
                    if state.get("pause_until")
                    else False
                )
                active = (
                    bool(state.get("active_session"))
                    and time.time() < deadline <= time.time() + 14405
                    and not paused
                )
            except Exception:
                # Never include response bodies, bearer values or personal focus titles in status.
                error = "API unavailable or invalid state; apps resumed"
                active, deadline = False, 0
            if recovery_only:
                active = False
            if not active:
                journal = {"processes": resume(journal)}
                recovery_only = bool(journal["processes"])
                if journal["processes"]:
                    error = "App recovery pending; retrying"
            else:
                journal["processes"] = [
                    record
                    for record in journal["processes"]
                    if record_state(record) in {"stopped", "unknown"}
                ]
                existing = {record["pid"] for record in journal["processes"]}
                fresh = targets(executables, excluded | existing)
                journal = {
                    "processes": journal["processes"] + fresh,
                    "lease_until": time.monotonic() + LEASE,
                    "deadline": deadline,
                }
                # Durable recovery intent exists before the first stop signal.
                write_json(directory / "journal.json", journal)
                successful = set()
                for record in fresh:
                    if guard.poll() is not None:
                        raise RuntimeError("Recovery watchdog exited before suspension")
                    if send(record, signal.SIGSTOP):
                        successful.add(record["pid"])
                journal["processes"] = [
                    record
                    for record in journal["processes"]
                    if record["pid"] in existing | successful
                    and record_state(record) != "gone"
                ]
            write_json(directory / "journal.json", journal)
            write_json(
                directory / "status.json",
                {
                    "running": True,
                    "session_id": state.get("active_session", {}).get("id")
                    if state.get("active_session")
                    else None,
                    "deadline": deadline or None,
                    "suspended_count": len(journal["processes"]),
                    "last_sync": time.time(),
                    "error": error,
                },
            )
            report(
                "error"
                if error
                else "blocking"
                if active
                else "paused"
                if state.get("pause_until")
                else "idle",
                len(journal["processes"]),
                state if active else None,
            )
            time.sleep(POLL)
    finally:
        journal = {"processes": resume(journal)}
        write_json(directory / "journal.json", journal)
        pending_recovery = recover(directory)
        write_json(
            directory / "status.json",
            {
                "running": False,
                "suspended_count": len(pending_recovery),
                "error": "Recovery pending; retrying" if pending_recovery else None,
            },
        )
        report("error" if pending_recovery else "idle", len(pending_recovery))
        if pending_recovery and guard.poll() is not None:
            guard = subprocess.Popen(
                guard.args,
                start_new_session=True,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
            )
        lock.close()
        if not pending_recovery:
            guard.terminate()
            guard.wait(timeout=3)
        # If recovery remains unresolved, leave the independent watchdog alive.
        # It acquires the released lock and retries until verified resumed/gone.


def main() -> None:
    refuse_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=["pair", "run", "recover", "status", "_watchdog"]
    )
    parser.add_argument(
        "--state", type=Path, default=Path.home() / ".local/state/kairos-native"
    )
    parser.add_argument(
        "--config", type=Path, default=Path.home() / ".config/kairos-native.json"
    )
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--controller", help=argparse.SUPPRESS)
    args = parser.parse_args()
    private_dir(args.state)
    if args.command == "pair":
        origin = base_url(args.api)
        result = request(
            origin,
            "pair/redeem",
            body={
                "code": getpass.getpass("Pairing code: "),
                "label": "Linux native companion",
            },
        )
        write_json(
            args.state / "credential.json",
            {"api_origin": origin, "token": result["token"]},
        )
        print("Paired. Revoke the Linux native companion token in Kairos Settings.")
    elif args.command == "run":
        run(args.state, args.config)
    elif args.command == "recover":
        with (args.state / "controller.lock").open("a") as recovery_lock:
            try:
                fcntl.flock(recovery_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RuntimeError(
                    "Stop the running companion before manual recovery"
                ) from None
            pending = recover(args.state)
            if pending:
                raise RuntimeError(
                    "Recovery remains pending; intent retained, retry recover"
                )
    elif args.command == "status":
        print(
            json.dumps(
                read_private(args.state / "status.json")
                if (args.state / "status.json").exists()
                else {"running": False}
            )
        )
    else:
        watchdog(args.state, json.loads(args.controller))


if __name__ == "__main__":
    main()
