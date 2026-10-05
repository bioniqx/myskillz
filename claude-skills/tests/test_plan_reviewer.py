"""Black-box tests for the review command and tier mapping of plan_tool.py (T16).

Runs the real script against throwaway git repos under the system temp dir.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(TESTS_DIR)  # claude-skills/
TOOL = os.path.join(BASE_DIR, "claude-writing-plans-6.2", "scripts", "plan_tool.py")

PLAN_ONE = "# P\n\n## Contracts\n\n#### T01: Only\n- Files: `src/a.py`\n- Produces: `def a() -> None`\n"
MARKER = "BODY_MARKER_QRS"
FENCE = "`" * 3
BODY_ONE = (
    "**Files:**\n- Modify: `src/a.py`\n\n"
    "- [ ] **Step 1: implement**\n\n"
    + FENCE + "python\ndef a() -> None:\n    return None  # " + MARKER + "\n" + FENCE + "\n\n"
    "Then `git commit -m \"feat\"`.\n"
)


def run_tool(args, cwd, env=None, timeout=25):
    e = dict(os.environ)
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    if env:
        e.update(env)
    return subprocess.run([sys.executable, TOOL] + list(args), cwd=cwd, env=e,
                          capture_output=True, text=True, timeout=timeout)


def make_repo(files):
    d = os.path.realpath(tempfile.mkdtemp())
    for cmd in (["git", "init", "-q"], ["git", "config", "user.email", "t@example.com"],
                ["git", "config", "user.name", "T"], ["git", "config", "commit.gpgsign", "false"]):
        subprocess.run(cmd, cwd=d, check=True)
    for rel, content in files.items():
        p = os.path.join(d, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write(content)
    subprocess.run(["git", "add", "-A"], cwd=d, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=d, check=True)
    return d


def fake_home(agent=False):
    h = os.path.realpath(tempfile.mkdtemp())
    agents = os.path.join(h, ".claude", "agents")
    os.makedirs(agents)
    if agent:
        with open(os.path.join(agents, "claude-plan-task-writer.md"), "w") as f:
            f.write("writer agent\n")
    return h


def prepare(repo, home, plan_text, bodies):
    """Write the plan, run contracts, drop the given task bodies into the work dir."""
    plan = os.path.join(repo, "plan.md")
    with open(plan, "w") as f:
        f.write(plan_text)
    env = {"HOME": home}
    p = run_tool(["contracts", plan], cwd=repo, env=env)
    if p.returncode != 0:
        raise RuntimeError(p.stdout + p.stderr)
    tasks = os.path.join(repo, ".work", "plan", "tasks")
    for tid, body in bodies.items():
        with open(os.path.join(tasks, tid + ".md"), "w") as f:
            f.write(body)
    return plan, env


def read_briefs(repo):
    d = os.path.join(repo, ".work", "plan", "review-briefs")
    out = ""
    for name in sorted(os.listdir(d)):
        with open(os.path.join(d, name)) as f:
            out += f.read()
    return out


class ReviewerBriefBodyTests(unittest.TestCase):
    def test_brief_inlines_the_task_body(self):
        home = fake_home()
        self.addCleanup(shutil.rmtree, home, ignore_errors=True)
        repo = make_repo({"src/a.py": ""})
        self.addCleanup(shutil.rmtree, repo, ignore_errors=True)
        plan, env = prepare(repo, home, PLAN_ONE, {"T01": BODY_ONE})
        p = run_tool(["review", plan, "--all"], cwd=repo, env=env)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        content = read_briefs(repo)
        self.assertIn("## Task body T01", content)
        self.assertIn(MARKER, content)


PLAN_TIERS = (
    "# P\n\n## Contracts\n\n"
    "#### T01: Light\n- Files: `src/a.py`\n- Tier: light\n\n"
    "#### T02: Standard\n- Files: `src/b.py`\n\n"
    "#### T03: Deep\n- Files: `src/c.py`\n- Tier: deep\n"
)


class TierMappingTests(unittest.TestCase):
    def test_every_tier_dispatches_to_sonnet(self):
        home = fake_home()
        self.addCleanup(shutil.rmtree, home, ignore_errors=True)
        repo = make_repo({"src/a.py": "", "src/b.py": "", "src/c.py": ""})
        self.addCleanup(shutil.rmtree, repo, ignore_errors=True)
        plan = os.path.join(repo, "plan.md")
        with open(plan, "w") as f:
            f.write(PLAN_TIERS)
        p = run_tool(["contracts", plan], cwd=repo, env={"HOME": home})
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        rows = [l.split() for l in p.stdout.splitlines() if re.match(r"^W\d\d\s", l)]
        self.assertEqual([(r[0], r[2]) for r in rows], [("W01", "T01-T03")])
        self.assertEqual({r[1] for r in rows}, {"sonnet"})


class ReviewDispatchAgentTests(unittest.TestCase):
    def _dispatch_line(self, with_agent):
        home = fake_home(agent=with_agent)
        self.addCleanup(shutil.rmtree, home, ignore_errors=True)
        repo = make_repo({"src/a.py": ""})
        self.addCleanup(shutil.rmtree, repo, ignore_errors=True)
        plan, env = prepare(repo, home, PLAN_ONE, {"T01": BODY_ONE})
        p = run_tool(["review", plan, "--all"], cwd=repo, env=env)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        return next(l for l in p.stdout.splitlines() if l.startswith("DISPATCH"))

    def test_uses_the_writer_agent_when_installed(self):
        line = self._dispatch_line(with_agent=True)
        self.assertIn("subagent_type=claude-plan-task-writer", line)
        self.assertIn("model sonnet", line)

    def test_falls_back_to_general_purpose(self):
        line = self._dispatch_line(with_agent=False)
        self.assertIn("subagent_type=general-purpose", line)
        self.assertIn("model sonnet", line)


if __name__ == "__main__":
    unittest.main()
