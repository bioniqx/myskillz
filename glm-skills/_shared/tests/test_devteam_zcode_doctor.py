import argparse
import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
GLM = os.path.dirname(os.path.dirname(HERE))
SCRIPTS = os.path.join(GLM, "glm-dev-team", "scripts")
sys.path.insert(0, SCRIPTS)


def load_devteam():
    spec = importlib.util.spec_from_file_location("devteam_zc", os.path.join(SCRIPTS, "devteam.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


dt = load_devteam()

ZCODE_AGENTS = ("glm-code-reviewer", "glm-investigator", "glm-programmer",
                "glm-programmer-lite", "glm-programmer-strong",
                "glm-spot-reviewer", "glm-team-leader")
ALLOWED_KEYS = {"name", "description", "model", "thoughtLevel", "color", "tools",
                "disallowedTools", "maxTurns", "background", "injectAgentsMd", "mcpServers"}
BAD_KEYS = ("effort:", "hooks:", "mode:", "permissionMode:", "steps:",
            "omitClaudeMd:", "variant:", "memory:", "isolation:", "temperature:")
AGENTS_SRC = os.path.join(os.path.dirname(SCRIPTS), "agents")
GUARD_CMD = "python3 " + os.path.join(SCRIPTS, "guard.py") + " zcode"


def frontmatter(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read().split("\n---\n")[0]


def fm_keys(fm):
    keys = set()
    for line in fm.splitlines():
        if not line.strip() or line.lstrip().startswith("#") or line[:1] in (" ", "\t"):
            continue
        if ":" in line:
            keys.add(line.split(":", 1)[0].strip())
    return keys


class TestDevteamZcodeDoctor(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.home = os.path.join(self.tmp, "home")
        self.repo = os.path.join(self.tmp, "repo")
        for d in (self.home, self.repo):
            os.makedirs(d)
        for args in (["init", "-q"],
                     ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false",
                      "commit", "-q", "--allow-empty", "-m", "init"]):
            subprocess.run(["git"] + args, cwd=self.repo, check=True, capture_output=True)
        self.old = os.getcwd()
        os.chdir(self.repo)
        self.env = mock.patch.dict(os.environ, {"HOME": self.home})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        os.chdir(self.old)
        shutil.rmtree(self.tmp)

    def zfix(self):
        ns = argparse.Namespace(fix=True, harness="zcode")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            dt.doctor_zcode(ns, self.repo)
        return buf.getvalue()

    def cdoctor(self, fix=False):
        ns = argparse.Namespace(fix=fix, harness="zcode")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            dt.cmd_doctor(ns)
        return buf.getvalue()

    @staticmethod
    def source_text(name):
        with open(os.path.join(AGENTS_SRC, name + ".md"), encoding="utf-8") as fh:
            return fh.read()

    def test_zcode_agent_text_is_the_repo_file_verbatim(self):
        for name in ZCODE_AGENTS:
            self.assertEqual(dt.zcode_agent_text(AGENTS_SRC, name), self.source_text(name), name)

    def test_fix_installs_seven_agents_with_zcode_frontmatter(self):
        out = self.zfix()
        self.assertIn("harness zcode", out)
        agents_dir = os.path.join(self.home, ".zcode", "agents")
        self.assertEqual(sorted(os.listdir(agents_dir)),
                         sorted(name + ".md" for name in ZCODE_AGENTS))
        for name in ZCODE_AGENTS:
            with open(os.path.join(agents_dir, name + ".md"), encoding="utf-8") as fh:
                self.assertEqual(fh.read(), self.source_text(name), name)
            fm = frontmatter(os.path.join(agents_dir, name + ".md"))
            self.assertTrue(fm_keys(fm) <= ALLOWED_KEYS, (name, sorted(fm_keys(fm) - ALLOWED_KEYS)))
            for alias in ("haiku", "sonnet", "opus"):
                self.assertNotIn("\nmodel: " + alias, "\n" + fm, (name, alias))
            for bad in BAD_KEYS:
                self.assertNotIn("\n" + bad, "\n" + fm, (name, bad))
        self.assertFalse(os.path.exists(os.path.join(self.repo, ".claude", "settings.local.json")))
        self.assertFalse(os.path.exists(os.path.join(self.home, ".claude", "settings.local.json")))

    def test_hooks_merge_preserves_user_config(self):
        cli = os.path.join(self.home, ".zcode", "cli")
        os.makedirs(cli, exist_ok=True)
        cfg_path = os.path.join(cli, "config.json")
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump({"plugins": {"theme": {"enabled": True}}, "model": "acct/Main"}, f)
        self.zfix()
        with open(cfg_path, encoding="utf-8") as f:
            cfg = json.load(f)
        self.assertEqual(cfg["plugins"], {"theme": {"enabled": True}})
        self.assertEqual(cfg["model"], "acct/Main")
        hooks = cfg.get("hooks") or {}
        self.assertIn("enabled", hooks)
        self.assertTrue(hooks["enabled"])
        events = hooks.get("events") or {}
        self.assertEqual(events.get("PreToolUse"), [
            {"matcher": "Write|Edit", "hooks": [{"type": "process", "command": GUARD_CMD}]},
            {"matcher": "Bash", "hooks": [{"type": "process", "command": GUARD_CMD}]},
        ])
        self.assertEqual(events.get("Stop"), [{"hooks": [{"type": "process", "command": GUARD_CMD}]}])
        for key in ("PreToolUse", "Stop"):  # legacy unwrapped keys must not survive a render
            self.assertNotIn(key, hooks)

    def test_changed_files_are_replaced_in_place_without_bak(self):
        agents_dir = os.path.join(self.home, ".zcode", "agents")
        cfg_path = os.path.join(self.home, ".zcode", "cli", "config.json")
        self.zfix()
        agent = os.path.join(agents_dir, "glm-programmer.md")
        want = dt.zcode_agent_text(AGENTS_SRC, "glm-programmer")
        with open(agent, "a", encoding="utf-8") as f:
            f.write("my edit\n")
        with open(cfg_path, encoding="utf-8") as f:
            cfg = json.load(f)
        cfg["userKey"] = "keep me"
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
        self.zfix()
        with open(agent, encoding="utf-8") as f:
            self.assertEqual(f.read(), want)
        with open(cfg_path, encoding="utf-8") as f:
            self.assertEqual(json.load(f)["userKey"], "keep me")
        baks = sorted([f for f in os.listdir(agents_dir) if f.endswith(".bak")] +
                      [f for f in os.listdir(os.path.dirname(cfg_path)) if f.endswith(".bak")])
        self.assertFalse(baks, baks)

    def test_rerun_is_a_noop(self):
        agents_dir = os.path.join(self.home, ".zcode", "agents")
        cli_dir = os.path.join(self.home, ".zcode", "cli")
        self.zfix()
        cfg_path = os.path.join(cli_dir, "config.json")
        agent = os.path.join(agents_dir, "glm-programmer.md")
        with open(agent, encoding="utf-8") as f:
            agent_before = f.read()
        with open(cfg_path, encoding="utf-8") as f:
            cfg_before = f.read()
        self.zfix()
        with open(agent, encoding="utf-8") as f:
            self.assertEqual(f.read(), agent_before)
        with open(cfg_path, encoding="utf-8") as f:
            self.assertEqual(f.read(), cfg_before)
        baks = sorted([f for f in os.listdir(agents_dir) if f.endswith(".bak")] +
                      [f for f in os.listdir(cli_dir) if f.endswith(".bak")])
        self.assertFalse(baks, baks)

    def test_cmd_doctor_routes_zcode(self):
        agents_dir = os.path.join(self.home, ".zcode", "agents")
        out = self.cdoctor(fix=True)
        installed = sorted(os.listdir(agents_dir)) if os.path.isdir(agents_dir) else []
        self.assertIn("glm-programmer.md", installed)
        self.assertIn("harness zcode", out)
        self.assertFalse(os.path.exists(os.path.join(self.repo, ".claude", "settings.local.json")))
        report = self.cdoctor(fix=False)
        self.assertIn("harness zcode", report)
        self.assertNotIn("MISSING:", report)
        agent = os.path.join(agents_dir, "glm-programmer.md")
        with open(agent, "a", encoding="utf-8") as f:
            f.write("drift\n")
        self.assertIn("STALE: agent glm-programmer does not match the source file", self.cdoctor(fix=False))
        self.cdoctor(fix=True)
        with open(agent, encoding="utf-8") as f:
            self.assertEqual(f.read(), self.source_text("glm-programmer"))


if __name__ == "__main__":
    unittest.main()
