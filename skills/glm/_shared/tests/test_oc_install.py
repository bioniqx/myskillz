import argparse
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import oc_harness

AGENT = (
    "---\n"
    "description: test agent\n"
    "model: flash\n"
    "effort: high\n"
    "access: read\n"
    "bash: false\n"
    "web: false\n"
    "steps: 5\n"
    "---\n"
    "Do the work.\n"
)
COMMAND = "---\ndescription: run debug\n---\n!`python3 {{SKILL_DIR}}/scripts/tool.py doctor`\nLoad the skill with $ARGUMENTS\n"


def make_skill(root, folder="systematic-debugging-glm", name="systematic-debugging"):
    skill = os.path.join(root, folder)
    os.makedirs(os.path.join(skill, "opencode", "agents"))
    os.makedirs(os.path.join(skill, "opencode", "commands"))
    os.makedirs(os.path.join(skill, "scripts", "__pycache__"))
    with open(os.path.join(skill, "SKILL.md"), "w") as fh:
        fh.write("---\nname: %s\ndescription: test skill\n---\nbody\n" % name)
    with open(os.path.join(skill, "opencode", "agents", "worker.md"), "w") as fh:
        fh.write(AGENT)
    with open(os.path.join(skill, "opencode", "commands", "debug.md"), "w") as fh:
        fh.write(COMMAND)
    with open(os.path.join(skill, "scripts", "__pycache__", "x.pyc"), "w") as fh:
        fh.write("junk")
    return skill


class Patch:
    """Swap module attributes for one test and restore them afterwards."""

    def __init__(self, test, **attrs):
        for key, value in attrs.items():
            original = getattr(oc_harness, key)
            test.addCleanup(setattr, oc_harness, key, original)
            setattr(oc_harness, key, value)


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="oc-install-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.skill = make_skill(self.tmp)
        self.home = os.path.join(self.tmp, "home")
        self.root = os.path.join(self.home, ".config", "opencode")

    def test_skill_name_strips_glm_suffix(self):
        other = make_skill(self.tmp, "writing-plans-glm", "writing-plans-glm")
        self.assertEqual(oc_harness.skill_name(other), "writing-plans")
        self.assertEqual(oc_harness.skill_name(self.skill), "systematic-debugging")

    def test_install_uses_frontmatter_name_and_writes_marker(self):
        written = oc_harness.install(self.skill, 1, self.home)
        dst = os.path.join(self.root, "skills", "systematic-debugging")
        self.assertIn(dst, written)
        self.assertTrue(os.path.isfile(os.path.join(dst, "SKILL.md")))
        self.assertFalse(os.path.exists(os.path.join(dst, "scripts", "__pycache__")))
        with open(os.path.join(dst, ".oc-major")) as fh:
            self.assertEqual(fh.read().strip(), "1")

    def test_install_renders_agents_and_commands_under_their_own_names(self):
        oc_harness.install(self.skill, 2, self.home)
        agent = os.path.join(self.root, "agents", "worker.md")
        command = os.path.join(self.root, "commands", "debug.md")
        with open(agent) as fh:
            text = fh.read()
        self.assertIn("mode: subagent", text)
        self.assertIn("reasoning_effort: high", text)
        with open(command) as fh:
            text = fh.read()
        dst = os.path.join(self.root, "skills", "systematic-debugging")
        self.assertIn("python3 %s/scripts/tool.py doctor" % dst, text)
        self.assertNotIn("{{SKILL_DIR}}", text)

    def test_install_rejects_unknown_major(self):
        with self.assertRaises(ValueError):
            oc_harness.install(self.skill, 0, self.home)


class CheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="oc-check-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.skill = make_skill(self.tmp)
        self.home = os.path.join(self.tmp, "home")
        real = os.path.expanduser
        self.addCleanup(setattr, os.path, "expanduser", real)
        os.path.expanduser = lambda path: path.replace("~", self.home, 1)

    def test_missing_install(self):
        self.assertEqual(oc_harness.check(self.skill), ["MISSING: systematic-debugging is not installed for OpenCode"])

    def test_major_mismatch_and_missing_flags(self):
        oc_harness.install(self.skill, 1, self.home)
        Patch(self, detect=lambda binary="opencode": 2,
              check_run_flags=lambda major, binary="opencode": ["--dir"])
        lines = oc_harness.check(self.skill)
        self.assertEqual(lines[0], "INSTALLED: systematic-debugging (major 1)")
        self.assertIn("FAIL: installed major 1 != detected major 2, re-run install-opencode.sh", lines)
        self.assertIn("FAIL: opencode run lacks --dir", lines)

    def test_binary_missing(self):
        oc_harness.install(self.skill, 1, self.home)
        Patch(self, detect=lambda binary="opencode": 0)
        self.assertIn("FAIL: opencode binary not found", oc_harness.check(self.skill))


class ProbeEffortTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="oc-probe-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.home = os.path.join(self.tmp, "home")
        self.seen_agents = []
        Patch(self, detect=lambda binary="opencode": 1)

    def fake_run_lanes(self, low, high, status="OK"):
        def run(lanes, out_dir, width=8, stall=180, binary="opencode", major=0):
            rows = []
            for lane, reasoning in zip(lanes, (low, high)):
                agent_file = os.path.join(self.home, ".config", "opencode", "agents", lane["agent"] + ".md")
                self.seen_agents.append(os.path.isfile(agent_file))
                out = os.path.join(out_dir, lane["id"] + ".jsonl")
                with open(out, "w") as fh:
                    fh.write(json.dumps({"type": "text", "part": {"text": "25"}}) + "\n")
                    fh.write(json.dumps({"type": "step_finish", "part": {"tokens": {"reasoning": reasoning}}}) + "\n")
                rows.append({"id": lane["id"], "status": status, "out": out})
            return rows
        return run

    def test_honored_when_max_thinks_much_longer(self):
        Patch(self, run_lanes=self.fake_run_lanes(40, 400))
        self.assertEqual(oc_harness.probe_effort("opencode", self.home), "honored")
        self.assertEqual(self.seen_agents, [True, True])
        agents = os.path.join(self.home, ".config", "opencode", "agents")
        self.assertEqual(os.listdir(agents), [])

    def test_ignored_when_counts_are_close(self):
        Patch(self, run_lanes=self.fake_run_lanes(300, 320))
        self.assertEqual(oc_harness.probe_effort("opencode", self.home), "ignored")

    def test_unknown_without_usage_or_on_failure(self):
        Patch(self, run_lanes=self.fake_run_lanes(0, 0))
        self.assertEqual(oc_harness.probe_effort("opencode", self.home), "unknown")
        Patch(self, run_lanes=self.fake_run_lanes(40, 400, status="FAIL"))
        self.assertEqual(oc_harness.probe_effort("opencode", self.home), "unknown")


class MainTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="oc-main-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.skill = make_skill(self.tmp)
        self.home = os.path.join(self.tmp, "home")

    def run_main(self, argv):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = oc_harness.main(argv)
        return rc, buf.getvalue()

    def test_install_positional_major_and_home(self):
        rc, out = self.run_main(["install", self.skill, "1", self.home])
        self.assertEqual(rc, 0)
        self.assertIn(os.path.join(self.home, ".config", "opencode", "skills", "systematic-debugging"), out)
        self.assertIn("NEXT:", out)

    def test_install_without_opencode_fails(self):
        Patch(self, detect=lambda binary="opencode": 0)
        rc, out = self.run_main(["install", self.skill])
        self.assertEqual(rc, 1)
        self.assertIn("opencode not found", out)

    def test_run_prints_lane_rows_and_exit_code(self):
        lanes = os.path.join(self.tmp, "lanes.json")
        with open(lanes, "w") as fh:
            json.dump([{"id": "a", "agent": "worker", "model": "flash", "dir": ".", "brief": "hi"}], fh)
        rows = [{"id": "a", "status": "OK", "exit": 0, "error": "", "out": "a.jsonl"}]
        Patch(self, run_lanes=lambda lanes, out_dir, width=8, stall=180, binary="opencode", major=0: rows)
        rc, out = self.run_main(["run", lanes, "--out", os.path.join(self.tmp, "out")])
        self.assertEqual(rc, 0)
        self.assertIn("LANE a OK exit=0", out)
        self.assertIn("NEXT:", out)
        rows[0]["status"] = "FAIL"
        rc, _ = self.run_main(["run", lanes, "--out", os.path.join(self.tmp, "out")])
        self.assertEqual(rc, 1)

    def test_detect_returns_one_when_missing(self):
        Patch(self, detect=lambda binary="opencode": 0)
        rc, out = self.run_main(["detect"])
        self.assertEqual(rc, 1)
        self.assertIn("0", out)

    def test_detect_prints_major_and_returns_zero(self):
        Patch(self, detect=lambda binary="opencode": 2)
        rc, out = self.run_main(["detect"])
        self.assertEqual(rc, 0)
        self.assertIn("2", out)

    def test_check_returns_one_on_fail_line(self):
        Patch(self, check=lambda skill_dir: ["MISSING: foo is not installed for OpenCode"])
        rc, out = self.run_main(["check", self.skill])
        self.assertEqual(rc, 1)
        self.assertIn("MISSING: foo is not installed for OpenCode", out)

    def test_check_returns_one_on_fail_line_after_installed_line(self):
        Patch(self, check=lambda skill_dir: [
            "INSTALLED: x (major 1)",
            "FAIL: opencode run lacks --agent",
        ])
        rc, out = self.run_main(["check", self.skill])
        self.assertEqual(rc, 1)
        self.assertIn("INSTALLED: x (major 1)", out)
        self.assertIn("FAIL: opencode run lacks --agent", out)

    def test_check_returns_zero_for_clean_install(self):
        Patch(self, check=lambda skill_dir: ["INSTALLED: systematic-debugging (major 1)"])
        rc, out = self.run_main(["check", self.skill])
        self.assertEqual(rc, 0)
        self.assertIn("INSTALLED: systematic-debugging (major 1)", out)

    def test_snippet_prints_provider_and_returns_zero(self):
        rc, out = self.run_main(["snippet", "1"])
        self.assertEqual(rc, 0)
        self.assertIn("zai-coding-plan", out)

    def test_probe_effort_prints_effort_line_and_returns_zero(self):
        Patch(self, probe_effort=lambda binary="opencode", home="": "honored")
        rc, out = self.run_main(["probe-effort"])
        self.assertEqual(rc, 0)
        self.assertIn("EFFORT honored", out)

    def test_unknown_command_returns_two(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            sys_stderr = sys.stderr
            sys.stderr = io.StringIO()
            try:
                rc = oc_harness.main(["bogus"])
            finally:
                sys.stderr = sys_stderr
        self.assertEqual(rc, 2)


class ConfigSnippetV2Tests(unittest.TestCase):
    """Evidence (opencode v2.0.16 binary, `strings` on
    /opt/homebrew/Cellar/opencode-v2/2.0.16/bin/opencode):

    The static opencode.json / agent-frontmatter "permission" field is
    defined as `permission:n(ef)` in BOTH the top-level `identifier:"Config"`
    schema and the per-agent `identifier:"AgentConfig"` schema, where
    `ef=fI.pipe(...).annotate({identifier:"PermissionConfig"})` and
    `Pr=P([mo,uI]).annotate({identifier:"PermissionRuleConfig"})`,
    `mo=K(["ask","allow","deny"]).annotate({identifier:"PermissionActionConfig"})`,
    `uI=L(t,mo).annotate({identifier:"PermissionObjectConfig"})` — i.e. a
    record mapping a pattern (e.g. a skill name) to "ask"/"allow"/"deny",
    exactly the nested-map shape already emitted:
    {"permission": {"skill": {"<name>": "deny"}}}.

    The {action, resource, effect} rule-list shape does exist in the binary
    (`wj=r({action:t,resource:t,effect:PB}).annotate({identifier:"Permission.Rule"})`,
    `Np=x(wj).annotate({identifier:"Permission.Ruleset"})`) but it backs the
    *runtime* permission ask/reply protocol
    (`identifier:"Permission.Request"` carries sessionID/action/resources/
    source/message — a live approval event), not the static config file.
    So config_snippet(2) keeping the nested-map shape is correct; no shape
    change was needed.
    """

    def test_config_snippet_v2_emits_nested_map_permission_shape(self):
        snippet = oc_harness.config_snippet(2, ["systematic-debugging", "writing-plans"])
        data = json.loads(snippet)
        self.assertEqual(data["permission"]["skill"], {
            "systematic-debugging": "deny",
            "writing-plans": "deny",
        })
        self.assertNotIn("action", snippet)
        self.assertNotIn("resource", snippet)
        self.assertNotIn("effect", snippet)

    def test_config_snippet_v2_omits_permission_when_no_deny_list(self):
        self.assertNotIn("permission", json.loads(oc_harness.config_snippet(2, [])))

    def test_config_snippet_v1_output_unchanged(self):
        snippet = oc_harness.config_snippet(1, ["systematic-debugging", "writing-plans"])
        data = json.loads(snippet)
        self.assertEqual(data["permission"]["skill"], {
            "systematic-debugging": "deny",
            "writing-plans": "deny",
        })
        self.assertEqual(
            oc_harness.config_snippet(1, ["x"]),
            oc_harness.config_snippet(2, ["x"]),
        )


class InstallFromOwnDestinationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="oc-selfinstall-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.home = os.path.join(self.tmp, "home")
        skills_root = os.path.join(self.home, ".config", "opencode", "skills")
        os.makedirs(skills_root)
        self.skill_dst = make_skill(skills_root, "systematic-debugging", "systematic-debugging")

    def test_install_from_its_own_destination_does_not_delete_it(self):
        written = oc_harness.install(self.skill_dst, 1, self.home)
        self.assertIn(self.skill_dst, written)
        self.assertTrue(os.path.isfile(os.path.join(self.skill_dst, "SKILL.md")))
        self.assertTrue(os.path.isdir(os.path.join(self.skill_dst, "scripts")))
        with open(os.path.join(self.skill_dst, ".oc-major")) as fh:
            self.assertEqual(fh.read().strip(), "1")
        agent = os.path.join(self.home, ".config", "opencode", "agents", "worker.md")
        self.assertTrue(os.path.isfile(agent))


class AuditSetupFromInstalledCopyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="oc-audit-selfinstall-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.home = os.path.join(self.tmp, "home")
        src = os.path.normpath(os.path.join(
            os.path.dirname(__file__), "..", "..", "requirements-code-audit-glm"))
        self.installed = os.path.join(
            self.home, ".config", "opencode", "skills", "requirements-code-audit")
        os.makedirs(os.path.dirname(self.installed))
        shutil.copytree(src, self.installed, ignore=shutil.ignore_patterns("__pycache__"))

    def test_setup_run_from_installed_copy_leaves_it_in_place(self):
        audit_path = os.path.join(self.installed, "scripts", "audit.py")
        spec = importlib.util.spec_from_file_location("audit_installed_f22", audit_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        args = argparse.Namespace(harness="opencode", dry_run=False)
        buf = io.StringIO()
        with mock.patch.dict(os.environ, {"HOME": self.home}, clear=False), \
                mock.patch.object(oc_harness, "detect", return_value=2):
            with redirect_stdout(buf):
                rc = mod.cmd_setup(args)
        self.assertEqual(rc or 0, 0, buf.getvalue())
        self.assertTrue(os.path.isdir(self.installed), buf.getvalue())
        self.assertTrue(os.path.isfile(os.path.join(self.installed, "SKILL.md")))


if __name__ == "__main__":
    unittest.main()
