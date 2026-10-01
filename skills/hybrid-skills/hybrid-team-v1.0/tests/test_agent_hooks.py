"""Black-box tests for the hybrid-team agent hooks: each agent's hook probes the hybrid-team /
hybrid-team-v1.0 installs (first match wins, silent exit 0 with no match) and stays compatible with
devteam.py's HOOK_LOOP_RE / pin_hooks.
"""
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
AGENTS_DIR = REPO / "agents"
SKILL_MD = REPO / "SKILL.md"

AGENT_HOOK_MODES = {
    "hybrid-team-leader.md": ["edit-ro", "bash-ro"],
    "hybrid-team-programmer.md": ["edit", "bash", "stop"],
    "hybrid-team-code-reviewer.md": ["edit-ro", "bash-ro"],
    "hybrid-team-spot-reviewer.md": ["edit-ro", "bash-ro"],
    "hybrid-team-investigator.md": ["edit-ro", "bash-ro"],
}

STUB_GUARD = (
    "import sys, os\n"
    "d = os.path.basename(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))\n"
    "print(d + ' ' + sys.argv[1])\n"
)

DASH = shutil.which("dash")
PATH = os.environ.get("PATH", "/usr/bin:/bin")


def _load_devteam():
    sys.path.insert(0, str(REPO / "scripts"))
    path = REPO / "scripts" / "devteam.py"
    spec = importlib.util.spec_from_file_location("ht_devteam", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _fold(match_text):
    """Fold a YAML ">-" block scalar match (raw text with literal newlines)
    into the single-line string a YAML parser would hand the host."""
    lines = match_text.split("\n")
    scalar_lines = [l.strip() for l in lines[1:]]
    return " ".join(scalar_lines)


def _extract_hooks(devteam, text):
    """[(mode, inner_shell_script), ...] for every HOOK_LOOP_RE match in text."""
    hooks = []
    for m in devteam.HOOK_LOOP_RE.finditer(text):
        mode = m.group(1)
        folded = _fold(m.group(0))
        inner = re.match(r"^sh -c '(.*)'$", folded, re.DOTALL).group(1)
        hooks.append((mode, inner))
    return hooks


def _write_stub(root):
    guard = root / "scripts" / "guard.py"
    guard.parent.mkdir(parents=True, exist_ok=True)
    guard.write_text(STUB_GUARD)
    return guard


def _run(shell, inner, env):
    return subprocess.run(
        [shell, "-c", inner],
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )


class TestAgentHookGlobs(unittest.TestCase):
    devteam = None

    @classmethod
    def setUpClass(cls):
        cls.devteam = _load_devteam()
        cls.texts = {name: (AGENTS_DIR / name).read_text() for name in AGENT_HOOK_MODES}
        cls.hooks = {
            name: _extract_hooks(cls.devteam, text) for name, text in cls.texts.items()
        }

    def test_hook_count_per_agent(self):
        for name, modes in AGENT_HOOK_MODES.items():
            got = [mode for mode, _ in self.hooks[name]]
            self.assertEqual(got, modes, name)

    def test_hooks_execute_stub_with_right_mode(self):
        for name, hooks in self.hooks.items():
            for mode, inner in hooks:
                with tempfile.TemporaryDirectory() as tmp:
                    home = Path(tmp).resolve() / "home"
                    home.mkdir()
                    _write_stub(home / ".claude" / "skills" / "hybrid-team-v1.0")
                    env = {"HOME": str(home), "PATH": PATH}
                    for shell in filter(None, ["sh", DASH]):
                        res = _run(shell, inner, env)
                        self.assertEqual(res.returncode, 0, f"{name}/{mode}/{shell}: {res.stderr}")
                        self.assertEqual(
                            res.stdout.strip(), f"hybrid-team-v1.0 {mode}",
                            f"{name}/{mode}/{shell}: {res.stdout!r} {res.stderr!r}",
                        )

    def test_no_match_exits_silently(self):
        mode, inner = self.hooks["hybrid-team-programmer.md"][0]
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp).resolve() / "empty-home"
            home.mkdir()
            env = {"HOME": str(home), "PATH": PATH}
            for shell in filter(None, ["sh", DASH]):
                res = _run(shell, inner, env)
                self.assertEqual(res.returncode, 0, f"{shell}: {res.stderr}")
                self.assertEqual(res.stdout, "", f"{shell}: {res.stdout!r}")

    def test_claude_project_dir_unset(self):
        mode, inner = self.hooks["hybrid-team-leader.md"][0]
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp).resolve() / "home"
            home.mkdir()
            _write_stub(home / ".claude" / "skills" / "hybrid-team-v1.0")
            # CLAUDE_PROJECT_DIR is deliberately absent from env, not just empty.
            env = {"HOME": str(home), "PATH": PATH}
            self.assertNotIn("CLAUDE_PROJECT_DIR", env)
            res = _run("sh", inner, env)
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertEqual(res.stdout.strip(), f"hybrid-team-v1.0 {mode}")

    def test_two_installs_first_match_wins(self):
        mode, inner = self.hooks["hybrid-team-investigator.md"][0]
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp).resolve() / "home"
            home.mkdir()
            _write_stub(home / ".claude" / "skills" / "hybrid-team-v1.0")
            _write_stub(home / ".claude" / "skills" / "hybrid-team")
            env = {"HOME": str(home), "PATH": PATH}
            for shell in filter(None, ["sh", DASH]):
                res = _run(shell, inner, env)
                self.assertEqual(res.returncode, 0, f"{shell}: {res.stderr}")
                self.assertEqual(
                    res.stdout.strip(), f"hybrid-team {mode}",
                    f"{shell}: expected the first probed install (hybrid-team) to win, got {res.stdout!r}",
                )

    def test_pin_hooks_rewrites_all_agents(self):
        guard = "/abs/pinned/guard.py"
        for name, text in self.texts.items():
            rewritten = self.devteam.pin_hooks(text, guard)
            for mode in AGENT_HOOK_MODES[name]:
                expected = f'command: "python3 \\"{guard}\\" {mode}"'
                self.assertIn(expected, rewritten, name)
            self.assertIsNone(self.devteam.HOOK_LOOP_RE.search(rewritten), name)
            self.assertEqual(
                len(self.devteam.HOOK_PIN_RE.findall(rewritten)),
                len(AGENT_HOOK_MODES[name]),
                name,
            )


if __name__ == "__main__":
    unittest.main()
