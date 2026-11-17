"""FAST chain fold in plan_tool check: a passing check advances the chain itself.

chain.json mode fast + continue true makes cmd_check print the HANDOFF
glm-dev-team block with the devteam.py start command; without the chain, with
a chain that does not continue, or under a slow mode stamp, the check output
is unchanged. No model calls."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLAN_TOOL = os.path.join(HERE, "..", "..", "glm-writing-plans", "scripts", "plan_tool.py")
FENCE = "`" * 3
FILES = ["src/a.py", "tests/test_a.py"]

SPEC_TEXT = "\n".join([
    "# Settings loader",
    "",
    "## Background",
    "Context for the loader design.",
    "",
    "## Behavior",
    'The loader "must ship" a dict and "must log" every key.',
    "Return value is plain and lock-free.",
    "",
])
_BEHAVIOR = SPEC_TEXT.splitlines().index("## Behavior") + 1
RANGE = "L%d-L%d" % (_BEHAVIOR + 1, _BEHAVIOR + 2)

CHAIN_FAST = {
    "continue": True,
    "source": "fast",
    "pick": "A",
    "mode": "fast",
    "next": ["spec", "glm-writing-plans", "glm-dev-team"],
}


def plan_text():
    return "\n".join([
        "# Plan",
        "",
        "**Out of scope:** the `telemetry` sender",
        "",
        "## Contracts",
        "",
        "#### T01: settings",
        "- Files: `%s`, `%s`" % (FILES[0], FILES[1]),
        "- Produces: `load_settings()`",
        "- Spec: %s" % RANGE,
        "- Tier: light",
        "",
        "<!-- TASKS -->",
        "",
    ])


def task_body():
    """A T01 body that lints clean without a slow stamp."""
    rows = ["**Files:**"] + ["- Create: `%s`" % f for f in FILES]
    rows += ["", "- [ ] **Step 1: Write the code**", "", FENCE + "python",
             "value = load_settings()", FENCE, "",
             "**Run:** python3 -m unittest tests.test_a", "",
             "**Expected:** `load_settings()` returns the dict", "",
             "- [ ] **Step 2: Commit**", "", FENCE + "bash",
             "git add " + " ".join(FILES),
             'git commit -m "feat: settings"', FENCE, ""]
    return "\n".join(rows)


class CheckFastChain(unittest.TestCase):
    def repo(self, chain=None, slow=False):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, True)
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        with open(os.path.join(root, "spec.md"), "w", encoding="utf-8") as fh:
            fh.write(SPEC_TEXT)
        self.plan = os.path.join(root, "plan.md")
        with open(self.plan, "w", encoding="utf-8") as fh:
            fh.write(plan_text() + "### T01: settings\n\n" + task_body() + "\n")
        if chain is not None:
            path = os.path.join(root, ".brainstorm", "drafts", "chain.json")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(chain, fh)
        if slow:
            path = os.path.join(root, ".claude", "dev-team", "mode")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("slow 123\n")
        return root

    def check(self, root):
        proc = subprocess.run(
            [sys.executable, PLAN_TOOL, "check", self.plan, "--spec",
             os.path.join(root, "spec.md")],
            capture_output=True, text=True, timeout=120, cwd=root)
        return proc.returncode, proc.stdout

    def test_fast_chain_prints_the_devteam_handoff_after_the_ok_line(self):
        root = self.repo(chain=dict(CHAIN_FAST))
        rc, out = self.check(root)
        self.assertEqual(rc, 0, out)
        self.assertIn("OK plan:", out)
        self.assertIn("HANDOFF glm-dev-team", out)
        self.assertIn("devteam.py start %s" % self.plan, out)
        self.assertIn("NEXT-EXTRA: FAST chain: skip glm-dev-team's open.", out)
        self.assertIn("RESULT next action=handoff name=glm-dev-team", out)
        self.assertLess(out.index("OK plan:"), out.index("HANDOFF glm-dev-team"))

    def test_brainstorming_in_the_chain_next_list_leads_the_seen_line(self):
        chain = dict(CHAIN_FAST, next=["glm-brainstorming", "glm-writing-plans",
                                        "glm-dev-team"])
        root = self.repo(chain=chain)
        rc, out = self.check(root)
        self.assertEqual(rc, 0, out)
        self.assertIn("FROM-LINE: From: glm-brainstorming,glm-writing-plans,glm-dev-team", out)

    def test_no_chain_file_keeps_the_output_unchanged(self):
        root = self.repo()
        rc, out = self.check(root)
        self.assertEqual(rc, 0, out)
        self.assertIn("OK plan:", out)
        self.assertNotIn("HANDOFF", out)
        self.assertNotIn("NEXT-EXTRA", out)

    def test_a_chain_that_is_not_fast_and_continuing_does_not_hand_off(self):
        for chain in (dict(CHAIN_FAST, mode="slow"),
                      dict(CHAIN_FAST, **{"continue": False})):
            root = self.repo(chain=chain)
            rc, out = self.check(root)
            self.assertEqual(rc, 0, out)
            self.assertNotIn("HANDOFF", out)

    def test_a_slow_stamp_wins_over_the_fast_chain(self):
        root = self.repo(chain=dict(CHAIN_FAST), slow=True)
        rc, out = self.check(root)
        self.assertEqual(rc, 1, out)
        self.assertIn("mode stamp is slow", out)
        self.assertNotIn("OK plan:", out)
        self.assertNotIn("HANDOFF", out)


if __name__ == "__main__":
    unittest.main()
