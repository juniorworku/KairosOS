"""Real Linux signals are exercised only on a unique disposable binary copy."""

import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime, UTC, timedelta

MODULE = Path(__file__).resolve().parents[1] / "kairos_native.py"
spec = importlib.util.spec_from_file_location("native", MODULE)
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)


def wait_for(predicate, timeout=6):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        if predicate():
            return
        time.sleep(0.04)
    raise AssertionError("Timed out waiting for process state")


@unittest.skipUnless(
    sys.platform == "linux" and hasattr(signal, "pidfd_send_signal"),
    "Linux pidfd required",
)
class CompanionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.state = self.root / "state"
        native.private_dir(self.state)
        self.binary = self.root / "disposable-sleep"
        shutil.copy2(shutil.which("sleep"), self.binary)
        self.target = subprocess.Popen([str(self.binary), "60"])
        self.addCleanup(self.cleanup_target)
        self.controller = None
        self.guard = None
        self.active = True
        self.unavailable = False
        self.deadline = datetime.now(UTC) + timedelta(seconds=60)
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if owner.unavailable:
                    self.send_error(503)
                    return
                result = {
                    "active_session": {"id": "00000000-0000-4000-8000-000000000001"}
                    if owner.active
                    else None,
                    "ends_at": owner.deadline.isoformat() if owner.active else None,
                    "pause_until": None,
                }
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps(result).encode())

            def do_POST(self):
                self.rfile.read(int(self.headers.get("Content-Length", 0)))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"{}")

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        origin = f"http://127.0.0.1:{self.server.server_port}"
        native.write_json(
            self.state / "credential.json",
            {"api_origin": origin, "token": "test-only-not-a-real-credential"},
        )
        self.config = self.root / "config.json"
        native.write_json(
            self.config,
            {"enabled": True, "api_origin": origin, "executables": [str(self.binary)]},
        )

    def cleanup_target(self):
        if self.target.poll() is None:
            os.kill(self.target.pid, signal.SIGCONT)
            self.target.terminate()
            self.target.wait(timeout=3)

    def tearDown(self):
        if self.controller and self.controller.poll() is None:
            self.controller.terminate()
            self.controller.wait(timeout=6)
        if self.controller and self.controller.stderr:
            self.controller.stderr.close()
        native.recover(self.state)
        self.target.terminate()
        self.target.wait(timeout=3)
        self.server.shutdown()
        self.server.server_close()
        self.temp.cleanup()

    def start(self):
        self.controller = subprocess.Popen(
            [
                sys.executable,
                str(MODULE),
                "run",
                "--state",
                str(self.state),
                "--config",
                str(self.config),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        wait_for(lambda: native.identity(self.target.pid)["state"] == "T")
        self.assertEqual(self.controller.poll(), None)

    def resumed(self):
        wait_for(lambda: native.identity(self.target.pid)["state"] != "T")

    def test_session_end_resumes_real_process(self):
        self.start()
        self.active = False
        self.resumed()

    def test_api_failure_resumes_real_process(self):
        self.start()
        self.unavailable = True
        self.resumed()

    def test_controller_sigkill_recovers_independently(self):
        self.start()
        self.controller.kill()
        self.controller.wait(timeout=3)
        self.resumed()

    def test_deadline_recovers_during_frozen_controller(self):
        self.deadline = datetime.now(UTC) + timedelta(seconds=2)
        self.start()
        os.kill(self.controller.pid, signal.SIGSTOP)
        try:
            self.resumed()
        finally:
            os.kill(self.controller.pid, signal.SIGCONT)

    def test_lease_recovers_when_controller_is_frozen(self):
        self.start()
        os.kill(self.controller.pid, signal.SIGSTOP)
        try:
            wait_for(
                lambda: native.identity(self.target.pid)["state"] != "T", timeout=10
            )
        finally:
            os.kill(self.controller.pid, signal.SIGCONT)

    def test_watchdog_death_controller_resumes(self):
        self.start()
        children = (
            Path(f"/proc/{self.controller.pid}/task/{self.controller.pid}/children")
            .read_text()
            .split()
        )
        self.assertEqual(len(children), 1)
        os.kill(int(children[0]), signal.SIGKILL)
        self.resumed()
        self.controller.wait(timeout=4)
        self.assertNotEqual(self.controller.returncode, 0)

    def test_transient_continue_failure_retains_journal_until_verified_recovery(self):
        record = native.identity(self.target.pid)
        os.kill(self.target.pid, signal.SIGSTOP)
        wait_for(lambda: native.identity(self.target.pid)["state"] == "T")
        native.write_json(self.state / "journal.json", {"processes": [record]})
        with mock.patch.object(native, "send", return_value=False):
            pending = native.recover(self.state)
        self.assertEqual([item["pid"] for item in pending], [self.target.pid])
        self.assertEqual(
            len(native.read_private(self.state / "journal.json")["processes"]), 1
        )
        self.assertEqual(native.identity(self.target.pid)["state"], "T")
        native.recover(self.state)
        self.resumed()
        self.assertEqual(native.recover(self.state), [])
        self.assertEqual(
            native.read_private(self.state / "journal.json")["processes"], []
        )

    def test_watchdog_retries_transient_continue_failure_after_controller_crash(self):
        record = native.identity(self.target.pid)
        os.kill(self.target.pid, signal.SIGSTOP)
        wait_for(lambda: native.identity(self.target.pid)["state"] == "T")
        native.write_json(self.state / "journal.json", {"processes": [record]})
        dead_controller = {**native.identity(os.getpid()), "start": "different-start"}
        original_send = native.send
        attempts = 0

        def transient_send(target, command):
            nonlocal attempts
            attempts += 1
            return False if attempts == 1 else original_send(target, command)

        with mock.patch.object(native, "send", side_effect=transient_send):
            native.watchdog(self.state, dead_controller)
        self.assertGreaterEqual(attempts, 2)
        self.resumed()
        self.assertEqual(
            native.read_private(self.state / "journal.json")["processes"], []
        )

    def test_transient_identity_failure_does_not_discard_recovery(self):
        record = native.identity(self.target.pid)
        os.kill(self.target.pid, signal.SIGSTOP)
        wait_for(lambda: native.identity(self.target.pid)["state"] == "T")
        with mock.patch.object(native, "identity", return_value=None):
            self.assertEqual(native.resume({"processes": [record]}), [record])
        os.kill(self.target.pid, signal.SIGCONT)

    def test_root_refused_before_state_path_mutation(self):
        with (
            mock.patch.object(native.os, "geteuid", return_value=0),
            mock.patch.object(native, "private_dir") as create,
        ):
            with self.assertRaisesRegex(RuntimeError, "never as root"):
                native.main()
            create.assert_not_called()
            with self.assertRaisesRegex(RuntimeError, "never as root"):
                native.run(self.root / "unused-state", self.config)
            create.assert_not_called()

    def test_identity_mismatch_never_signals(self):
        record = native.identity(self.target.pid)
        record["start"] = "not-the-process-start"
        self.assertFalse(native.send(record, signal.SIGSTOP))
        self.assertNotEqual(native.identity(self.target.pid)["state"], "T")

    def test_preexisting_stopped_process_is_not_adopted(self):
        os.kill(self.target.pid, signal.SIGSTOP)
        try:
            self.assertEqual(native.targets([str(self.binary)], set()), [])
        finally:
            os.kill(self.target.pid, signal.SIGCONT)

    def test_protected_configuration_and_transport(self):
        with self.assertRaises(ValueError):
            native.validate_config(
                {"api_origin": "http://localhost:8000", "executables": [sys.executable]}
            )
        with self.assertRaises(ValueError):
            native.base_url("http://example.com")
        with self.assertRaises(ValueError):
            native.base_url("https://user:secret@example.com")
        self.assertIn(os.getpid(), native.protected_pids())
        self.assertEqual(native.targets([str(self.binary)], {self.target.pid}), [])


if __name__ == "__main__":
    unittest.main()
