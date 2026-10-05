"""Black-box tests for plan_tool.py task hashing and writer dispatch skipping (T14).

Runs the real script against throwaway git repos under the system temp dir.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(TESTS_DIR), "claude-writing-plans-6.2", "scripts", "plan_tool.py")
FENCE = "`" * 3
HEADING = "#" * 4


def make_plan(sig_a):
    def contract(tid, name, path, sig, depends=None):
        lines = ["%s %s: %s" % (HEADING, tid, name)]
        if depends:
            lines.append("- Depends: %s" % depends)
        lines += ["- Files: `%s`" % path, "- Produces: `%s`" % sig, ""]
        return "\n".join(lines)

    return "\n".join([
        "# Demo Plan", "", "## Contracts", "",
        contract("T01", "First", "src/a.py", sig_a),
        contract("T02", "Second", "src/b.py", "def b() -> None", depends="T01"),
        contract("T03", "Third", "src/c.py", "def c() -> None"),
        contract("T04", "Fourth", "src/d.py", "def d() -> None"),
        contract("T05", "Fifth", "src/e.py", "def e() -> None"),
        contract("T06", "Sixth", "src/f.py", "def f() -> None"),
    ])


def make_body(path, sig):
    return (
        "**Files:**\n- Create: `%s`\n\n"
        "- [ ] **Step 1: implement**\n\n"
        "%spython\n%s:\n    pass\n%s\n\n"
        "Then `git commit -m \"feat\"`.\n"
    ) % (path, FENCE, sig, FENCE)


class PlanHashingTests(unittest.TestCase):
    def setUp(self):
        self.home = os.path.realpath(tempfile.mkdtemp())
        self.repo = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.home, ignore_errors=True)
        self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)
        subprocess.run(["git", "init", "-q"], cwd=self.repo, check=True)
        self.plan = os.path.join(self.repo, "plan.md")
        self.tasks = os.path.join(self.repo, ".work", "plan", "tasks")
        self.write_plan("def a() -> None")
        self.first = self.contracts()
        self.assertEqual(self.first.returncode, 0, self.first.stdout + self.first.stderr)

    def tool(self, *args):
        env = dict(os.environ, HOME=self.home, PYTHONDONTWRITEBYTECODE="1")
        return subprocess.run([sys.executable, TOOL] + list(args), cwd=self.repo, env=env,
                              capture_output=True, text=True, timeout=30)

    def write_plan(self, sig_a):
        with open(self.plan, "w") as f:
            f.write(make_plan(sig_a))

    def contracts(self):
        return self.tool("contracts", self.plan, "--agents", "8")

    def finish(self, tid, path, sig):
        task = os.path.join(self.tasks, tid + ".md")
        with open(task, "w") as f:
            f.write(make_body(path, sig))
        p = self.tool("lint-task", self.plan, task)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertTrue(os.path.exists(task + ".ok"))

    def finish_all(self):
        self.finish("T01", "src/a.py", "def a() -> None")
        self.finish("T02", "src/b.py", "def b() -> None")
        self.finish("T03", "src/c.py", "def c() -> None")
        self.finish("T04", "src/d.py", "def d() -> None")
        self.finish("T05", "src/e.py", "def e() -> None")
        self.finish("T06", "src/f.py", "def f() -> None")

    def brief(self, tid):
        return os.path.join("briefs", tid + ".md")

    def test_changed_producer_drops_dependent_body_and_mark(self):
        self.finish_all()
        self.write_plan("def a(x: int) -> None")
        p = self.contracts()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        for tid in ("T01", "T02"):
            path = os.path.join(self.tasks, tid + ".md")
            self.assertFalse(os.path.exists(path), "%s body should be dropped" % tid)
            self.assertFalse(os.path.exists(path + ".ok"), "%s mark should be dropped" % tid)
        keep = os.path.join(self.tasks, "T03.md")
        self.assertTrue(os.path.exists(keep), "unrelated task body should be kept")
        self.assertTrue(os.path.exists(keep + ".ok"), "unrelated task mark should be kept")

    def test_rerun_skips_groups_with_a_fresh_ok_mark(self):
        for gid in ("W01", "W02"):  # 6 tasks -> ceil(6/3) = 2 writers of 3
            self.assertIn(self.brief(gid), self.first.stdout)
        for tid, path, sig in (("T01", "a", "a"), ("T02", "b", "b"), ("T03", "c", "c")):
            self.finish(tid, "src/%s.py" % path, "def %s() -> None" % sig)
        p = self.contracts()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertNotIn(self.brief("W01"), p.stdout)
        self.assertIn(self.brief("W02"), p.stdout)
        self.assertIn("DISPATCH 1 writers", p.stdout)
        for tid, path, sig in (("T04", "d", "d"), ("T05", "e", "e"), ("T06", "f", "f")):
            self.finish(tid, "src/%s.py" % path, "def %s() -> None" % sig)
        p = self.contracts()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("NOTHING TO DISPATCH", p.stdout)
        self.assertNotIn("briefs", p.stdout)


if __name__ == "__main__":
    unittest.main()
