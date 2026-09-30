"""Black-box tests for writing-plans-6.2/scripts/plan_tool.py (slice K14).

Covers: W8-1 (preload never cancels the skill), W8-6 (contract hashing),
W8-7 (shared warn/fail mark helper), W8-8 (stale agent detection),
W8-10 (git --no-optional-locks), W8-11 + SKILL.md contract items (static
text checks), and perf (a)-(d).

Runs the real script against throwaway git repos built under the system
temp dir. Never touches the real ~/.claude or this repo's own state.
"""
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(TESTS_DIR)  # claude-skills/
WP_DIR = os.path.join(BASE_DIR, "writing-plans-6.2")
TOOL = os.path.join(WP_DIR, "scripts", "plan_tool.py")
SKILL_MD = os.path.join(WP_DIR, "SKILL.md")
CHANGELOG = os.path.join(WP_DIR, "CHANGELOG.md")


def run_tool(args, cwd, env=None, timeout=25, input_text=None):
    e = dict(os.environ)
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    if env:
        e.update(env)
    return subprocess.run(
        [sys.executable, TOOL] + list(args),
        cwd=cwd, env=e, capture_output=True, text=True,
        timeout=timeout, input=input_text,
    )


def make_repo(files=None, commit=True):
    d = os.path.realpath(tempfile.mkdtemp())
    subprocess.run(["git", "init", "-q"], cwd=d, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=d, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=d, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=d, check=True)
    files = dict(files or {})
    if commit and not files:
        files["README.md"] = "seed\n"
    for rel, content in files.items():
        p = os.path.join(d, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True) if os.path.dirname(p) else None
        with open(p, "w") as f:
            f.write(content)
    if commit:
        subprocess.run(["git", "add", "-A"], cwd=d, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=d, check=True)
    return d


def fake_home():
    h = os.path.realpath(tempfile.mkdtemp())
    os.makedirs(os.path.join(h, ".claude", "agents"), exist_ok=True)
    return h


PLAN_2TASK = """# Demo Plan

**Goal:** demo

**Architecture:** demo

**Tech Stack:** python

## Global Constraints

- keep it simple

## Contracts

#### T01: First
- Files: `src/a.py`
- Produces: `def a() -> None`

#### T02: Second
- Files: `src/b.py`
- Produces: `def b() -> None`
"""


def basic_body(files, produce_sig, code, extra=""):
    files_lines = "\n".join("- `%s`" % f for f in files)
    return (
        "**Files:**\n%s\n\n%s"
        "- [ ] **Step 1: implement**\n\n"
        "```python\n%s\n```\n\n"
        "%s\n\n"
        "Then `git commit -m \"feat\"`.\n"
    ) % (files_lines, extra, code, produce_sig)


class ContextNeverCancelsTests(unittest.TestCase):
    """W8-1: the preload must always exit 0 and print bounded output."""

    def setUp(self):
        self.repo = make_repo(files={"spec.md": "# Spec\n\nSome content.\n"})
        self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)

    def test_variants_exit_zero(self):
        variants = [
            [],
            [""],
            ["--thorough"],
            ["--thorough spec.md"],
            ["let's plan (see spec)"],
            ["no/such/spec.md"],
            ['has "a quote" inside'],
        ]
        for v in variants:
            with self.subTest(argv=v):
                p = run_tool(["context"] + v, cwd=self.repo)
                self.assertEqual(p.returncode, 0, "argv=%r stderr=%s" % (v, p.stderr))

    def test_thorough_with_spec_is_parsed_out_of_one_quoted_token(self):
        p = run_tool(["context", "--thorough spec.md"], cwd=self.repo)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("THOROUGH", p.stdout)
        self.assertIn("spec:", p.stdout)

    def test_detached_head(self):
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.repo,
                              capture_output=True, text=True, check=True).stdout.strip()
        subprocess.run(["git", "checkout", "-q", "--detach", sha], cwd=self.repo, check=True)
        p = run_tool(["context"], cwd=self.repo)
        self.assertEqual(p.returncode, 0, p.stderr)

    def test_no_commits_repo(self):
        d = make_repo(commit=False)
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        p = run_tool(["context"], cwd=d)
        self.assertEqual(p.returncode, 0, p.stderr)

    def test_outside_git_repo(self):
        d = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        p = run_tool(["context"], cwd=d)
        self.assertEqual(p.returncode, 0, p.stderr)


class ContextPerfTests(unittest.TestCase):
    """Perf (a): bounded output; W8-10: no-optional-locks."""

    def test_bounded_output_on_a_large_repo(self):
        files = {"spec.md": "# Spec\n"}
        for i in range(320):
            files["pkg%03d/mod%03d.py" % (i // 20, i)] = "x = 1\n"
        repo = make_repo(files=files)
        self.addCleanup(shutil.rmtree, repo, ignore_errors=True)
        p = run_tool(["context"], cwd=repo)
        self.assertEqual(p.returncode, 0, p.stderr)
        lines = p.stdout.rstrip("\n").splitlines()
        self.assertLessEqual(len(lines), 55, "got %d lines" % len(lines))
        idx = next(i for i, l in enumerate(lines) if l.startswith("files ("))
        shown = len(lines) - idx - 1
        self.assertLessEqual(shown, 30, "listed %d files" % shown)

    def test_uses_no_optional_locks_for_status(self):
        real_git = shutil.which("git")
        self.assertIsNotNone(real_git)
        bindir = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, bindir, ignore_errors=True)
        log = os.path.join(bindir, "git.log")
        wrapper = os.path.join(bindir, "git")
        with open(wrapper, "w") as f:
            f.write("#!/bin/sh\necho \"$@\" >> \"%s\"\nexec \"%s\" \"$@\"\n" % (log, real_git))
        os.chmod(wrapper, os.stat(wrapper).st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        repo = make_repo(files={"spec.md": "# S\n"})
        self.addCleanup(shutil.rmtree, repo, ignore_errors=True)
        env = {"PATH": bindir + os.pathsep + os.environ.get("PATH", "")}
        p = run_tool(["context"], cwd=repo, env=env)
        self.assertEqual(p.returncode, 0, p.stderr)
        with open(log) as f:
            calls = f.read().splitlines()
        status_calls = [c for c in calls if "status" in c]
        self.assertTrue(status_calls, "no git status call logged: %r" % calls)
        self.assertTrue(any("--no-optional-locks" in c for c in status_calls),
                         "status call missing --no-optional-locks: %r" % status_calls)


class StaleAgentTests(unittest.TestCase):
    """W8-8: a stale __PLAN_TOOL__ placeholder agent must be flagged regardless of cap."""

    def test_stale_agent_flags_setup_hint_even_at_max_cap(self):
        home = fake_home()
        self.addCleanup(shutil.rmtree, home, ignore_errors=True)
        repo = make_repo(files={"spec.md": "# S\n"})
        self.addCleanup(shutil.rmtree, repo, ignore_errors=True)
        agent_path = os.path.join(home, ".claude", "agents", "plan-task-writer.md")
        with open(agent_path, "w") as f:
            f.write("some agent using __PLAN_TOOL__ hook-lint\n")
        env = {"HOME": home, "CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS": "64"}
        p = run_tool(["context"], cwd=repo, env=env)
        self.assertEqual(p.returncode, 0, p.stderr)
        out = p.stdout.lower()
        self.assertIn("setup", out)
        self.assertIn("apply", out)
        self.assertTrue("stale" in out or "placeholder" in out, p.stdout)


class ContractHashingTests(unittest.TestCase):
    """W8-6: re-running contracts after a contract change drops that task's body+.ok."""

    def test_changed_contract_drops_body_and_mark_unchanged_keeps_it(self):
        home = fake_home()
        self.addCleanup(shutil.rmtree, home, ignore_errors=True)
        repo = make_repo(files={"src/a.py": "", "src/b.py": ""})
        self.addCleanup(shutil.rmtree, repo, ignore_errors=True)
        plan = os.path.join(repo, "plan.md")
        with open(plan, "w") as f:
            f.write(PLAN_2TASK)
        env = {"HOME": home}
        p = run_tool(["contracts", plan], cwd=repo, env=env)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        work = os.path.join(repo, ".work", "plan")
        tasks = os.path.join(work, "tasks")
        with open(os.path.join(tasks, "T01.md"), "w") as f:
            f.write(basic_body(["src/a.py"], "def a() -> None", "def a() -> None:\n    pass"))
        with open(os.path.join(tasks, "T02.md"), "w") as f:
            f.write(basic_body(["src/b.py"], "def b() -> None", "def b() -> None:\n    pass"))
        for t in ("T01", "T02"):
            p = run_tool(["lint-task", plan, os.path.join(tasks, t + ".md")], cwd=repo, env=env)
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            self.assertTrue(os.path.exists(os.path.join(tasks, t + ".md.ok")))
        with open(plan, "w") as f:
            f.write(PLAN_2TASK.replace("def a() -> None`", "def a(x: int) -> None`"))
        p = run_tool(["contracts", plan], cwd=repo, env=env)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertFalse(os.path.exists(os.path.join(tasks, "T01.md")), "changed task body should be dropped")
        self.assertFalse(os.path.exists(os.path.join(tasks, "T01.md.ok")), "changed task .ok should be dropped")
        self.assertTrue(os.path.exists(os.path.join(tasks, "T02.md")), "unchanged task body should be kept")
        self.assertTrue(os.path.exists(os.path.join(tasks, "T02.md.ok")), "unchanged task .ok should be kept")


class MarkHelperTests(unittest.TestCase):
    """W8-7: lint-task and hook-lint share one mark helper (.warn / .fail / .ok)."""

    def setUp(self):
        self.home = fake_home()
        self.addCleanup(shutil.rmtree, self.home, ignore_errors=True)
        self.repo = make_repo(files={"src/a.py": ""})
        self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)
        self.plan = os.path.join(self.repo, "plan.md")
        with open(self.plan, "w") as f:
            f.write("# P\n\n## Contracts\n\n#### T01: Only\n- Files: `src/a.py`\n- Produces: `def a() -> None`\n")
        self.env = {"HOME": self.home}
        p = run_tool(["contracts", self.plan], cwd=self.repo, env=self.env)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.task = os.path.join(self.repo, ".work", "plan", "tasks", "T01.md")

    def _lint(self):
        return run_tool(["lint-task", self.plan, self.task], cwd=self.repo, env=self.env)

    def test_warn_written_then_cleared(self):
        with open(self.task, "w") as f:
            f.write(basic_body(["src/a.py"], "def a() -> None", "def a() -> None:\n    pass",
                                extra="- Modify: `src/zzz_missing.py`\n\n"))
        p = self._lint()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        warn_path = self.task + ".warn"
        self.assertTrue(os.path.exists(warn_path), "expected a .warn mark")
        with open(self.task, "w") as f:
            f.write(basic_body(["src/a.py"], "def a() -> None", "def a() -> None:\n    pass"))
        p = self._lint()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertFalse(os.path.exists(warn_path), "stale .warn should be cleared on a clean lint")

    def test_fail_written_on_error_then_cleared_on_success(self):
        with open(self.task, "w") as f:
            f.write("this task body has no Files block and no code\n")
        p = self._lint()
        self.assertNotEqual(p.returncode, 0)
        fail_path = self.task + ".fail"
        self.assertTrue(os.path.exists(fail_path), "expected a .fail mark on lint error")
        self.assertFalse(os.path.exists(self.task + ".ok"))
        with open(self.task, "w") as f:
            f.write(basic_body(["src/a.py"], "def a() -> None", "def a() -> None:\n    pass"))
        p = self._lint()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertFalse(os.path.exists(fail_path), "stale .fail should be cleared once lint passes")

    def _hook_lint(self):
        payload = json.dumps({"tool_input": {"file_path": self.task}})
        return run_tool(["hook-lint"], cwd=self.repo, env=self.env, input_text=payload)

    def test_hook_lint_writes_warn_and_fail_like_lint_task(self):
        with open(self.task, "w") as f:
            f.write(basic_body(["src/a.py"], "def a() -> None", "def a() -> None:\n    pass",
                                extra="- Modify: `src/zzz_missing.py`\n\n"))
        p = self._hook_lint()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertTrue(os.path.exists(self.task + ".warn"), "hook-lint should also write .warn")
        with open(self.task, "w") as f:
            f.write("broken body, no files block\n")
        p = self._hook_lint()
        self.assertEqual(p.returncode, 0)  # hook never fails the tool call itself
        self.assertTrue(os.path.exists(self.task + ".fail"), "hook-lint should also write .fail on error")


class WaitEarlyPendingTests(unittest.TestCase):
    """Perf (c): wait returns PENDING early once all pending tasks are failing & stale,
    but staleness is measured from wait START, not from the file's absolute mtime
    (a task already old before wait began must not fire the early line prematurely)."""

    def _make_stale_plan(self, age_seconds=100):
        repo = make_repo()
        self.addCleanup(shutil.rmtree, repo, ignore_errors=True)
        plan = os.path.join(repo, "plan.md")
        with open(plan, "w") as f:
            f.write("# P\n")
        work = os.path.join(repo, ".work", "plan")
        tasks = os.path.join(work, "tasks")
        os.makedirs(tasks)
        info = {"plan": plan, "spec": None, "repo": repo, "allow": [], "agents": 4,
                "tasks": ["T01", "T02"], "groups": {}, "review": []}
        with open(os.path.join(work, "work.json"), "w") as f:
            json.dump(info, f)
        old = time.time() - age_seconds
        for t in ("T01", "T02"):
            tp = os.path.join(tasks, t + ".md")
            with open(tp, "w") as f:
                f.write("body\n")
            fp = tp + ".fail"
            with open(fp, "w") as f:
                f.write("err\n")
            os.utime(tp, (old, old))
            os.utime(fp, (old, old))
        return repo, plan

    def test_no_early_line_when_stale_before_wait_started(self):
        """Files already >=100s old BEFORE wait starts: with the default 45s min_age
        and a 3s timeout, wait must return the normal timeout PENDING after ~3s, never
        the early 'all pending are failing' line - staleness is measured from wait start."""
        home = fake_home()
        self.addCleanup(shutil.rmtree, home, ignore_errors=True)
        repo, plan = self._make_stale_plan(age_seconds=100)
        t0 = time.time()
        p = run_tool(["wait", plan, "--timeout", "3", "--idle", "100"], cwd=repo,
                      env={"HOME": home}, timeout=15)
        elapsed = time.time() - t0
        self.assertGreaterEqual(elapsed, 2.5, "should run the full timeout, not return instantly")
        self.assertLess(elapsed, 10)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("PENDING", p.stdout)
        self.assertNotIn("all pending are failing", p.stdout)
        self.assertIn("timeout", p.stdout)

    def test_early_line_when_unchanged_for_min_age_after_wait_started(self):
        """No body/.fail change for >=min_age seconds AFTER wait started: wait returns
        the early PENDING line. min_age is lowered via PLAN_TOOL_WAIT_MIN_AGE so the
        test doesn't need to sleep the real default of 45s."""
        home = fake_home()
        self.addCleanup(shutil.rmtree, home, ignore_errors=True)
        repo, plan = self._make_stale_plan(age_seconds=100)
        t0 = time.time()
        try:
            p = run_tool(["wait", plan, "--timeout", "500", "--idle", "500"], cwd=repo,
                          env={"HOME": home, "PLAN_TOOL_WAIT_MIN_AGE": "1"}, timeout=10)
        except subprocess.TimeoutExpired:
            self.fail("wait did not return early once unchanged for min_age after wait started")
        elapsed = time.time() - t0
        self.assertLess(elapsed, 10, "wait should return early, took %.1fs" % elapsed)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("PENDING", p.stdout)
        self.assertIn("all pending are failing", p.stdout)
        # hedge: tells the leader to re-wait if an agent is still running, and only
        # otherwise to re-dispatch.
        self.assertIn("still running", p.stdout)
        self.assertIn("run wait again", p.stdout)
        self.assertIn("re-dispatch", p.stdout)

    def test_early_line_when_files_first_written_after_wait_started(self):
        """Body and .fail first appear ~1s AFTER wait starts, then never change: quiet
        time counts from that observed change, so with min_age=2 wait returns the early
        line (~3s), far below --timeout/--idle."""
        home = fake_home()
        self.addCleanup(shutil.rmtree, home, ignore_errors=True)
        repo, plan = self._make_stale_plan(age_seconds=100)
        tasks = os.path.join(repo, ".work", "plan", "tasks")
        for t in ("T01", "T02"):
            os.remove(os.path.join(tasks, t + ".md"))
            os.remove(os.path.join(tasks, t + ".md.fail"))
        e = dict(os.environ)
        e.update({"HOME": home, "PLAN_TOOL_WAIT_MIN_AGE": "2", "PYTHONDONTWRITEBYTECODE": "1"})
        t0 = time.time()
        proc = subprocess.Popen([sys.executable, TOOL, "wait", plan, "--timeout", "500", "--idle", "500"],
                                cwd=repo, env=e, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: proc.poll() is None and proc.kill())
        time.sleep(1.0)
        for t in ("T01", "T02"):
            for name, body in ((t + ".md", "body\n"), (t + ".md.fail", "err\n")):
                with open(os.path.join(tasks, name), "w") as f:
                    f.write(body)
        try:
            out, err = proc.communicate(timeout=12)
        except subprocess.TimeoutExpired:
            proc.kill()
            self.fail("wait did not return early after files were written post-start")
        elapsed = time.time() - t0
        self.assertLess(elapsed, 10, "took %.1fs" % elapsed)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("PENDING", out)
        self.assertIn("all pending are failing", out)

    def test_non_integer_min_age_falls_back_to_default(self):
        """PLAN_TOOL_WAIT_MIN_AGE=abc must not crash; default 45 applies, so with old
        files and --timeout 3 the normal timeout PENDING line is printed."""
        home = fake_home()
        self.addCleanup(shutil.rmtree, home, ignore_errors=True)
        repo, plan = self._make_stale_plan(age_seconds=100)
        p = run_tool(["wait", plan, "--timeout", "3", "--idle", "100"], cwd=repo,
                      env={"HOME": home, "PLAN_TOOL_WAIT_MIN_AGE": "abc"}, timeout=15)
        self.assertNotIn("Traceback", p.stderr)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("PENDING", p.stdout)
        self.assertNotIn("all pending are failing", p.stdout)
        self.assertIn("timeout", p.stdout)


class AssembleParallelNodeTests(unittest.TestCase):
    """Perf (b): JS blocks are checked with node --check, still catching real errors."""

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_flags_bad_js_block_among_many_good_ones(self):
        home = fake_home()
        self.addCleanup(shutil.rmtree, home, ignore_errors=True)
        contracts = ["## Contracts", ""]
        n = 8
        for i in range(1, n + 1):
            tid = "T%02d" % i
            contracts.append("#### %s: Task %d" % (tid, i))
            contracts.append("- Files: `src/m%02d.js`" % i)
            contracts.append("- Produces: `function f%d() {}`" % i)
            contracts.append("")
        plan_text = "# P\n\n" + "\n".join(contracts)
        repo = make_repo()
        self.addCleanup(shutil.rmtree, repo, ignore_errors=True)
        plan = os.path.join(repo, "plan.md")
        with open(plan, "w") as f:
            f.write(plan_text)
        env = {"HOME": home}
        p = run_tool(["contracts", plan], cwd=repo, env=env)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        tasks = os.path.join(repo, ".work", "plan", "tasks")
        for i in range(1, n + 1):
            tid = "T%02d" % i
            code = "function f%d() {}" % i
            if i == 3:
                code = "function f3( {"  # intentionally broken
            with open(os.path.join(tasks, tid + ".md"), "w") as f:
                f.write(basic_body(["src/m%02d.js" % i], "function f%d() {}" % i,
                                    code).replace("```python", "```javascript"))
        p = run_tool(["assemble", plan], cwd=repo, env=env, timeout=60)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("T03", p.stdout)
        for i in (1, 2, 4, 5, 6, 7, 8):
            self.assertNotIn("T%02d:" % i + " code block", p.stdout)


class ReviewerBriefInlineTests(unittest.TestCase):
    """Perf (d): reviewer briefs inline existing target files like writer briefs do."""

    def test_reviewer_brief_inlines_existing_file(self):
        home = fake_home()
        self.addCleanup(shutil.rmtree, home, ignore_errors=True)
        marker = "EXISTING_FILE_MARKER_XYZ"
        repo = make_repo(files={"src/a.py": "# %s\n" % marker})
        self.addCleanup(shutil.rmtree, repo, ignore_errors=True)
        plan = os.path.join(repo, "plan.md")
        with open(plan, "w") as f:
            f.write("# P\n\n## Contracts\n\n#### T01: Only\n- Files: `src/a.py`\n"
                     "- Produces: `def a() -> None`\n")
        env = {"HOME": home}
        p = run_tool(["contracts", plan], cwd=repo, env=env)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        work = os.path.join(repo, ".work", "plan")
        task = os.path.join(work, "tasks", "T01.md")
        with open(task, "w") as f:
            f.write(basic_body(["src/a.py"], "def a() -> None", "def a() -> None:\n    pass",
                                extra="- Modify: `src/a.py`\n\n"))
        p = run_tool(["lint-task", plan, task], cwd=repo, env=env)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        p = run_tool(["review", plan, "--all"], cwd=repo, env=env)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        brief_dir = os.path.join(work, "review-briefs")
        briefs = os.listdir(brief_dir) if os.path.isdir(brief_dir) else []
        self.assertTrue(briefs, "no review briefs written")
        content = ""
        for b in briefs:
            with open(os.path.join(brief_dir, b)) as f:
                content += f.read()
        self.assertIn("Existing files", content)
        self.assertIn(marker, content)


class SkillMdContractTests(unittest.TestCase):
    """W8 SKILL.md contract items."""

    @classmethod
    def setUpClass(cls):
        with open(SKILL_MD, encoding="utf-8") as f:
            cls.text = f.read()

    def test_description_within_limit(self):
        m = re.search(r"^description:\s*(.+)$", self.text, re.M)
        self.assertIsNotNone(m)
        self.assertLessEqual(len(m.group(1)), 1024)

    def test_no_ultracode_mention(self):
        self.assertNotIn("ultracode", self.text.lower())

    def test_no_disabled_superpowers_handoff(self):
        self.assertNotIn("superpowers:", self.text)
        self.assertIn("dev-team", self.text)

    def test_allow_advice_is_in_phase_1(self):
        m1 = re.search(r"^## Phase 1[^\n]*\n", self.text, re.M)
        m2 = re.search(r"^## Phase 2[^\n]*\n", self.text, re.M)
        self.assertIsNotNone(m1)
        self.assertIsNotNone(m2)
        phase1 = self.text[m1.end():m2.start()]
        self.assertIn("--allow", phase1)

    def test_setup_trigger_covers_stale_agent(self):
        m = re.search(r"^## One-time speed setup.*$", self.text, re.M)
        self.assertIsNotNone(m)
        trigger_line = m.group(0)
        self.assertTrue("stale" in trigger_line.lower() or "placeholder" in trigger_line.lower(),
                         trigger_line)


class ChangelogTests(unittest.TestCase):
    def test_records_w8_and_fixed_install_path(self):
        with open(CHANGELOG, encoding="utf-8") as f:
            text = f.read()
        self.assertIn("W8", text)
        self.assertIn("writing-plans-6.2", text)
        self.assertNotIn("~/.claude/skills/writing-plans/", text)


if __name__ == "__main__":
    unittest.main()
