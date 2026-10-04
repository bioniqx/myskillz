"""Behaviour of the ported systematic-debugging scripts and tool (glm variant)."""
import glob
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
import json
import re

HERE = os.path.dirname(os.path.realpath(__file__))
SCRIPTS = os.path.realpath(os.path.join(HERE, "..", "..", "systematic-debugging-glm", "scripts"))
SKILL = os.path.dirname(SCRIPTS)
TOOL = os.path.join(SCRIPTS, "debug_tool.py")
LIB = os.path.join(SCRIPTS, "_lib.sh")
STRESS = os.path.join(SCRIPTS, "stress.sh")
BISECT = os.path.join(SCRIPTS, "bisect-parallel.sh")
POLLUTER = os.path.join(SCRIPTS, "find-polluter.sh")
SNAPSHOT = os.path.join(SCRIPTS, "snapshot.sh")

STALE_PROBE = '#!/bin/sh\n[ -e junk ] && echo STALE >>"$LOG"\n: >junk\ngrep -q bad val && exit 1\nexit 0\n'
MARK_PROBE = (
    "import os, time\n"
    "f = open(os.environ['MARK_FILE'], 'a')\n"
    "f.write('S %s\\n' % os.environ['SD_ARM'])\n"
    "f.flush()\n"
    "time.sleep(0.4)\n"
    "f.write('E %s\\n' % os.environ['SD_ARM'])\n"
    "f.close()\n"
)


def make_env(base):
    env = dict(os.environ)
    for key in list(env):
        if key.startswith("GIT_"):
            del env[key]
    env.update({
        "TMPDIR": base,
        "HOME": base,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.com",
    })
    return env


def wait_until(predicate, seconds):
    end = time.time() + seconds
    while time.time() < end:
        if predicate():
            return True
        time.sleep(0.1)
    return False


class Base(unittest.TestCase):
    def setUp(self):
        self.base = os.path.realpath(tempfile.mkdtemp(prefix="sdport."))
        self.addCleanup(shutil.rmtree, self.base, True)
        self.env = make_env(self.base)

    def git(self, repo, *args):
        done = subprocess.run(["git"] + list(args), cwd=repo, env=self.env, check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        return done.stdout.strip()

    def write_files(self, repo, files):
        for rel, text in files.items():
            path = os.path.join(repo, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as handle:
                handle.write(text)

    def commit(self, repo, message):
        self.git(repo, "add", "--all")
        self.git(repo, "commit", "-q", "-m", message)

    def make_repo(self, files, name="repo"):
        repo = os.path.join(self.base, name)
        os.makedirs(repo)
        self.git(repo, "init", "-q")
        self.write_files(repo, files)
        self.commit(repo, "base")
        return repo

    def history(self, total=7, bad_from=4):
        repo = self.make_repo({".gitignore": "junk\n", "val": "good\n"})
        good = self.git(repo, "rev-parse", "HEAD")
        for i in range(1, total + 1):
            self.write_files(repo, {"val": "good\n" if i < bad_from else "bad\n", "c%d" % i: "x\n"})
            self.commit(repo, "c%d" % i)
        return repo, good

    def run_cmd(self, argv, cwd=None, timeout=120, **extra):
        env = dict(self.env)
        env.update(extra)
        return subprocess.run(argv, cwd=cwd, env=env, timeout=timeout, universal_newlines=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def alive(self, marker):
        return subprocess.run(["pgrep", "-f", marker], stdout=subprocess.DEVNULL).returncode == 0

    def reap_later(self, marker):
        self.addCleanup(subprocess.run, ["pkill", "-f", marker], stdout=subprocess.DEVNULL)


class LibTests(Base):
    def test_kill_tree_kills_descendants(self):
        kid = os.path.join(self.base, "kid")
        script = '''
. "$LIB"
bash -c 'sleep 3573 & echo $! >"$KID"; wait' &
root=$!
i=0; while [ ! -s "$KID" ] && [ $i -lt 100 ]; do sleep 0.1; i=$((i+1)); done
sd_kill_tree "$root"
kid=$(cat "$KID")
if kill -0 "$kid" 2>/dev/null; then echo KID_ALIVE; kill -9 "$kid" 2>/dev/null; else echo KID_DEAD; fi
'''
        self.reap_later("sleep 3573")
        done = self.run_cmd(["bash", "-c", script], LIB=LIB, KID=kid)
        self.assertIn("KID_DEAD", done.stdout, done.stdout + done.stderr)


class StressTests(Base):
    def test_baseline_needs_positive_runs(self):
        done = self.run_cmd(["bash", STRESS, "-n", "1", "-b", "5/0", "--", "true"])
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        self.assertIn("N > 0", done.stderr)

    def test_sigint_kills_running_workers(self):
        marker = "sleep 3574"
        self.reap_later(marker)
        out = os.path.join(self.base, "out")
        proc = subprocess.Popen(["bash", STRESS, "-n", "4", "-j", "4", "-o", out, "--", "sleep", "3574"],
                                env=self.env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                start_new_session=True)
        self.assertTrue(wait_until(lambda: len(glob.glob(os.path.join(out, "tmp.*"))) >= 4, 20))
        time.sleep(0.5)
        proc.send_signal(signal.SIGINT)
        rc = proc.wait(timeout=30)
        time.sleep(0.5)
        self.assertEqual(rc, 130)
        self.assertFalse(self.alive(marker))


class BisectTests(Base):
    def test_reused_worktree_is_cleaned_of_ignored_files(self):
        repo, good = self.history()
        probe = os.path.join(self.base, "probe.sh")
        self.write_files(self.base, {"probe.sh": STALE_PROBE})
        log = os.path.join(self.base, "stale.log")
        done = self.run_cmd(["bash", BISECT, "-j", "1", good, "HEAD", "--", "sh", probe], cwd=repo, LOG=log)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("FIRST BAD COMMIT", done.stdout)
        self.assertFalse(os.path.exists(log), "a reused worktree still held an ignored file from the last probe")

    def test_sigint_kills_probes_and_removes_worktrees(self):
        marker = "sleep 3575"
        self.reap_later(marker)
        repo, good = self.history()
        proc = subprocess.Popen(["bash", BISECT, "-j", "2", "--no-verify", good, "HEAD", "--", "sleep", "3575"],
                                cwd=repo, env=self.env, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, start_new_session=True)
        self.assertTrue(wait_until(lambda: self.alive(marker), 20))
        time.sleep(0.5)
        proc.send_signal(signal.SIGINT)
        rc = proc.wait(timeout=30)
        time.sleep(0.5)
        self.assertEqual(rc, 130)
        self.assertFalse(self.alive(marker))
        listing = self.git(repo, "worktree", "list", "--porcelain")
        self.assertEqual(listing.count("worktree "), 1, listing)


class PolluterTests(Base):
    def test_build_and_dependency_dirs_are_not_searched(self):
        files = {name: ": ok\n" for name in (
            "a.test.sh", "dist/d.test.sh", ".venv/v.test.sh", ".claude/c.test.sh", "linked/l.test.sh")}
        repo = self.make_repo(files)
        done = self.run_cmd(["bash", POLLUTER, "-j", "1", "--cmd", "sh", "--link", "linked",
                             "pollute.out", "*.test.sh"], cwd=repo)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("across 1 test files", done.stderr)
        self.assertIn("No polluter found", done.stdout)

    def test_leftover_pollution_file_is_not_copied_into_worktrees(self):
        repo = self.make_repo({"t.test.sh": ": ok\n"})
        self.write_files(repo, {"pollute.out": "left over from an earlier run\n"})
        done = self.run_cmd(["bash", POLLUTER, "-j", "1", "--cmd", "sh", "pollute.out", "*.test.sh"], cwd=repo)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("No polluter found", done.stdout)


class SnapshotTests(Base):
    def test_library_is_found_from_a_relative_script_path(self):
        proj = os.path.join(self.base, "proj")
        os.makedirs(proj)
        done = self.run_cmd(["bash", os.path.join("scripts", "snapshot.sh"), proj], cwd=SKILL)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertRegex(done.stdout, r"cpus: \d+")


class ToolTests(Base):
    def test_multi_component_text_routes_to_swarm(self):
        proj = os.path.join(self.base, "plain")
        os.makedirs(proj)
        done = self.run_cmd([sys.executable, TOOL, "probe", "--dir", proj, "--error",
                             "multi-component pipeline output is wrong, many plausible causes"])
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("LANE: SWARM", done.stdout)

    def experiment(self, spec, **extra):
        repo = self.make_repo({"README": "x\n"})
        spec_path = os.path.join(self.base, "exp.json")
        with open(spec_path, "w") as handle:
            json.dump(spec, handle)
        return self.run_cmd([sys.executable, TOOL, "experiment", "--spec", spec_path, "--dir", repo,
                             "-j", "8"], cwd=repo, **extra)

    def test_flaky_arms_run_one_after_another(self):
        probe = os.path.join(self.base, "mark.py")
        self.write_files(self.base, {"mark.py": MARK_PROBE})
        mark = os.path.join(self.base, "marks.txt")
        cmd = "%s %s" % (sys.executable, probe)
        spec = [{"id": "h1", "hypothesis": "arms must not overlap", "cmd": cmd, "treatment_cmd": cmd,
                 "runs": 2, "expect": "treatment_passes"}]
        done = self.experiment(spec, MARK_FILE=mark)
        with open(mark) as handle:
            rows = [line.split() for line in handle.read().splitlines()]
        self.assertEqual([r[0] for r in rows], ["S", "E"] * 4, done.stdout + done.stderr)
        self.assertEqual([r[1] for r in rows], ["control"] * 4 + ["treatment"] * 4)

    def test_partial_improvement_is_not_confirmed(self):
        spec = [{"id": "h1", "hypothesis": "half of the treatment runs pass", "cmd": "false",
                 "treatment_cmd": 'test "$SD_RUN" = 1', "runs": 2, "expect": "treatment_passes"}]
        done = self.experiment(spec)
        self.assertNotIn("[CONFIRMED]", done.stdout, done.stdout + done.stderr)
        self.assertIn("[INCONCLUSIVE] h1", done.stdout)

    def test_full_flip_still_confirms(self):
        spec = [{"id": "h1", "hypothesis": "the treatment passes", "cmd": "false",
                 "treatment_cmd": "true", "runs": 1, "expect": "treatment_passes"}]
        done = self.experiment(spec)
        self.assertIn("[CONFIRMED] h1", done.stdout, done.stdout + done.stderr)


if __name__ == "__main__":
    unittest.main()
