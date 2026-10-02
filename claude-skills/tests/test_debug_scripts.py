"""Black-box tests for claude-systematic-debugging-6.3 scripts/*.sh (K19).

Covers: no orphaned workers after SIGTERM (stress.sh), kill-before-cleanup ordering
(bisect-parallel.sh / find-polluter.sh), the -t warning when timeout/gtimeout are
missing, bisect correctness on a 40-commit fixture, status_of() not forking cat,
and the -j default-docs wording.
"""
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest

SCRIPTS = os.path.realpath(os.path.join(
    os.path.dirname(__file__), "..", "claude-systematic-debugging-6.3", "scripts"))
STRESS = os.path.join(SCRIPTS, "stress.sh")
BISECT = os.path.join(SCRIPTS, "bisect-parallel.sh")
FINDPOL = os.path.join(SCRIPTS, "find-polluter.sh")
SKILL_MD = os.path.realpath(os.path.join(
    os.path.dirname(__file__), "..", "claude-systematic-debugging-6.3", "SKILL.md"))
README = os.path.realpath(os.path.join(
    os.path.dirname(__file__), "..", "claude-systematic-debugging-6.3", "README.md"))


def sh(cmd, cwd=None, env=None, timeout=30):
    return subprocess.run(cmd, cwd=cwd, env=env, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, text=True, timeout=timeout)


def wait_until(predicate, timeout=5.0, interval=0.05):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


def descendants(pid):
    """All pids in pid's process tree (including pid itself), via pgrep -P."""
    all_pids = [pid]
    frontier = [pid]
    while frontier:
        nxt = []
        for p in frontier:
            r = subprocess.run(["pgrep", "-P", str(p)], stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True)
            for line in r.stdout.split():
                try:
                    nxt.append(int(line))
                except ValueError:
                    pass
        all_pids.extend(nxt)
        frontier = nxt
    return all_pids


def alive(pids):
    return [p for p in pids if _is_alive(p)]


def _is_alive(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    # a zombie/defunct process is dead for our purposes
    r = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE, text=True)
    stat = r.stdout.strip()
    return bool(stat) and not stat.startswith("Z")


def pgrep_pids(token):
    r = subprocess.run(["pgrep", "-f", token], stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE, text=True)
    out = []
    for line in r.stdout.split():
        try:
            out.append(int(line))
        except ValueError:
            pass
    return out


def make_fakebin_without_timeout(dest_dir):
    """A PATH directory with symlinks to everything on PATH except timeout/gtimeout."""
    fakebin = os.path.join(dest_dir, "fakebin")
    os.makedirs(fakebin, exist_ok=True)
    for d in os.environ.get("PATH", "").split(os.pathsep):
        if not d or not os.path.isdir(d):
            continue
        try:
            names = os.listdir(d)
        except OSError:
            continue
        for name in names:
            if name in ("timeout", "gtimeout"):
                continue
            dest = os.path.join(fakebin, name)
            if os.path.exists(dest):
                continue
            src = os.path.join(d, name)
            try:
                os.symlink(src, dest)
            except OSError:
                pass
    return fakebin


def init_repo(path):
    subprocess.run(["git", "init", "-q", path], check=True)
    subprocess.run(["git", "-C", path, "config", "user.email", "t@t.example"], check=True)
    subprocess.run(["git", "-C", path, "config", "user.name", "tester"], check=True)


class BaseTC(unittest.TestCase):
    def setUp(self):
        self.tmproot = os.path.realpath(tempfile.mkdtemp(prefix="sdtest."))
        self.addCleanup(shutil.rmtree, self.tmproot, ignore_errors=True)

    def env_with_tmp(self, extra=None):
        env = dict(os.environ)
        env["TMPDIR"] = self.tmproot
        if extra:
            env.update(extra)
        return env


class TestScriptsSyntax(BaseTC):
    def test_bash_syntax_all_scripts(self):
        for f in (STRESS, BISECT, FINDPOL, os.path.join(SCRIPTS, "_lib.sh")):
            r = sh(["bash", "-n", f])
            self.assertEqual(r.returncode, 0, f"{f}: {r.stderr}")


class TestStressNoOrphans(BaseTC):
    def test_sigterm_leaves_no_worker_processes_and_removes_tmp(self):
        # edge case: worker ignores TERM -> must be KILLed after the grace period.
        token = "SDTOK_%d_A" % os.getpid()
        env = self.env_with_tmp()
        proc = subprocess.Popen(
            ["bash", STRESS, "-n", "6", "-j", "3", "--",
             "bash", "-c", "trap '' TERM; echo " + token + "; sleep 30"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
        try:
            self.assertTrue(wait_until(lambda: len(pgrep_pids(token)) > 0, timeout=5),
                             "workers never started")
            time.sleep(0.3)
            roots = pgrep_pids(token)
            self.assertTrue(roots)
            tree_before = set()
            for r in roots:
                tree_before.update(descendants(r))
            self.assertTrue(tree_before)
            proc.send_signal(signal.SIGTERM)
            ok = wait_until(lambda: not alive(tree_before), timeout=3)
            survivors = alive(tree_before)
            self.assertTrue(ok, "worker processes survived SIGTERM: %s" % survivors)
            out, err = proc.communicate(timeout=5)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.communicate()
        self.assertEqual(proc.returncode, 130)
        m = re.search(r"logs in (\S+)", err)
        self.assertIsNotNone(m, err)
        self.assertFalse(os.path.exists(m.group(1)), "temp dir was not removed")

    def test_all_runs_exit_125_contract_preserved(self):
        env = self.env_with_tmp()
        r = sh(["bash", STRESS, "-n", "3", "-j", "3", "--", "bash", "-c", "exit 125"],
               env=env, timeout=20)
        self.assertEqual(r.returncode, 125, r.stdout + r.stderr)
        self.assertIn("all runs exited 125", r.stdout + r.stderr)


class TestBisectFixes(BaseTC):
    def test_no_timeout_warns_like_stress(self):
        fakebin = make_fakebin_without_timeout(self.tmproot)
        env = self.env_with_tmp({"PATH": fakebin})
        repo = os.path.join(self.tmproot, "repo")
        os.makedirs(repo)
        init_repo(repo)
        with open(os.path.join(repo, "f"), "w") as fh:
            fh.write("1")
        subprocess.run(["git", "-C", repo, "add", "."], check=True)
        subprocess.run(["git", "-C", repo, "commit", "-q", "-m", "c1"], check=True)
        with open(os.path.join(repo, "f"), "w") as fh:
            fh.write("2")
        subprocess.run(["git", "-C", repo, "add", "."], check=True)
        subprocess.run(["git", "-C", repo, "commit", "-q", "-m", "c2"], check=True)
        r = sh(["bash", BISECT, "-j", "1", "-t", "5", "HEAD~1", "HEAD", "--", "true"],
               cwd=repo, env=env, timeout=30)
        self.assertIn("warn: no timeout/gtimeout found; -t ignored", r.stderr)

    def test_status_of_forks_no_cat(self):
        with open(BISECT) as fh:
            src = fh.read()
        m = re.search(r"^status_of\(\)\s*\{[^\n]*\}", src, re.MULTILINE)
        self.assertIsNotNone(m, "status_of() definition not found")
        body = m.group(0)
        self.assertNotIn("cat ", body, "status_of() still forks cat: %s" % body)
        self.assertIn("read", body)

    def test_finds_regression_in_40_commit_fixture(self):
        repo = os.path.join(self.tmproot, "repo40")
        os.makedirs(repo)
        init_repo(repo)
        bad_at = 21
        total = 40
        for i in range(1, total + 1):
            with open(os.path.join(repo, "version.txt"), "w") as fh:
                fh.write(str(i))
            subprocess.run(["git", "-C", repo, "add", "."], check=True)
            subprocess.run(["git", "-C", repo, "commit", "-q", "-m", "v%d" % i], check=True)
        good = subprocess.run(["git", "-C", repo, "rev-list", "--max-parents=0", "HEAD"],
                               stdout=subprocess.PIPE, text=True, check=True).stdout.strip()
        env = self.env_with_tmp()
        r = sh(["bash", BISECT, "-j", "8", good, "HEAD", "--",
                "bash", "-c", "[ \"$(cat version.txt)\" -lt %d ]" % bad_at],
               cwd=repo, env=env, timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("FIRST BAD COMMIT", r.stdout)
        self.assertIn("v%d" % bad_at, r.stdout)

    def test_sigterm_kills_workers_before_removing_worktrees(self):
        token = "SDTOK_%d_B" % os.getpid()
        repo = os.path.join(self.tmproot, "repob")
        os.makedirs(repo)
        init_repo(repo)
        for i in range(1, 6):
            with open(os.path.join(repo, "f"), "w") as fh:
                fh.write(str(i))
            subprocess.run(["git", "-C", repo, "add", "."], check=True)
            subprocess.run(["git", "-C", repo, "commit", "-q", "-m", "c%d" % i], check=True)
        good = subprocess.run(["git", "-C", repo, "rev-list", "--max-parents=0", "HEAD"],
                               stdout=subprocess.PIPE, text=True, check=True).stdout.strip()
        env = self.env_with_tmp()
        proc = subprocess.Popen(
            ["bash", BISECT, "-j", "2", "--no-verify", good, "HEAD", "--",
             "bash", "-c", "trap '' TERM; echo " + token + "; sleep 30"],
            cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
        try:
            self.assertTrue(wait_until(lambda: len(pgrep_pids(token)) > 0, timeout=5),
                             "bisect workers never started")
            time.sleep(0.3)
            roots = pgrep_pids(token)
            tree_before = set()
            for r in roots:
                tree_before.update(descendants(r))
            proc.send_signal(signal.SIGTERM)
            ok = wait_until(lambda: not alive(tree_before), timeout=3)
            survivors = alive(tree_before)
            out, err = proc.communicate(timeout=5)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.communicate()
        self.assertTrue(ok, "bisect worker processes survived SIGTERM: %s" % survivors)
        self.assertNotIn("No such file or directory", err)
        wl = subprocess.run(["git", "-C", repo, "worktree", "list"],
                             stdout=subprocess.PIPE, text=True, check=True).stdout
        self.assertNotIn(os.sep + "w1", wl)
        self.assertNotIn(os.sep + "w2", wl)


class TestFindPolluterFixes(BaseTC):
    def test_sigterm_kills_workers_before_removing_worktrees(self):
        token = "SDTOK_%d_C" % os.getpid()
        repo = os.path.join(self.tmproot, "repoc")
        os.makedirs(repo)
        init_repo(repo)
        for name in ("a.test.js", "b.test.js"):
            with open(os.path.join(repo, name), "w") as fh:
                fh.write("// test\n")
        subprocess.run(["git", "-C", repo, "add", "."], check=True)
        subprocess.run(["git", "-C", repo, "commit", "-q", "-m", "add tests"], check=True)
        runner_script = os.path.join(self.tmproot, "ignore_term.sh")
        with open(runner_script, "w") as fh:
            fh.write("#!/usr/bin/env bash\ntrap '' TERM\necho \"$1\"\nsleep 30\n")
        os.chmod(runner_script, 0o755)
        env = self.env_with_tmp()
        proc = subprocess.Popen(
            ["bash", FINDPOL, "-j", "2", "--cmd", "bash " + runner_script + " " + token + " --",
             "no_such_pollution_marker", "*.test.js"],
            cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
        try:
            self.assertTrue(wait_until(lambda: len(pgrep_pids(token)) > 0, timeout=5),
                             "find-polluter workers never started")
            time.sleep(0.3)
            roots = pgrep_pids(token)
            tree_before = set()
            for r in roots:
                tree_before.update(descendants(r))
            proc.send_signal(signal.SIGTERM)
            ok = wait_until(lambda: not alive(tree_before), timeout=3)
            survivors = alive(tree_before)
            out, err = proc.communicate(timeout=5)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.communicate()
        self.assertTrue(ok, "find-polluter worker processes survived SIGTERM: %s" % survivors)
        self.assertNotIn("No such file or directory", err)
        wl = subprocess.run(["git", "-C", repo, "worktree", "list"],
                             stdout=subprocess.PIPE, text=True, check=True).stdout
        self.assertNotIn(os.sep + "w1", wl)
        self.assertNotIn(os.sep + "w2", wl)


class TestTreeKillNoRespawn(BaseTC):
    """F27: sd_kill_tree must freeze the tree so nothing can spawn between snapshot and kill."""

    def test_stress_sigterm_leaves_no_late_spawned_child(self):
        token = "3%d" % (os.getpid() + 500000)
        env = self.env_with_tmp()
        proc = subprocess.Popen(
            ["bash", STRESS, "-n", "2", "-j", "2", "--",
             "sh", "-c", "sleep 3; sleep " + token],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
        try:
            self.assertTrue(wait_until(lambda: len(pgrep_pids("sleep 3$")) > 0, timeout=5),
                             "workers never started")
            time.sleep(0.5)
            proc.send_signal(signal.SIGTERM)
            proc.communicate(timeout=10)
            time.sleep(2)
            late = pgrep_pids("sleep " + token)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.communicate()
            for p in pgrep_pids("sleep " + token):
                try:
                    os.kill(p, signal.SIGKILL)
                except OSError:
                    pass
        self.assertEqual(late, [], "process spawned after SIGTERM survived: %s" % late)

    def test_find_polluter_sigterm_leaves_no_runner_and_clean_worktrees(self):
        token = "SDTOK_%d_F" % os.getpid()
        repo = os.path.join(self.tmproot, "repof")
        os.makedirs(repo)
        init_repo(repo)
        for i in range(6):
            with open(os.path.join(repo, "t%d.test.js" % i), "w") as fh:
                fh.write("// test\n")
        subprocess.run(["git", "-C", repo, "add", "."], check=True)
        subprocess.run(["git", "-C", repo, "commit", "-q", "-m", "add tests"], check=True)
        runner_script = os.path.join(self.tmproot, "slow.sh")
        with open(runner_script, "w") as fh:
            fh.write("#!/usr/bin/env bash\nsleep 30\n")
        os.chmod(runner_script, 0o755)
        env = self.env_with_tmp()
        proc = subprocess.Popen(
            ["bash", FINDPOL, "-j", "2", "--cmd", "bash " + runner_script + " " + token,
             "no_such_pollution_marker", "*.test.js"],
            cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
        try:
            self.assertTrue(wait_until(lambda: len(pgrep_pids(token)) > 0, timeout=8),
                             "runners never started")
            time.sleep(0.5)
            proc.send_signal(signal.SIGTERM)
            out, err = proc.communicate(timeout=15)
            time.sleep(1.5)
            late = pgrep_pids(token)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.communicate()
            for p in pgrep_pids(token):
                try:
                    os.kill(p, signal.SIGKILL)
                except OSError:
                    pass
        self.assertEqual(late, [], "runner survived SIGTERM: %s" % late)
        self.assertNotIn("No such file", err)
        wl = subprocess.run(["git", "-C", repo, "worktree", "list"],
                             stdout=subprocess.PIPE, text=True, check=True).stdout
        self.assertEqual(len(wl.strip().splitlines()), 1, wl)

    def test_sd_kill_tree_freezes_before_killing(self):
        token = "4%d" % (os.getpid() + 500000)
        lib = os.path.join(SCRIPTS, "_lib.sh")
        script = (". '%s'; sh -c 'sleep 1; sleep %s' & p=$!; sleep 0.3; "
                  "sd_kill_tree $p; sleep 2; pgrep -f 'sleep %s' | wc -l" % (lib, token, token))
        r = sh(["bash", "-c", script], timeout=20)
        for p in pgrep_pids("sleep " + token):
            try:
                os.kill(p, signal.SIGKILL)
            except OSError:
                pass
        self.assertEqual(r.stdout.strip(), "0", r.stdout + r.stderr)
        with open(lib) as fh:
            src = fh.read()
        self.assertRegex(src, r"kill -STOP|kill -s STOP|kill -SIGSTOP")


class TestKillTreeGraceAndSignals(BaseTC):
    """F42: TERM grace after the freeze; INT/TERM ignored while the kill runs."""

    def test_stress_sigterm_runs_command_term_trap(self):
        marker = os.path.join(self.tmproot, "term-marker")
        body = ('trap "echo trapped > %s; exit 0" TERM; sleep 30 & wait' % marker)
        env = self.env_with_tmp()
        proc = subprocess.Popen(
            ["bash", STRESS, "-n", "1", "-j", "1", "--", "bash", "-c", body],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
        try:
            self.assertTrue(wait_until(lambda: len(pgrep_pids("sleep 30")) > 0, timeout=5),
                             "worker never started")
            time.sleep(0.5)
            proc.send_signal(signal.SIGTERM)
            proc.communicate(timeout=10)
            self.assertTrue(wait_until(lambda: os.path.exists(marker), timeout=2),
                             "command's TERM trap did not run before SIGKILL")
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.communicate()
            for p in pgrep_pids("sleep 30"):
                try:
                    os.kill(p, signal.SIGKILL)
                except OSError:
                    pass

    def test_sd_kill_tree_kills_term_ignoring_survivors_after_grace(self):
        lib = os.path.join(SCRIPTS, "_lib.sh")
        token = "5%d" % (os.getpid() + 500000)
        script = (". '%s'; sh -c 'trap \"\" TERM; while :; do sleep %s; done' & p=$!; "
                  "sleep 0.3; sd_kill_tree $p; kill -0 $p 2>/dev/null && echo ALIVE || echo DEAD" % (lib, token))
        r = sh(["bash", "-c", script], timeout=20)
        time.sleep(0.5)
        left = pgrep_pids("sleep " + token)
        for p in left:
            try:
                os.kill(p, signal.SIGKILL)
            except OSError:
                pass
        self.assertEqual(r.stdout.strip(), "DEAD", r.stdout + r.stderr)
        self.assertEqual(left, [])

    def test_stress_sigterm_kills_children_forked_during_term_grace(self):
        token = "6%d" % (os.getpid() + 500000)
        body = ('trap "" TERM; while :; do sleep %s & sleep 0.02; done' % token)
        env = self.env_with_tmp()
        proc = subprocess.Popen(
            ["bash", STRESS, "-n", "1", "-j", "1", "--", "bash", "-c", body],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
        try:
            self.assertTrue(wait_until(lambda: len(pgrep_pids("sleep " + token)) > 2, timeout=5),
                             "worker never started forking")
            proc.send_signal(signal.SIGTERM)
            proc.communicate(timeout=15)
            time.sleep(1.0)
            left = alive(pgrep_pids("sleep " + token))
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.communicate()
            for p in pgrep_pids("sleep " + token):
                try:
                    os.kill(p, signal.SIGKILL)
                except OSError:
                    pass
        self.assertEqual(left, [], "children forked during the TERM grace survived: %s" % left)

    def test_sd_kill_tree_rescans_after_grace_and_refreezes(self):
        lib = os.path.join(SCRIPTS, "_lib.sh")
        token = "7%d" % (os.getpid() + 500000)
        script = (". '%s'; bash -c 'trap \"\" TERM; while :; do sleep %s & sleep 0.02; done' & p=$!; "
                  "sleep 0.3; sd_kill_tree $p; sleep 0.5; "
                  "kill -0 $p 2>/dev/null && echo ROOT_ALIVE; pgrep -f 'sleep %s' | wc -l" % (lib, token, token))
        r = sh(["bash", "-c", script], timeout=20)
        left = alive(pgrep_pids("sleep " + token))
        for p in left:
            try:
                os.kill(p, signal.SIGKILL)
            except OSError:
                pass
        self.assertNotIn("ROOT_ALIVE", r.stdout)
        self.assertEqual(left, [], r.stdout + r.stderr)

    def test_sd_kill_tree_ignores_int_term_during_kill_and_restores_traps(self):
        lib = os.path.join(SCRIPTS, "_lib.sh")
        script = (". '%s'; trap 'echo GOT' INT TERM; "
                  "sh -c 'trap \"\" TERM; while :; do sleep 1; done' & p=$!; sleep 0.3; "
                  "(sleep 0.1; kill -INT $$; kill -TERM $$) & "
                  "sd_kill_tree $p; sleep 0.3; echo done; trap -p INT TERM" % lib)
        r = sh(["bash", "-c", script], timeout=20)
        self.assertNotIn("GOT", r.stdout.splitlines(), r.stdout + r.stderr)
        self.assertIn("done", r.stdout)
        self.assertIn("trap -- 'echo GOT' SIGINT", r.stdout.replace(" INT", " SIGINT"))
        self.assertIn("trap -- 'echo GOT' SIGTERM", r.stdout.replace(" TERM", " SIGTERM"))


class TestSnapshotLevels(BaseTC):
    def _lib_func_src(self, name):
        with open(os.path.join(SCRIPTS, "_lib.sh")) as fh:
            src = fh.read()
        m = re.search(r"^" + name + r"\(\) \{.*?^\}", src, re.S | re.M)
        self.assertIsNotNone(m, name + " missing from _lib.sh")
        return m.group(0)

    def test_no_per_pid_forks_in_source(self):
        for name in ("sd_children_of", "sd_levels"):
            body = self._lib_func_src(name)
            self.assertNotIn("pgrep", body, name)
            self.assertNotIn("kill -0", body, name)
        self.assertIn("ps -eo pid=,ppid=", self._lib_func_src("sd_levels"))
        self.assertIn("awk", self._lib_func_src("sd_levels"))

    def test_sd_levels_one_ps_call_and_correct_tree(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        tmp = os.path.realpath(tmp)
        real_ps = shutil.which("ps")
        fake = os.path.join(tmp, "bin")
        os.mkdir(fake)
        log = os.path.join(tmp, "calls.log")
        for name, body in (
            ("ps", '#!/bin/sh\necho ps >> "%s"\nexec "%s" "$@"\n' % (log, real_ps)),
            ("pgrep", '#!/bin/sh\necho pgrep >> "%s"\nexit 1\n' % log),
        ):
            path = os.path.join(fake, name)
            with open(path, "w") as fh:
                fh.write(body)
            os.chmod(path, 0o755)
        script = os.path.join(tmp, "t.sh")
        with open(script, "w") as fh:
            fh.write(
                ". \"%s/_lib.sh\"\n"
                "bash -c 'sleep 30 & bash -c \"sleep 30 & sleep 30 & wait\" & wait' &\n"
                "root=$!\n"
                "sleep 1\n"
                ": > \"%s\"\n"
                "PATH=\"%s:$PATH\"\n"
                "sd_levels \"$root\"\n"
                "echo ROOT=$root\n"
                "kill -KILL $(sd_levels \"$root\" | awk '{print $2}') $root 2>/dev/null\n"
                % (SCRIPTS, log, fake))
        r = sh(["bash", script], timeout=30)
        out = r.stdout
        root = re.search(r"ROOT=(\d+)", out).group(1)
        lines = [l.split() for l in out.splitlines() if re.match(r"^\d+ \d+$", l)]
        self.assertEqual(len(lines), 4, out)
        self.assertEqual([d for d, _ in lines[:4]].count("1"), 2, out)
        self.assertEqual([d for d, _ in lines[:4]].count("2"), 2, out)
        self.assertNotIn(root, [p for _, p in lines])
        with open(log) as fh:
            calls = fh.read().split()
        self.assertEqual(calls.count("pgrep"), 0, calls)
        self.assertEqual(calls.count("ps"), 2, calls)  # exactly one per sd_levels scan


class TestDocs(BaseTC):
    def test_j_default_docs_say_min64_cpus(self):
        with open(SKILL_MD) as fh:
            skill = fh.read()
        self.assertNotIn("`-j` defaults to CPUs)", skill,
                          "SKILL.md still claims -j defaults to plain CPU count")
        self.assertIn("min(64, CPUs)", skill)
        with open(BISECT) as fh:
            bisect_src = fh.read()
        self.assertIn("min(64, CPUs) - 1", bisect_src)
        with open(STRESS) as fh:
            stress_src = fh.read()
        self.assertIn("min(64, CPUs)", stress_src)

    def test_readme_scopes_j_default_per_script(self):
        with open(README) as fh:
            readme = fh.read()
        line = [l for l in readme.splitlines() if l.startswith("- Docs:") and "-j" in l]
        self.assertEqual(len(line), 1, "README Docs -j line missing")
        line = line[0]
        self.assertIn("stress.sh", line)
        self.assertIn("bisect-parallel.sh", line)
        self.assertIn("min(64, CPUs)", line)
        self.assertIn("find-polluter.sh", line)
        self.assertIn("min(16, CPUs)", line)

    def test_readme_records_the_fixes(self):
        with open(README) as fh:
            readme = fh.read()
        self.assertIn("Fixes", readme)
        low = readme.lower()
        self.assertTrue("orphan" in low or "sigterm" in low,
                         "README does not document the orphaned-worker / SIGTERM fix")
        self.assertTrue("kill" in low, "README does not mention killing workers before cleanup")


if __name__ == "__main__":
    unittest.main()
