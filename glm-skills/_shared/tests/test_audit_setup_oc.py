import argparse
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.normpath(os.path.join(HERE, "..", "..", "glm-requirements-code-audit", "scripts"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import audit  # noqa: E402
import oc_harness  # noqa: E402

SETUP_MD = os.path.normpath(os.path.join(HERE, "..", "..", "glm-requirements-code-audit", "SETUP.md"))


class IsolatedHome(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.home, ignore_errors=True)

    def run_setup(self, dry_run=False):
        args = argparse.Namespace(harness="opencode", dry_run=dry_run)
        buf = io.StringIO()
        with mock.patch.dict(os.environ, {"HOME": self.home}, clear=False):
            with redirect_stdout(buf):
                rc = audit.cmd_setup(args)
        return rc, buf.getvalue()


class OpenCodeAgentInstall(IsolatedHome):
    def test_writes_rendered_agent_files_with_real_dialect(self):
        with mock.patch.object(oc_harness, "detect", return_value=2):
            rc, out = self.run_setup()
        self.assertEqual(rc or 0, 0)
        inv = os.path.join(self.home, ".config", "opencode", "agents", "glm-rca-investigator.md")
        ver = os.path.join(self.home, ".config", "opencode", "agents", "glm-rca-verifier.md")
        self.assertTrue(os.path.isfile(inv), out)
        self.assertTrue(os.path.isfile(ver), out)
        with open(inv) as fh:
            inv_text = fh.read()
        with open(ver) as fh:
            ver_text = fh.read()
        self.assertIn("mode: subagent", inv_text)
        self.assertIn("model: zai-coding-plan/glm-5.3-flash", inv_text)
        self.assertIn("mode: subagent", ver_text)
        # anchored: "glm-5.3" alone must not also match "glm-5.3-flash"
        self.assertRegex(ver_text, r"(?m)^model: zai-coding-plan/glm-5\.3$")

    def test_prints_installed_paths_from_install(self):
        with mock.patch.object(oc_harness, "detect", return_value=2), \
             mock.patch.object(oc_harness, "install", return_value=["/x/a.md", "/x/b.md"]):
            rc, out = self.run_setup()
        self.assertEqual(rc or 0, 0)
        self.assertIn("  installed /x/a.md", out)
        self.assertIn("  installed /x/b.md", out)

    def test_prints_nothing_installed_when_install_returns_empty(self):
        with mock.patch.object(oc_harness, "detect", return_value=2), \
             mock.patch.object(oc_harness, "install", return_value=[]):
            rc, out = self.run_setup()
        self.assertEqual(rc or 0, 0)
        self.assertNotIn("  installed ", out)

    def test_returns_1_when_opencode_not_found(self):
        with mock.patch.object(oc_harness, "detect", return_value=0):
            rc, out = self.run_setup()
        self.assertEqual(rc, 1)
        self.assertIn("opencode not found", out)


class SetupDocInstructions(unittest.TestCase):
    def test_opencode_section_points_at_the_install_command_not_hand_copy(self):
        with open(SETUP_MD) as fh:
            text = fh.read()
        self.assertTrue(
            "oc_harness.py install" in text or "audit.py setup" in text,
            "SETUP.md should name the install command for OpenCode")
        self.assertNotIn("from `opencode/agents/`", text,
                          "SETUP.md should not tell users to hand-copy the neutral opencode/agents/*.md sources")


class AgentLaneDispatchLine(unittest.TestCase):
    def test_opencode_v2_uses_shared_dispatch_line(self):
        with mock.patch.object(oc_harness, "harness", return_value="opencode"), \
             mock.patch.object(oc_harness, "major", return_value=2):
            line = audit._dispatch("glm-rca-investigator", "/a/batch-01.md", "rca batch-01")
        want = oc_harness.dispatch_line("glm-rca-investigator", "/a/batch-01.md", "rca batch-01", 2,
                                        background=True)
        self.assertEqual(line, want)
        self.assertNotIn("haiku", line)
        self.assertNotIn("sonnet", line)

    def test_unknown_major_falls_back_to_v1_dialect(self):
        with mock.patch.object(oc_harness, "harness", return_value="opencode"), \
             mock.patch.object(oc_harness, "major", return_value=0):
            line = audit._dispatch("glm-rca-verifier", "/a/b.md", "rca b")
        want = oc_harness.dispatch_line("glm-rca-verifier", "/a/b.md", "rca b", 1, background=True)
        self.assertEqual(line, want)

    def test_non_opencode_line_names_no_model_alias(self):
        with mock.patch.object(oc_harness, "harness", return_value="zcode"):
            line = audit._dispatch("glm-rca-investigator", "/a/b.md", "rca b")
        self.assertEqual(line, "subagent_type=glm-rca-investigator  prompt: read /a/b.md and follow it exactly")

    def test_source_no_longer_prints_model_alias_dispatch(self):
        with open(os.path.join(SCRIPTS, "audit.py")) as fh:
            src = fh.read()
        self.assertNotIn("model=%s  prompt", src)


class V1LaneDispatch(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        tmp = self.tmp

        class FakeCtx(object):
            tcfg = audit.TIERS["std"]

            def p(self, *parts):
                return os.path.join(tmp, *parts)

        self.c = FakeCtx()
        self.lanes_dir = os.path.join(tmp, "oc-lanes")
        self.batches = [("batch-01", os.path.join(tmp, "batches", "batch-01.md")),
                        ("batch-02", os.path.join(tmp, "batches", "batch-02.md"))]

    def dispatch(self, major, agent, role, wave):
        buf = io.StringIO()
        with mock.patch.object(oc_harness, "harness", return_value="opencode"), \
             mock.patch.object(oc_harness, "major", return_value=major), \
             redirect_stdout(buf):
            audit._print_dispatch(self.c, wave, self.batches, agent, role, "DISPATCH")
        return buf.getvalue()

    def load(self, wave):
        with open(os.path.join(self.lanes_dir, "wave-%s.json" % wave)) as fh:
            return json.load(fh)

    def test_v1_investigators_write_lanes_json_and_one_next_line(self):
        out = self.dispatch(1, "glm-rca-investigator", "judge", "A")
        lanes = self.load("A")
        self.assertEqual([lane["id"] for lane in lanes], ["batch-01", "batch-02"])
        for lane, (_, p) in zip(lanes, self.batches):
            self.assertEqual(lane["agent"], "glm-rca-investigator")
            self.assertEqual(lane["model"], "flash")
            self.assertEqual(lane["effort"], "high")
            self.assertEqual(lane["brief"], os.path.abspath(p))
            self.assertEqual(lane["dir"], os.path.abspath(os.getcwd()))
        nexts = [line for line in out.splitlines() if line.startswith("NEXT:")]
        want = "NEXT: python3 %s run %s --out %s" % (
            os.path.join(SCRIPTS, "oc_harness.py"),
            os.path.join(self.lanes_dir, "wave-A.json"),
            os.path.join(self.lanes_dir, "A"))
        self.assertEqual(nexts, [want])
        self.assertNotIn("task(", out)
        self.assertNotIn("subagent_type=", out)

    def test_v1_verifiers_use_verify_tier(self):
        self.dispatch(1, "glm-rca-verifier", "verify", "V01")
        lanes = self.load("V01")
        self.assertEqual(len(lanes), 2)
        for lane in lanes:
            self.assertEqual(lane["agent"], "glm-rca-verifier")
            self.assertEqual(lane["model"], "pro")
            self.assertEqual(lane["effort"], "max")

    def test_v2_prints_background_subagent_lines_and_writes_no_lanes(self):
        out = self.dispatch(2, "glm-rca-investigator", "judge", "A")
        for name, p in self.batches:
            want = oc_harness.dispatch_line("glm-rca-investigator", p, "rca " + name, 2,
                                            background=True)
            self.assertIn("  " + want, out)
        self.assertFalse(os.path.exists(self.lanes_dir))
        self.assertNotIn("oc_harness.py run", out)


class AgentLaneBatchSizing(unittest.TestCase):
    def env(self, value=None):
        patch = mock.patch.dict(os.environ, {}, clear=False)
        patch.start()
        self.addCleanup(patch.stop)
        os.environ.pop("OC_MAX_LANES", None)
        if value is not None:
            os.environ["OC_MAX_LANES"] = value

    def test_even_groups_balances_sizes_and_keeps_order(self):
        groups = audit._even_groups(list(range(10)), 3)
        self.assertEqual([len(g) for g in groups], [4, 3, 3])
        self.assertEqual(sum(groups, []), list(range(10)))

    def test_even_groups_of_nothing_is_empty(self):
        self.assertEqual(audit._even_groups([], 8), [])

    def test_caps_batch_count_at_default_lane_width_of_six(self):
        self.env()
        self.assertEqual(audit._oc_lanes(), 6)
        groups = audit._agent_groups(list(range(64)), 64, 12)
        self.assertEqual(sorted(len(g) for g in groups), [10] * 2 + [11] * 4)

    def test_oc_max_lanes_never_exceeds_eight(self):
        self.env("64")
        self.assertEqual(audit._oc_lanes(), 8)
        groups = audit._agent_groups(list(range(64)), 64, 12)
        self.assertEqual([len(g) for g in groups], [8] * 8)

    def test_honours_oc_max_lanes(self):
        self.env("3")
        groups = audit._agent_groups(list(range(10)), 64, 12)
        self.assertEqual([len(g) for g in groups], [4, 3, 3])

    def test_bad_oc_max_lanes_falls_back_to_six(self):
        self.env("many")
        self.assertEqual(audit._oc_lanes(), 6)
        self.env("")
        self.assertEqual(audit._oc_lanes(), 6)
        self.env("0")
        self.assertEqual(audit._oc_lanes(), 1)

    def test_batch_count_is_ceil_n_over_three(self):
        self.env()
        self.assertEqual([len(g) for g in audit._agent_groups(list(range(5)), 64, 12)], [3, 2])
        self.assertEqual([len(g) for g in audit._agent_groups(list(range(9)), 64, 12)], [3, 3, 3])
        self.assertEqual([len(g) for g in audit._agent_groups(list(range(2)), 64, 12)], [2])

    def test_cap_limits_batch_count(self):
        self.env()
        groups = audit._agent_groups(list(range(20)), 4, 12)
        self.assertEqual([len(g) for g in groups], [5] * 4)

    def test_batch_never_exceeds_max_per(self):
        self.env()
        groups = audit._agent_groups(list(range(64)), 4, 12)
        self.assertTrue(all(len(g) <= 12 for g in groups))
        self.assertEqual(sum(groups, []), list(range(64)))
        self.assertEqual(len(audit._agent_groups(list(range(40)), 4, 3)), 14)

    def test_cpu_threads_clamps_to_eight(self):
        self.env()
        for var in ("AUDIT_THREADS", "CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS"):
            os.environ.pop(var, None)
        self.assertEqual(audit.cpu_threads(), 8)
        self.assertEqual(audit.cpu_threads(64), 8)
        self.assertEqual(audit.cpu_threads(3), 3)
        os.environ["AUDIT_THREADS"] = "64"
        self.assertEqual(audit.cpu_threads(), 8)
        os.environ["AUDIT_THREADS"] = "2"
        self.assertEqual(audit.cpu_threads(), 2)
        self.assertEqual(audit.Fan(None, 64).threads, 8)

    def test_empty_input_gives_no_batches(self):
        self.assertEqual(audit._agent_groups([], 20, 12), [])


class SetupAgentLaneText(IsolatedHome):
    def test_setup_describes_real_agent_lane_routing(self):
        with mock.patch.object(oc_harness, "detect", return_value=2), \
             mock.patch.object(oc_harness, "install", return_value=[]):
            rc, out = self.run_setup()
        self.assertEqual(rc or 0, 0)
        self.assertIn("OC_MAX_LANES", out)
        self.assertIn("v1 runs them in parallel through oc_harness.py run", out)
        self.assertIn("v2 dispatches them as background subagent calls", out)


if __name__ == "__main__":
    unittest.main()
