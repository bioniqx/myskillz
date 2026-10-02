"""Black-box tests for claude-brainstorming-6.3/scripts/start-server.sh and stop-server.sh.

Exercises the real scripts (bash -n / sh -n syntax, real node + server.cjs for the
happy paths, a fake "node" executable for the crash/wrapper paths) against fixture
directories under the system temp dir. Never touches the repo working tree or
real .claude/dev-team/ state.
"""
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest

THIS_DIR = os.path.dirname(os.path.realpath(__file__))
SCRIPTS_DIR = os.path.realpath(
    os.path.join(THIS_DIR, "..", "claude-brainstorming-6.3", "scripts")
)
START = os.path.join(SCRIPTS_DIR, "start-server.sh")
STOP = os.path.join(SCRIPTS_DIR, "stop-server.sh")


def _read_json_line(line):
    line = line.strip()
    return json.loads(line) if line else {}


def _make_fake_node(bin_dir, body):
    """Write a fake `node` executable ahead of the real one on PATH."""
    node_path = os.path.join(bin_dir, "node")
    with open(node_path, "w") as f:
        f.write("#!/bin/sh\n" + body + "\n")
    st = os.stat(node_path)
    os.chmod(node_path, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return node_path


def _pid_alive(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _wait_for(predicate, timeout=3.0, step=0.05):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(step)
    return predicate()


class SyntaxTests(unittest.TestCase):
    def test_bash_n_and_sh_n_pass(self):
        for script in (START, STOP):
            r = subprocess.run(["bash", "-n", script], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, msg="bash -n %s: %s" % (script, r.stderr))
            r = subprocess.run(["sh", "-n", script], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, msg="sh -n %s: %s" % (script, r.stderr))


class RealServerTests(unittest.TestCase):
    """Tests that spawn the real node + server.cjs. Each stops what it starts."""

    def setUp(self):
        self._project_dirs = []
        self._session_dirs = []

    def tearDown(self):
        for session_dir in self._session_dirs:
            subprocess.run([STOP, session_dir], capture_output=True, text=True, timeout=10)
        for d in self._project_dirs:
            shutil.rmtree(d, ignore_errors=True)

    def _new_project_dir(self, suffix=""):
        d = os.path.realpath(tempfile.mkdtemp(prefix="brainstorm-proj" + suffix))
        self._project_dirs.append(d)
        return d

    def test_relative_project_dir_starts_server(self):
        project_dir = self._new_project_dir("-rel")
        env = dict(os.environ)
        env["HOME"] = project_dir
        r = subprocess.run(
            [START, "--project-dir", "."],
            cwd=project_dir,
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )
        self.assertEqual(r.returncode, 0, msg=r.stdout + r.stderr)
        info = _read_json_line(r.stdout)
        self.assertEqual(info.get("type"), "server-started")
        state_dir = info["state_dir"]
        self._session_dirs.append(os.path.dirname(state_dir))
        # The session must live under the (absolute) project dir, not under
        # SCRIPT_DIR or some other cwd the script `cd`d into.
        self.assertTrue(
            os.path.realpath(state_dir).startswith(os.path.realpath(project_dir)),
            msg="state_dir %s not under project_dir %s" % (state_dir, project_dir),
        )

    def test_project_dir_with_spaces(self):
        parent = self._new_project_dir("-space-parent")
        project_dir = os.path.join(parent, "my project")
        os.mkdir(project_dir)
        env = dict(os.environ)
        env["HOME"] = parent
        r = subprocess.run(
            [START, "--project-dir", project_dir],
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )
        self.assertEqual(r.returncode, 0, msg=r.stdout + r.stderr)
        info = _read_json_line(r.stdout)
        self.assertEqual(info.get("type"), "server-started")
        state_dir = info["state_dir"]
        self._session_dirs.append(os.path.dirname(state_dir))
        self.assertTrue(os.path.realpath(state_dir).startswith(os.path.realpath(project_dir)))

    def test_second_start_stops_first_session(self):
        project_dir = self._new_project_dir("-double")
        env = dict(os.environ)
        env["HOME"] = project_dir

        r1 = subprocess.run(
            [START, "--project-dir", project_dir],
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )
        self.assertEqual(r1.returncode, 0, msg=r1.stdout + r1.stderr)
        info1 = _read_json_line(r1.stdout)
        session_dir1 = os.path.dirname(info1["state_dir"])
        pid1_file = os.path.join(info1["state_dir"], "server.pid")
        with open(pid1_file) as f:
            pid1 = int(f.read().strip())
        self.assertTrue(_pid_alive(pid1), "first server should be running")

        r2 = subprocess.run(
            [START, "--project-dir", project_dir],
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )
        self.assertEqual(r2.returncode, 0, msg=r2.stdout + r2.stderr)
        info2 = _read_json_line(r2.stdout)
        session_dir2 = os.path.dirname(info2["state_dir"])
        self._session_dirs.append(session_dir2)
        self.assertNotEqual(session_dir1, session_dir2)

        # The prior session's server must have been stopped by the second start.
        self.assertTrue(
            _wait_for(lambda: not _pid_alive(pid1), timeout=3.0),
            "first server's pid %d should have been stopped" % pid1,
        )

    def test_second_start_never_signals_unrelated_process(self):
        # An unrelated process recorded under a stale/foreign session's pid
        # file (wrong server-instance-id) must never be signalled by a
        # second start for the same project dir.
        project_dir = self._new_project_dir("-unrelated")
        brainstorm_root = os.path.join(project_dir, ".superpowers", "brainstorm")
        foreign_session = os.path.join(brainstorm_root, "foreign-session")
        foreign_state = os.path.join(foreign_session, "state")
        os.makedirs(foreign_state)
        proc = subprocess.Popen(["sleep", "5"])
        try:
            time.sleep(0.1)
            with open(os.path.join(foreign_state, "server.pid"), "w") as f:
                f.write(str(proc.pid))
            with open(os.path.join(foreign_state, "server-instance-id"), "w") as f:
                f.write("d" * 40)

            env = dict(os.environ)
            env["HOME"] = project_dir
            r = subprocess.run(
                [START, "--project-dir", project_dir],
                capture_output=True,
                text=True,
                env=env,
                timeout=10,
            )
            self.assertEqual(r.returncode, 0, msg=r.stdout + r.stderr)
            info = _read_json_line(r.stdout)
            self._session_dirs.append(os.path.dirname(info["state_dir"]))
            self.assertIsNone(proc.poll(), "unrelated process must never be signalled")
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()

    def test_healthy_start_is_fast(self):
        project_dir = self._new_project_dir("-fast")
        env = dict(os.environ)
        env["HOME"] = project_dir
        started = time.time()
        r = subprocess.run(
            [START, "--project-dir", project_dir],
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )
        elapsed = time.time() - started
        self.assertEqual(r.returncode, 0, msg=r.stdout + r.stderr)
        info = _read_json_line(r.stdout)
        self._session_dirs.append(os.path.dirname(info["state_dir"]))
        # Was ~0.5s+ startup overhead before the perf fix; generous bound for CI.
        self.assertLess(elapsed, 2.0, "healthy start took %.3fs" % elapsed)


class FakeNodeTests(unittest.TestCase):
    """Tests that replace `node` on PATH to control crash timing precisely."""

    def setUp(self):
        self._tmp_dirs = []

    def tearDown(self):
        for d in self._tmp_dirs:
            shutil.rmtree(d, ignore_errors=True)

    def _new_dir(self, prefix):
        d = os.path.realpath(tempfile.mkdtemp(prefix=prefix))
        self._tmp_dirs.append(d)
        return d

    def test_dead_node_fails_fast_with_log_tail(self):
        bin_dir = self._new_dir("brainstorm-bin")
        _make_fake_node(
            bin_dir,
            'echo "boom line 1" >&2\n'
            'echo "boom line 2" >&2\n'
            'echo "boom line 3" >&2\n'
            "exit 1\n",
        )
        project_dir = self._new_dir("brainstorm-crash")
        env = dict(os.environ)
        env["HOME"] = project_dir
        env["PATH"] = bin_dir + os.pathsep + env.get("PATH", "")

        started = time.time()
        r = subprocess.run(
            [START, "--project-dir", project_dir],
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )
        elapsed = time.time() - started
        self.assertNotEqual(r.returncode, 0)
        self.assertLess(elapsed, 3.0, "dead-node failure took %.3fs (want ~1s)" % elapsed)
        err = _read_json_line(r.stdout)
        self.assertIn("error", err)
        tail = err.get("log_tail", "")
        self.assertIn("boom line 3", tail)
        self.assertIn("boom line 1", tail)

    def test_owner_pid_survives_wrappers(self):
        bin_dir = self._new_dir("brainstorm-bin2")
        _make_fake_node(bin_dir, "exit 1\n")
        project_dir = self._new_dir("brainstorm-owner")
        env = dict(os.environ)
        env["HOME"] = project_dir
        env["PATH"] = bin_dir + os.pathsep + env.get("PATH", "")

        # Wrap the script in a sh -> nohup -> env chain (no `exec`, so each
        # wrapper stays a live ancestor process) so OWNER_PID must climb past
        # all of them to find this test process as the real owner.
        chain_cmd = 'env sh -c \'nohup sh -c "\\"%s\\" --project-dir \\"%s\\""\'' % (
            START,
            project_dir,
        )
        subprocess.run(
            ["sh", "-c", chain_cmd],
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )
        owner_pid_file = None
        deadline = time.time() + 3.0
        while time.time() < deadline:
            candidates = []
            state_root = os.path.join(project_dir, ".superpowers", "brainstorm")
            if os.path.isdir(state_root):
                for session in os.listdir(state_root):
                    p = os.path.join(state_root, session, "state", "owner-pid")
                    if os.path.isfile(p):
                        candidates.append(p)
            if candidates:
                owner_pid_file = candidates[0]
                break
            time.sleep(0.05)
        self.assertIsNotNone(owner_pid_file, "owner-pid file was never written")
        with open(owner_pid_file) as f:
            owner_pid = int(f.read().strip())
        self.assertEqual(
            owner_pid,
            os.getpid(),
            "owner pid should climb past sh/nohup/env wrappers to the real owner",
        )


class StopServerTests(unittest.TestCase):
    def setUp(self):
        self._tmp_dirs = []
        self._procs = []

    def tearDown(self):
        for p in self._procs:
            if p.poll() is None:
                p.terminate()
                try:
                    p.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    p.kill()
        for d in self._tmp_dirs:
            shutil.rmtree(d, ignore_errors=True)

    def _new_dir(self, prefix, under_tmp=False):
        if under_tmp:
            # Intentionally NOT realpath'd: stop-server.sh's cleanup check is a
            # literal "/tmp/*" prefix match, and realpath would resolve macOS's
            # /tmp symlink to /private/tmp, defeating the very thing under test.
            d = tempfile.mkdtemp(prefix=prefix, dir="/tmp")
        else:
            d = os.path.realpath(tempfile.mkdtemp(prefix=prefix))
        self._tmp_dirs.append(d)
        return d

    def _make_session(self, session_dir, pid, server_id="a" * 40):
        state_dir = os.path.join(session_dir, "state")
        os.makedirs(state_dir, exist_ok=True)
        with open(os.path.join(state_dir, "server.pid"), "w") as f:
            f.write(str(pid))
        with open(os.path.join(state_dir, "server-instance-id"), "w") as f:
            f.write(server_id)
        with open(os.path.join(state_dir, "server-info"), "w") as f:
            f.write('{"type":"server-started"}\n')
        return state_dir

    def test_already_exited_persistent_session_keeps_real_reason(self):
        # A persistent (--project-dir) session whose server already exited on
        # its own must keep the reason node recorded, never overwritten with
        # stale_pid, and its directory must NOT be deleted (not ephemeral).
        session_dir = self._new_dir("brainstorm-exited-persist")
        state_dir = self._make_session(session_dir, pid=999999999, server_id="b" * 40)
        stopped_file = os.path.join(state_dir, "server-stopped")
        with open(stopped_file, "w") as f:
            f.write('{"reason":"idle-timeout","timestamp":123}\n')

        r = subprocess.run([STOP, session_dir], capture_output=True, text=True, timeout=10)
        self.assertEqual(r.returncode, 0, msg=r.stdout + r.stderr)
        out = _read_json_line(r.stdout)
        self.assertNotEqual(out.get("status"), "stale_pid")

        self.assertTrue(os.path.exists(stopped_file), "server-stopped file was removed")
        with open(stopped_file) as f:
            recorded = json.load(f)
        self.assertEqual(recorded.get("reason"), "idle-timeout")

        self.assertTrue(
            os.path.exists(session_dir), "persistent session dir must not be deleted"
        )

    def test_already_exited_tmp_session_cleans_up(self):
        # An ephemeral /tmp session whose server already exited on its own
        # must have its whole directory removed, and the printed status must
        # not be stale_pid (the pid simply isn't running any more).
        session_dir = self._new_dir("brainstorm-exited-tmp", under_tmp=True)
        self._make_session(session_dir, pid=999999999, server_id="e" * 40)

        r = subprocess.run([STOP, session_dir], capture_output=True, text=True, timeout=10)
        self.assertEqual(r.returncode, 0, msg=r.stdout + r.stderr)
        out = _read_json_line(r.stdout)
        self.assertNotEqual(out.get("status"), "stale_pid")

        self.assertFalse(os.path.exists(session_dir), "session dir under /tmp was not cleaned up")

    def test_stale_pid_reused_pid_never_signalled(self):
        session_dir = self._new_dir("brainstorm-stale")
        proc = subprocess.Popen(["sleep", "5"])
        self._procs.append(proc)
        time.sleep(0.1)
        state_dir = self._make_session(session_dir, pid=proc.pid, server_id="c" * 40)

        r = subprocess.run([STOP, session_dir], capture_output=True, text=True, timeout=10)
        self.assertEqual(r.returncode, 0, msg=r.stdout + r.stderr)
        out = _read_json_line(r.stdout)
        self.assertEqual(out.get("status"), "stale_pid")

        # The unrelated `sleep` process must never have been signalled.
        self.assertIsNone(proc.poll(), "unrelated process was killed")


if __name__ == "__main__":
    unittest.main()
