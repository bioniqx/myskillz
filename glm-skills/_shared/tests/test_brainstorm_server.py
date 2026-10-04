"""Tests for the brainstorming visual-companion scripts (start-server.sh, server.cjs, helper.js)."""
import json
import os
import shutil
import signal
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "brainstorming-glm" / "scripts"
START = SCRIPTS / "start-server.sh"
SERVER = SCRIPTS / "server.cjs"
HELPER = SCRIPTS / "helper.js"

HAVE_NODE = shutil.which("node") is not None
HAVE_BASH = shutil.which("bash") is not None


def _clean_env():
    env = dict(os.environ)
    for name in ("CODEX_CI", "BRAINSTORM_PORT", "BRAINSTORM_TOKEN", "BRAINSTORM_OPEN",
                 "BRAINSTORM_PORT_FILE", "BRAINSTORM_TOKEN_FILE", "BRAINSTORM_DIR"):
        env.pop(name, None)
    return env


def _stop_pid(pid):
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return
    deadline = time.time() + 5
    while time.time() < deadline:
        try:
            os.kill(pid, 0)
        except OSError:
            return
        time.sleep(0.05)
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        pass


@unittest.skipUnless(HAVE_NODE and HAVE_BASH, "node and bash required")
class StartServerProjectDirTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="bs-start-")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_relative_project_dir_starts_and_is_absolutized(self):
        proc = subprocess.run(
            ["bash", str(START), "--project-dir", "proj", "--background"],
            cwd=self.tmp, env=_clean_env(),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True, timeout=30,
        )
        out = proc.stdout.strip()
        self.assertIn("server-started", out, out + proc.stderr)
        info = json.loads(out.splitlines()[-1])
        pid_file = Path(info["state_dir"]) / "server.pid"
        if pid_file.exists():
            self.addCleanup(_stop_pid, int(pid_file.read_text().strip()))
        self.assertTrue(os.path.isabs(info["screen_dir"]), info["screen_dir"])
        expected_root = os.path.realpath(os.path.join(self.tmp, "proj", ".superpowers", "brainstorm"))
        self.assertTrue(
            os.path.realpath(info["screen_dir"]).startswith(expected_root + os.sep),
            info["screen_dir"],
        )
        self.assertEqual(proc.returncode, 0)


@unittest.skipUnless(HAVE_NODE, "node required")
class ServerSignalTest(unittest.TestCase):
    def _start(self):
        tmp = tempfile.mkdtemp(prefix="bs-sig-")
        self.addCleanup(shutil.rmtree, tmp, True)
        env = _clean_env()
        env["BRAINSTORM_DIR"] = tmp
        proc = subprocess.Popen(
            ["node", str(SERVER)], env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        self.addCleanup(_stop_pid, proc.pid)
        info = Path(tmp) / "state" / "server-info"
        deadline = time.time() + 10
        while time.time() < deadline and not info.exists():
            time.sleep(0.05)
        self.assertTrue(info.exists(), "server never wrote server-info")
        return proc, Path(tmp) / "state"

    def _assert_stops_cleanly(self, sig):
        proc, state = self._start()
        proc.send_signal(sig)
        proc.wait(timeout=10)
        stopped = state / "server-stopped"
        self.assertTrue(stopped.exists(), "server-stopped not written")
        self.assertFalse((state / "server-info").exists(), "stale server-info left behind")
        self.assertEqual(json.loads(stopped.read_text())["reason"], "signal")
        self.assertEqual(proc.returncode, 0)

    def test_sigterm_writes_server_stopped(self):
        self._assert_stops_cleanly(signal.SIGTERM)

    def test_sigint_writes_server_stopped(self):
        self._assert_stops_cleanly(signal.SIGINT)

    def test_sighup_writes_server_stopped(self):
        self._assert_stops_cleanly(signal.SIGHUP)


HELPER_DRIVER = """
const sent = [];
class FakeWS {
  constructor(url) { this.url = url; this.readyState = 1; }
  send(s) { sent.push(JSON.parse(s)); }
  close() {}
}
FakeWS.OPEN = 1;
global.WebSocket = FakeWS;
global.window = {
  location: { host: 'localhost:1', reload() {}, replace() {} },
  sessionStorage: { getItem() { return null; } }
};
global.document = {
  addEventListener() {},
  querySelector() { return null; },
  createElement() { return { style: {} }; },
  body: null
};
require(%s);
window.brainstorm.choice('b', { text: 'Option B' });
process.stdout.write(JSON.stringify(sent));
"""


@unittest.skipUnless(HAVE_NODE, "node required")
class HelperChoiceTest(unittest.TestCase):
    def test_choice_sends_choice_key(self):
        script = HELPER_DRIVER % json.dumps(str(HELPER))
        proc = subprocess.run(
            ["node", "-e", script],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True, timeout=30,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        sent = json.loads(proc.stdout)
        self.assertEqual(len(sent), 1, sent)
        event = sent[0]
        self.assertEqual(event["type"], "choice")
        self.assertEqual(event.get("choice"), "b", event)
        self.assertEqual(event["value"], "b")
        self.assertEqual(event["text"], "Option B")


if __name__ == "__main__":
    unittest.main()
