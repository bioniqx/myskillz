"""Black-box coverage tests for claude-writing-plans-6.2/scripts/plan_tool.py (T17).

Covers: partition of tasks into writer groups, risk-based review picking,
assemble, setup and spec coverage. Runs the real script against throwaway git
repos and a fake HOME under the system temp dir.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(TESTS_DIR)  # claude-skills/
TOOL = os.path.join(BASE_DIR, "claude-writing-plans-6.2", "scripts", "plan_tool.py")

HEADER = (
    "# Demo Plan\n\n**Goal:** demo\n\n**Architecture:** demo\n\n"
    "**Tech Stack:** python\n\n## Global Constraints\n\n- keep it simple\n\n"
    "## Contracts\n\n"
)
SPEC = (
    "# Spec\n\n## Alpha feature\n\nalpha text here\n\n"
    "## Beta feature\n\nbeta text here\n"
)


def contract(n, files=None, extra=""):
    """One contract block; task n owns src/m<n>.py and produces def f<n>() -> None."""
    return "#### T%02d: Task %d\n- Files: %s\n- Produces: `def f%d() -> None`\n%s\n" % (
        n, n, files or "`src/m%d.py`" % n, n, extra)


def body(n, files=None):
    path = files or "src/m%d.py" % n
    return (
        "**Files:**\n- Create: `%s`\n\n"
        "- [ ] **Step 1: implement**\n\n"
        "```python\ndef f%d() -> None:\n    pass\n```\n\n"
        "`def f%d() -> None`\n\n"
        "Then `git commit -m \"feat\"`.\n" % (path, n, n)
    )


class PlanCase(unittest.TestCase):
    def setUp(self):
        self.home = os.path.realpath(tempfile.mkdtemp())
        os.makedirs(os.path.join(self.home, ".claude", "agents"))
        self.repo = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.home, ignore_errors=True)
        self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)
        for cmd in (["init", "-q"], ["config", "user.email", "t@example.com"],
                    ["config", "user.name", "T"], ["config", "commit.gpgsign", "false"]):
            subprocess.run(["git"] + cmd, cwd=self.repo, check=True)
        self.write("README.md", "seed\n")
        self.write("src/exists.py", "x = 1\n")
        subprocess.run(["git", "add", "-A"], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=self.repo, check=True)
        self.plan = os.path.join(self.repo, "plan.md")
        self.work = os.path.join(self.repo, ".work", "plan")
        self.tasks = os.path.join(self.work, "tasks")

    def write(self, rel, text):
        p = os.path.join(self.repo, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write(text)
        return p

    def tool(self, *args, timeout=40):
        env = dict(os.environ, HOME=self.home, PYTHONDONTWRITEBYTECODE="1")
        return subprocess.run([sys.executable, TOOL] + list(args), cwd=self.repo,
                              env=env, capture_output=True, text=True, timeout=timeout)

    def start(self, contracts, *extra):
        with open(self.plan, "w") as f:
            f.write(HEADER + contracts)
        p = self.tool("contracts", self.plan, *extra)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        return p

    def finish_bodies(self, ids, files=None):
        for n in ids:
            task = os.path.join(self.tasks, "T%02d.md" % n)
            with open(task, "w") as f:
                f.write(body(n, (files or {}).get(n)))
            p = self.tool("lint-task", self.plan, task)
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def read(self, path):
        with open(path) as f:
            return f.read()


class PartitionTests(PlanCase):
    def test_tasks_beyond_the_agent_cap_share_writers(self):
        self.start("".join(contract(n) for n in range(1, 8)), "--agents", "2")
        with open(os.path.join(self.work, "work.json")) as f:
            groups = json.load(f)["groups"]
        self.assertEqual(sorted(groups), ["W01", "W02"])
        self.assertEqual(sorted(t for ids in groups.values() for t in ids),
                         ["T%02d" % n for n in range(1, 8)])
        for ids in groups.values():
            self.assertLessEqual(len(ids), 4)
        briefs = sorted(os.listdir(os.path.join(self.work, "briefs")))
        self.assertEqual(briefs, ["W01.md", "W02.md"])

    def test_writers_batch_about_three_tasks_each(self):
        p = self.start("".join(contract(n) for n in range(1, 8)), "--agents", "8")
        self.assertIn("3 writers", p.stdout)  # ceil(7/3)
        with open(os.path.join(self.work, "work.json")) as f:
            info = json.load(f)
        self.assertEqual(sorted(info["groups"]), ["W01", "W02", "W03"])
        self.assertEqual(info["agents"], 8)

    def test_three_tasks_share_one_writer(self):
        p = self.start("".join(contract(n) for n in range(1, 4)), "--agents", "8")
        self.assertIn("1 writers", p.stdout)
        with open(os.path.join(self.work, "work.json")) as f:
            groups = json.load(f)["groups"]
        self.assertEqual(groups, {"W01": ["T01", "T02", "T03"]})

    def test_writers_never_exceed_twelve(self):
        self.start("".join(contract(n) for n in range(1, 41)), "--agents", "64")
        with open(os.path.join(self.work, "work.json")) as f:
            self.assertEqual(len(json.load(f)["groups"]), 12)

    def test_every_tier_uses_the_sonnet_writer_model(self):
        p = self.start(contract(1) + contract(2, extra="- Tier: deep\n")
                       + contract(3, extra="- Tier: light\n"), "--agents", "8")
        rows = {l.split()[0]: l.split()[1] for l in p.stdout.splitlines()
                if l[:1] == "W" and l[1:3].isdigit()}
        self.assertEqual(rows, {"W01": "sonnet"})  # one writer holds the light, std and deep tasks


class ReviewPickingTests(PlanCase):
    def setUp(self):
        super().setUp()
        self.start(contract(1) + contract(2, extra="- Tier: deep\n")
                   + contract(3, files="`src/exists.py`"), "--agents", "8")
        self.finish_bodies([1, 2, 3], files={3: "src/exists.py"})

    def test_review_picks_deep_tier_and_lint_warnings_only(self):
        p = self.tool("review", self.plan)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("REVIEW 2 tasks", p.stdout)
        self.assertIn("T02(tier deep)", p.stdout)
        self.assertIn("T03(lint warnings)", p.stdout)
        self.assertNotIn("T01(", p.stdout)
        self.assertEqual(sorted(os.listdir(os.path.join(self.work, "review-briefs"))),
                         ["R01.md"])  # 2 risky tasks fit one reviewer

    def test_reviewers_batch_about_three_tasks_each(self):
        self.start("".join(contract(n) for n in range(1, 8)), "--agents", "8")
        self.finish_bodies(range(1, 8))
        p = self.tool("review", self.plan, "--all")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(sorted(os.listdir(os.path.join(self.work, "review-briefs"))),
                         ["R01.md", "R02.md", "R03.md"])  # ceil(7/3)

    def test_review_all_picks_every_task(self):
        p = self.tool("review", self.plan, "--all")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("REVIEW 3 tasks", p.stdout)
        for t in ("T01(all", "T02(all", "T03(all"):
            self.assertIn(t, p.stdout)

    def test_review_is_none_when_nothing_is_risky(self):
        self.start(contract(1), "--agents", "8")
        self.finish_bodies([1])
        p = self.tool("review", self.plan)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("NONE", p.stdout)
        self.assertNotIn("REVIEW ", p.stdout)


class AssembleTests(PlanCase):
    def test_missing_bodies_fail_and_leave_the_plan_untouched(self):
        self.start(contract(1) + contract(2), "--agents", "8")
        before = self.read(self.plan)
        p = self.tool("assemble", self.plan)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("T01: task body missing", p.stdout)
        self.assertIn("T02: task body missing", p.stdout)
        self.assertEqual(self.read(self.plan), before)

    def test_assemble_renders_protocol_waves_and_task_headers(self):
        self.start(contract(1) + contract(2)
                   + contract(3, extra="- Depends: T01\n"), "--agents", "8")
        self.finish_bodies([1, 2, 3])
        p = self.tool("assemble", self.plan)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("OK assembled 3 tasks", p.stdout)
        text = self.read(self.plan)
        self.assertIn("## Execution Protocol", text)
        self.assertIn("## Execution Waves", text)
        self.assertIn("### T01: Task 1 [P]", text)
        self.assertIn("### T02: Task 2 [P]", text)
        self.assertIn("### T03: Task 3", text)
        self.assertIn("**Depends:** T01", text)
        self.assertIn("**Wave 1:** T01 [P], T02 [P]", text)
        self.assertIn("**Wave 2:** T03", text)
        self.assertTrue(os.path.isdir(self.work), "workdir is kept without --clean")

    def test_clean_removes_the_workdir(self):
        self.start(contract(1), "--agents", "8")
        self.finish_bodies([1])
        p = self.tool("assemble", self.plan, "--clean")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("workdir removed", p.stdout)
        self.assertFalse(os.path.exists(self.work))
        self.assertIn("### T01: Task 1", self.read(self.plan))


class SetupTests(PlanCase):
    def settings(self):
        return os.path.join(self.home, ".claude", "settings.json")

    def agent(self):
        return os.path.join(self.home, ".claude", "agents", "claude-plan-task-writer.md")

    def test_dry_run_changes_nothing(self):
        p = self.tool("setup")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("DRY-RUN", p.stdout)
        self.assertIn("--apply", p.stdout)
        self.assertFalse(os.path.exists(self.settings()))
        self.assertFalse(os.path.exists(self.agent()))

    def test_apply_writes_settings_and_agent_and_keeps_existing_keys(self):
        with open(self.settings(), "w") as f:
            json.dump({"theme": "dark", "permissions": {"allow": ["Bash(ls)"]}}, f)
        p = self.tool("setup", "--apply")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        cfg = json.loads(self.read(self.settings()))
        self.assertEqual(cfg["theme"], "dark")
        self.assertNotIn("CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS", cfg.get("env", {}))  # unset = default 20, already enough
        allow = cfg["permissions"]["allow"]
        self.assertIn("Bash(ls)", allow)
        self.assertIn("Edit(**/docs/plans/**)", allow)
        self.assertTrue(any(a.startswith("Bash(python3 ") and a.endswith("plan_tool.py *)")
                            for a in allow), allow)
        self.assertTrue(os.path.exists(self.settings() + ".bak"))
        agent = self.read(self.agent())
        self.assertIn("model: sonnet", agent)
        self.assertIn("hook-lint", agent)
        self.assertNotIn("__PLAN_TOOL__", agent)

    def test_apply_keeps_a_cap_of_twelve_or_more_and_raises_a_lower_one(self):
        for old, want in (("40", "40"), ("12", "12"), ("5", "16")):
            with open(self.settings(), "w") as f:
                json.dump({"env": {"CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS": old}}, f)
            self.assertEqual(self.tool("setup", "--apply").returncode, 0)
            cfg = json.loads(self.read(self.settings()))
            self.assertEqual(cfg["env"]["CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS"], want, old)

    def test_second_apply_is_a_no_op(self):
        self.assertEqual(self.tool("setup", "--apply").returncode, 0)
        first = self.read(self.settings())
        p = self.tool("setup", "--apply")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("already complete", p.stdout)
        self.assertEqual(self.read(self.settings()), first)


class SpecCoverageTests(PlanCase):
    def start_with_spec(self, contracts):
        self.write("spec.md", SPEC)
        return self.start(contracts, "--agents", "8", "--spec",
                          os.path.join(self.repo, "spec.md"))

    def test_uncovered_spec_section_is_warned(self):
        p = self.start_with_spec(contract(1, extra="- Spec: L3-5\n") + contract(2))
        self.assertIn("WARN spec uncovered L7-9 ## Beta feature", p.stdout)
        self.assertNotIn("uncovered L3-5", p.stdout)

    def test_fully_covered_spec_has_no_uncovered_warning(self):
        p = self.start_with_spec(contract(1, extra="- Spec: L3-5\n")
                                 + contract(2, extra="- Spec: L7-9\n"))
        self.assertNotIn("spec uncovered", p.stdout)

    def test_task_without_spec_pointer_is_warned(self):
        p = self.start_with_spec(contract(1, extra="- Spec: L3-9\n") + contract(2))
        self.assertIn("WARN T02: no 'Spec: L<a>-<b>' pointer", p.stdout)


if __name__ == "__main__":
    unittest.main()
