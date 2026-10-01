"""hybrid-team guard.py stays a renamed copy of dev-team's guard.py, and lanes cannot drive THIS fork's engine.

The fork adds engine subcommands the original lacks (`lane`, `stats`); every one that is not a lane
helper must be denied to a lane, alone, wrapped, or inside a compound command. Also pins the renames
(state dir, agent name) and the write-capable tools that must never be pre-approved for any role.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
GUARD_PY = SKILL / "scripts" / "guard.py"
DEVTEAM_PY = SKILL / "scripts" / "devteam.py"
LANE_HELPERS = {"claim", "commit-red", "commit-green", "commit-work", "commit-fast"}


def run_guard(mode, payload, cwd):
    return subprocess.run([sys.executable, str(GUARD_PY), mode], input=json.dumps(payload), cwd=cwd,
                          capture_output=True, text=True, timeout=10)


def decision_of(res):
    out = res.stdout.strip()
    if not out:
        return None, None
    hso = json.loads(out).get("hookSpecificOutput") or {}
    return hso.get("permissionDecision"), hso.get("permissionDecisionReason")


def engine_subcommands():
    """The fork's real subcommand list, read from `devteam.py -h` (the `{a,b,...}` usage choice)."""
    r = subprocess.run([sys.executable, str(DEVTEAM_PY), "-h"], capture_output=True, text=True, timeout=30)
    m = re.search(r"\{([a-z0-9,-]+)\}", r.stdout)
    assert m, r.stdout + r.stderr
    return m.group(1).split(",")


class GuardResyncTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = os.path.realpath(self.tmp.name)
        self.wt = Path(self.base) / "wt"
        (self.wt / ".slice").mkdir(parents=True)
        (self.wt / ".slice" / "id").write_text("S1\n")

    def decide(self, mode, cmd):
        r = run_guard(mode, {"tool_name": "Bash", "cwd": str(self.wt), "tool_input": {"command": cmd}},
                      str(self.wt))
        self.assertEqual(r.returncode, 0, r.stderr)
        return decision_of(r)

    # --- the fork's engine surface -----------------------------------------------------------

    def test_fork_subcommands_include_the_hybrid_additions(self):
        subs = set(engine_subcommands())
        self.assertTrue({"lane", "stats", "retry", "doctor", "finish"} <= subs, subs)
        self.assertTrue(LANE_HELPERS <= subs, subs)

    def test_every_non_helper_subcommand_is_denied_to_a_lane(self):
        for sub in engine_subcommands():
            if sub in LANE_HELPERS:
                continue
            for cmd in (f"python3 /x/devteam.py {sub}",
                        f"python3 /x/devteam.py {sub} S1 --files '*'",
                        f"python3 -B /x/devteam.py {sub} --yes",
                        f"timeout 600 python3 /x/devteam.py {sub} S1",
                        f"cd sub && python3 /x/devteam.py {sub} S1",
                        f"echo x ; python3 /x/devteam.py {sub}"):
                with self.subTest(cmd=cmd):
                    decision, reason = self.decide("bash", cmd)
                    self.assertEqual(decision, "deny", msg=cmd)
                    self.assertIn(f"`devteam.py {sub}`", reason or "")

    def test_lane_helpers_are_not_denied_by_the_engine_check(self):
        for sub in sorted(LANE_HELPERS):
            with self.subTest(sub=sub):
                decision, _ = self.decide("bash", f"python3 /x/devteam.py {sub} S1")
                self.assertNotEqual(decision, "deny")

    def test_lane_subcommand_denied_even_when_hidden_behind_a_helper(self):
        for cmd in ("python3 /x/devteam.py claim S1 && python3 /x/devteam.py lane S1",
                    "python3 /x/devteam.py commit-green t; python3 /x/devteam.py retry S1 --files '*'"):
            with self.subTest(cmd=cmd):
                decision, _ = self.decide("bash", cmd)
                self.assertEqual(decision, "deny", msg=cmd)

    # --- renames ------------------------------------------------------------------------------

    def test_no_dev_team_name_left_in_the_fork(self):
        text = GUARD_PY.read_text()
        self.assertNotIn("dev-team", text)
        self.assertIn('STATE_DIRNAME = ".claude/hybrid-team"', text)

    def test_run_state_dir_is_protected_under_the_fork_name_only(self):
        d, _ = self.decide("bash", """python3 -c "open('.claude/hybrid-team/slices/S1.done','w').write('x')" """)
        self.assertEqual(d, "deny")
        d, _ = self.decide("bash", "printf x > .claude/hybrid-team/slices/S1.done")
        self.assertEqual(d, "deny")

    def test_only_the_hybrid_team_leader_may_write_plan_md(self):
        plan = str(Path(self.base) / ".claude" / "hybrid-team" / "plan.md")
        for agent, want in (("hybrid-team-leader", "allow"), ("team-leader", "deny"), ("hybrid-team-programmer", "deny")):
            with self.subTest(agent=agent):
                r = run_guard("edit-ro", {"cwd": self.base, "agent_type": agent,
                                          "tool_input": {"file_path": plan}}, self.base)
                self.assertEqual(decision_of(r)[0], want)

    # --- hardening the fork was missing --------------------------------------------------------

    WRITE_CAPABLE = [
        "git log --output=/tmp/x.log", "git show --output=/tmp/x HEAD", "sed -n 'w /tmp/x' f",
        "sed 's/x/y/e' f", "sort -uo /tmp/x f", "sort --out=/tmp/x f", "git grep -Ovim p",
        "rg --pre=cat p", "sed -ni 's/a/b/' f",
    ]

    def test_write_capable_commands_never_preapproved_for_any_role(self):
        for mode in ("bash", "bash-ro"):
            for cmd in self.WRITE_CAPABLE:
                with self.subTest(mode=mode, cmd=cmd):
                    self.assertNotEqual(self.decide(mode, cmd)[0], "allow", msg=cmd)

    def test_symlink_into_tests_cannot_bypass_frozen_tests(self):
        sd = self.wt / ".slice"
        (sd / "footprint").write_text("src/\n")
        (sd / "kind").write_text("refactor\n")
        (self.wt / "tests").mkdir()
        (self.wt / "tests" / "test_a.py").write_text("x\n")
        (self.wt / "src").mkdir()
        os.symlink(self.wt / "tests" / "test_a.py", self.wt / "src" / "link.py")
        r = run_guard("edit", {"cwd": str(self.wt), "tool_input": {"file_path": str(self.wt / "src" / "link.py")}},
                      str(self.wt))
        self.assertEqual(decision_of(r)[0], "deny", r.stdout)

    def test_dot_env_is_not_env(self):
        (self.wt / ".slice" / "footprint").write_text("env\n")
        r = run_guard("edit", {"cwd": str(self.wt), "tool_input": {"file_path": str(self.wt / ".env")}}, str(self.wt))
        self.assertEqual(decision_of(r)[0], "deny", r.stdout)


if __name__ == "__main__":
    unittest.main()
