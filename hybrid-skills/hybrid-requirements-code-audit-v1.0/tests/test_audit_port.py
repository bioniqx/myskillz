import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "scripts"))
ORIG_AUDIT = (Path(__file__).resolve().parents[3] / "claude-skills" / "claude-requirements-code-audit"
              / "scripts" / "audit.py")
FORK_AUDIT = HERE / "scripts" / "audit.py"

import audit  # noqa: E402
import ha_router  # noqa: E402


def load_original():
    spec = importlib.util.spec_from_file_location("orig_audit", str(ORIG_AUDIT))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def child_env(tmp):
    env = dict(os.environ)
    for key in ("CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS", "HYBRID_OPENCODE_STD", "HYBRID_OPENCODE_LITE",
                "HYBRID_OPENCODE_MODELS", "XDG_DATA_HOME"):
        env.pop(key, None)
    home = Path(tmp) / "home"
    home.mkdir(parents=True, exist_ok=True)
    env.update({
        "HOME": str(home),
        "HYBRID_AUDIT_ROUTING": str(Path(tmp) / "routing.json"),
        "HYBRID_AUDIT_DOCTOR_CACHE": str(Path(tmp) / "doctor.json"),
        "HYBRID_AUDIT_TELEMETRY": str(Path(tmp) / "lanes.jsonl"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONIOENCODING": "utf-8",
    })
    stub = Path(tmp) / "bin" / "opencode"
    stub.parent.mkdir(parents=True, exist_ok=True)
    stub.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    stub.chmod(0o755)
    env["PATH"] = str(stub.parent) + os.pathsep + env.get("PATH", "")
    return env


@unittest.skipUnless(ORIG_AUDIT.is_file(), "claude-requirements-code-audit is not present")
class ConstantsMatchOriginalTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.orig = load_original()

    def test_agent_identity_matches_original(self):
        self.assertEqual(audit.PLUGIN_NAME, self.orig.PLUGIN_NAME)
        self.assertEqual(audit.AGENT_NAMES, self.orig.AGENT_NAMES)
        self.assertEqual(audit.PLUGIN_NAME, "claude-req-audit")
        self.assertEqual(audit.AGENT_NAMES["investigator"], "claude-rca-investigator")

    def test_claude_preset_models_equal_original(self):
        self.assertEqual(audit.models_for("claude"), self.orig.MODELS)
        self.assertEqual(audit.models_for("claude")["investigator"], "sonnet")

    def test_offload_presets_keep_the_cheaper_investigator(self):
        for preset in ("hybrid", "opencode"):
            models = audit.models_for(preset)
            self.assertEqual(models["investigator"], "haiku", preset)
            self.assertEqual(models["verifier"], "sonnet", preset)
            self.assertEqual(models["parser"], "sonnet", preset)

    def test_parse_threshold_per_preset(self):
        self.assertEqual(audit.PARSE_THRESHOLD_WORDS, self.orig.PARSE_THRESHOLD_WORDS)
        self.assertEqual(audit.parse_threshold("claude"), 800)
        self.assertEqual(audit.parse_threshold(""), 800)
        self.assertEqual(audit.parse_threshold("hybrid"), 2500)
        self.assertEqual(audit.parse_threshold("opencode"), 2500)

    def test_offload_presets_are_declared_by_the_router(self):
        self.assertEqual(ha_router.OFFLOAD_PRESETS, ("hybrid", "opencode"))

    def test_rule_blocks_match_original(self):
        self.assertEqual(audit.VERIFY_SPEED_RULES, self.orig.VERIFY_SPEED_RULES)
        self.assertEqual(audit.SEARCH_GLOB_RULE, self.orig.SEARCH_GLOB_RULE)
        self.assertTrue(audit.HARD_RULES.endswith("\n" + audit.SEARCH_GLOB_RULE))

    def test_lean_agents_follow_the_original(self):
        self.assertEqual(audit.LEAN_BATCH, self.orig.LEAN_BATCH)
        self.assertFalse(audit.lean_agents(types.SimpleNamespace(cfg={"agents": "generic"})))
        self.assertFalse(audit.lean_agents(types.SimpleNamespace(cfg={"agents": "solo"})))
        self.assertFalse(audit.lean_agents(types.SimpleNamespace(cfg={})))
        self.assertTrue(audit.lean_agents(types.SimpleNamespace(cfg={"agents": "plugin"})))

    def test_lean_batching_uses_lean_batch_size(self):
        items = [{"id": "REQ-%03d" % i, "category": "c"} for i in range(1, 11)]
        lean = audit.partition_items(items, 64, False, True)
        self.assertEqual([len(b) for b in lean], [3, 3, 2, 2])
        self.assertEqual([len(b) for b in audit.partition_items(items, 64, False)], [3, 3, 2, 2])

    def test_batching_constants_follow_the_original(self):
        for name in ("SOFT_WIDTH", "MIN_BATCH", "MAX_BATCH", "MAX_PARSERS", "RECOMMENDED_CAP"):
            self.assertEqual(getattr(audit, name), getattr(self.orig, name), name)
        self.assertFalse(hasattr(audit, "TARGET_CAP"))


class VerifyBodyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.env = child_env(self.tmp)
        self.root = self.tmp / "work"
        (self.root / "src").mkdir(parents=True)
        (self.root / "src" / "app.py").write_text("def login(email, password):\n    return True\n", encoding="utf-8")
        (self.root / "spec.md").write_text("# Spec\n\nUsers MUST log in.\n", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def run_cli(self, *args):
        p = subprocess.run([sys.executable, str(FORK_AUDIT), "--cwd", str(self.root)] + list(args), env=self.env,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf-8")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_verify_body_carries_the_verifier_speed_rules(self):
        self.run_cli("init", "--spec", str(self.root / "spec.md"), "--cap", "2", "--lang", "en", "--preset", "claude")
        row = {"id": "REQ-001", "text": "Users MUST log in.", "strength": "MUST", "category": "auth",
               "stakes": "normal", "search_hints": ["login", "password"], "tags": [], "source": "§1"}
        (self.root / ".hybrid-audit" / "checklist.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
        self.run_cli("plan")
        c = audit.Ctx(str(self.root))
        repo_map = (c.out / "repo_map.md").read_text(encoding="utf-8")
        body = audit.verify_body(c, "batch-V01", ["REQ-001"], audit.Merged(c), repo_map)
        self.assertIn(audit.VERIFY_SPEED_RULES, body)
        self.assertIn("You are the last check on this item", body)
        self.assertNotIn("About 6 tool calls per requirement", body)


if __name__ == "__main__":
    unittest.main()
