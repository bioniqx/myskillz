import argparse
import io
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.normpath(os.path.join(HERE, "..", "..", "oc-requirements-code-audit", "scripts"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import oc_audit as audit  # noqa: E402
import oc_harness  # noqa: E402

SETUP_MD = os.path.normpath(os.path.join(HERE, "..", "..", "oc-requirements-code-audit", "SETUP.md"))
AGENTS = os.path.normpath(os.path.join(HERE, "..", "..", "oc-requirements-code-audit", "opencode", "agents"))


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
        inv = os.path.join(self.home, ".config", "opencode", "agents", "oc-rca-investigator.md")
        ver = os.path.join(self.home, ".config", "opencode", "agents", "oc-rca-verifier.md")
        self.assertTrue(os.path.isfile(inv), out)
        self.assertTrue(os.path.isfile(ver), out)
        with open(inv) as fh:
            self.assertIn("mode: subagent", fh.read())
        with open(ver) as fh:
            self.assertIn("mode: subagent", fh.read())

    def test_render_agent_gives_the_v2_dialect(self):
        with open(os.path.join(AGENTS, "oc-rca-investigator.md")) as fh:
            rendered = oc_harness.render_agent(fh.read(), 2)
        self.assertIn("mode: subagent", rendered)

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

    def test_returns_1_when_only_v1_is_installed(self):
        with mock.patch.object(oc_harness, "detect", return_value=1), \
             mock.patch.object(oc_harness, "install", return_value=[]) as inst:
            rc, out = self.run_setup()
        self.assertEqual(rc, 1)
        self.assertIn("OpenCode v2 required", out)
        inst.assert_not_called()


class SetupDocInstructions(unittest.TestCase):
    def test_opencode_section_points_at_the_install_command_not_hand_copy(self):
        with open(SETUP_MD) as fh:
            text = fh.read()
        self.assertTrue(
            "oc_harness.py install" in text or "oc_audit.py setup" in text,
            "SETUP.md should name the install command for OpenCode")
        self.assertNotIn("from `opencode/agents/`", text,
                         "SETUP.md should not tell users to hand-copy the neutral opencode/agents/*.md sources")


class DispatchLine(unittest.TestCase):
    def test_uses_shared_dispatch_line_at_major_2(self):
        line = audit._dispatch("rca-investigator", "/a/batch-01.md", "rca batch-01")
        want = oc_harness.dispatch_line("rca-investigator", "/a/batch-01.md", "rca batch-01", 2,
                                        background=True)
        self.assertEqual(line, want)

    def test_print_dispatch_prints_one_background_row_per_batch(self):
        batches = [("batch-01", "/a/batch-01.md"), ("batch-02", "/a/batch-02.md")]
        buf = io.StringIO()
        with redirect_stdout(buf):
            audit._print_dispatch(None, "A", batches, "rca-investigator", "judge", "DISPATCH")
        out = buf.getvalue()
        for name, p in batches:
            want = oc_harness.dispatch_line("rca-investigator", p, "rca " + name, 2,
                                            background=True)
            self.assertIn("  " + want, out)
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

    def test_caps_batch_count_at_default_lane_width(self):
        self.env()
        groups = audit._agent_groups(list(range(64)), 64)
        self.assertEqual([len(g) for g in groups], [8] * 8)

    def test_honours_oc_max_lanes(self):
        self.env("3")
        groups = audit._agent_groups(list(range(10)), 64)
        self.assertEqual([len(g) for g in groups], [4, 3, 3])

    def test_oc_max_lanes_above_ceiling_is_clamped_to_eight(self):
        self.env("64")
        self.assertEqual(audit._oc_lanes(), 8)
        groups = audit._agent_groups(list(range(64)), 64)
        self.assertEqual([len(g) for g in groups], [8] * 8)

    def test_cpu_threads_never_exceeds_eight(self):
        self.env()
        self.assertEqual(audit.cpu_threads(64), 8)
        self.assertEqual(audit.cpu_threads(), 8)
        with mock.patch.dict(os.environ, {"AUDIT_THREADS": "32"}):
            self.assertEqual(audit.cpu_threads(), 8)
            self.assertEqual(audit.cpu_threads(3), 3)

    def test_repair_wave_never_makes_more_briefs_than_lanes(self):
        self.env()
        with tempfile.TemporaryDirectory() as d:
            rows = [{"id": "REQ-%03d" % i, "lint_error": "x"} for i in range(100)]
            self.assertLessEqual(len(audit.repair_wave(d, rows, d, 1)), 8)

    def test_cap_below_lane_width_wins(self):
        self.env()
        groups = audit._agent_groups(list(range(64)), 2)
        self.assertEqual([len(g) for g in groups], [32, 32])

    def test_bad_oc_max_lanes_falls_back(self):
        self.env("many")
        self.assertEqual(audit._oc_lanes(), 8)
        self.env("0")
        self.assertEqual(audit._oc_lanes(), 1)

    def test_fewer_items_than_lanes_gives_one_each(self):
        self.env()
        groups = audit._agent_groups(list(range(5)), 64)
        self.assertEqual([len(g) for g in groups], [1] * 5)

    def test_empty_input_gives_no_batches(self):
        self.assertEqual(audit._agent_groups([], 20), [])


class SetupText(IsolatedHome):
    def test_setup_describes_lane_routing_without_a_model(self):
        with mock.patch.object(oc_harness, "detect", return_value=2), \
             mock.patch.object(oc_harness, "install", return_value=[]):
            rc, out = self.run_setup()
        self.assertEqual(rc or 0, 0)
        self.assertIn("OC_MAX_LANES", out)
        self.assertIn("background agent calls", out)
        self.assertNotIn("oc_harness.py run", out)


if __name__ == "__main__":
    unittest.main()
