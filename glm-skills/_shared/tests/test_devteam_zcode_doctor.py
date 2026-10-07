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

    def zfix(self, flash=None, main=None):
        ns = argparse.Namespace(fix=True, harness="zcode", flash=flash, main=main)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            dt.doctor_zcode(ns, self.repo)
        return buf.getvalue()

    def cdoctor(self, fix=False, flash=None, main=None):
        ns = argparse.Namespace(fix=fix, harness="zcode", flash=flash, main=main)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            dt.cmd_doctor(ns)
        return buf.getvalue()

    def test_render_agent_zcode_converts_frontmatter(self):
        flash, main = "acct/Flash", "acct/Main"
        cases = {
            "glm-programmer": ("model: " + flash, "thoughtLevel: high"),
            "glm-programmer-lite": ("model: " + flash, "thoughtLevel: low"),
            "glm-programmer-strong": ("model: " + main, "thoughtLevel: high"),
            "glm-code-reviewer": ("model: " + main, "thoughtLevel: high"),
            "glm-spot-reviewer": ("model: " + flash, "thoughtLevel: high"),
            "glm-investigator": ("model: " + flash, "thoughtLevel: high"),
            "glm-team-leader": ("model: " + main, "thoughtLevel: max"),
        }
        for name, (model_line, tl_line) in cases.items():
            text = dt.render_agent_zcode(AGENTS_SRC, name, flash, main)
            self.assertTrue(text.startswith("---\n"), name)
            fm, body = text.split("\n---\n", 1)
            self.assertTrue(body.strip(), name)
            self.assertIn("name: " + name, fm.splitlines(), name)
            self.assertIn(model_line, fm.splitlines(), name)
            self.assertIn(tl_line, fm.splitlines(), name)
            self.assertTrue(fm_keys(fm) <= ALLOWED_KEYS, (name, sorted(fm_keys(fm) - ALLOWED_KEYS)))
            for bad in BAD_KEYS:
                self.assertNotIn("\n" + bad, "\n" + fm, (name, bad))
            for alias in ("haiku", "sonnet", "opus"):
                self.assertNotIn("\nmodel: " + alias, "\n" + fm, (name, alias))

    def test_fix_installs_seven_agents_with_zcode_frontmatter(self):
        out = self.zfix()
        self.assertIn("harness zcode", out)
        agents_dir = os.path.join(self.home, ".zcode", "agents")
        self.assertEqual(sorted(os.listdir(agents_dir)),
                         sorted(name + ".md" for name in ZCODE_AGENTS))
        flash_agents = {"glm-programmer", "glm-programmer-lite",
                        "glm-spot-reviewer", "glm-investigator"}
        thought = {"glm-programmer": "high", "glm-programmer-lite": "low",
                   "glm-programmer-strong": "high", "glm-code-reviewer": "high",
                   "glm-spot-reviewer": "high", "glm-investigator": "high",
                   "glm-team-leader": "max"}
        for name in ZCODE_AGENTS:
            fm = frontmatter(os.path.join(agents_dir, name + ".md"))
            self.assertTrue(fm_keys(fm) <= ALLOWED_KEYS, (name, sorted(fm_keys(fm) - ALLOWED_KEYS)))
            self.assertNotIn("\nmodel: haiku", "\n" + fm, name)
            self.assertNotIn("\nmodel: sonnet", "\n" + fm, name)
            self.assertNotIn("\nmodel: opus", "\n" + fm, name)
            for bad in BAD_KEYS:
                self.assertNotIn("\n" + bad, "\n" + fm, (name, bad))
            model_lines = [ln for ln in fm.splitlines() if ln.startswith("model:")]
            expected = "glm-5.3-flash" if name in flash_agents else "glm-5.3"
            self.assertEqual(model_lines, ["model: " + expected], name)
            tl_lines = [ln for ln in fm.splitlines() if ln.startswith("thoughtLevel:")]
            self.assertEqual(tl_lines, ["thoughtLevel: " + thought[name]], name)
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
        want = dt.render_agent_zcode(AGENTS_SRC, "glm-programmer", "glm-5.3-flash", "glm-5.3")
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
        out2 = self.cdoctor(fix=True, flash="acct/Flash", main="acct/Main")
        self.assertIn("STALE: agent glm-programmer does not match the rendered file", out2)
        self.assertIn("\nmodel: acct/Flash",
                      "\n" + frontmatter(os.path.join(agents_dir, "glm-programmer.md")))
        self.assertIn("\nmodel: acct/Main",
                      "\n" + frontmatter(os.path.join(agents_dir, "glm-team-leader.md")))


if __name__ == "__main__":
    unittest.main()
