"""Black-box tests for K06: dev-team agent hooks probe dev-team-* installs.

Covers W4-1 (agents/*.md hook glob for dev-team-* installs, first match wins,
silent exit 0 with no match, HOOK_LOOP_RE/pin_hooks compatibility) and W4-2
(SKILL.md "Speed ceiling" trimmed to the Remaining-dials list + closing
sentence, frontmatter untouched).
"""
import importlib.util
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1] / "claude-dev-team-v3.2"
AGENTS_DIR = REPO / "agents"
SKILL_MD = REPO / "SKILL.md"

AGENT_HOOK_MODES = {
    "claude-team-leader.md": ["edit-ro", "bash-ro"],
    "claude-programmer.md": ["edit", "bash", "stop"],
    "claude-code-reviewer.md": ["edit-ro", "bash-ro"],
    "claude-spot-reviewer.md": ["edit-ro", "bash-ro"],
    "claude-investigator.md": ["edit-ro", "bash-ro"],
}

STUB_GUARD = (
    "import sys, os\n"
    "d = os.path.basename(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))\n"
    "print(d + ' ' + sys.argv[1])\n"
)

DASH = shutil.which("dash")
PATH = os.environ.get("PATH", "/usr/bin:/bin")


def _load_devteam():
    path = REPO / "scripts" / "devteam.py"
    spec = importlib.util.spec_from_file_location("k06_devteam", path)
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
                    _write_stub(home / ".claude" / "skills" / "claude-dev-team-v3.2")
                    env = {"HOME": str(home), "PATH": PATH}
                    for shell in filter(None, ["sh", DASH]):
                        res = _run(shell, inner, env)
                        self.assertEqual(res.returncode, 0, f"{name}/{mode}/{shell}: {res.stderr}")
                        self.assertEqual(
                            res.stdout.strip(), f"claude-dev-team-v3.2 {mode}",
                            f"{name}/{mode}/{shell}: {res.stdout!r} {res.stderr!r}",
                        )

    def test_no_match_exits_silently(self):
        mode, inner = self.hooks["claude-programmer.md"][0]
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp).resolve() / "empty-home"
            home.mkdir()
            env = {"HOME": str(home), "PATH": PATH}
            for shell in filter(None, ["sh", DASH]):
                res = _run(shell, inner, env)
                self.assertEqual(res.returncode, 0, f"{shell}: {res.stderr}")
                self.assertEqual(res.stdout, "", f"{shell}: {res.stdout!r}")

    def test_claude_project_dir_unset(self):
        mode, inner = self.hooks["claude-team-leader.md"][0]
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp).resolve() / "home"
            home.mkdir()
            _write_stub(home / ".claude" / "skills" / "claude-dev-team-v3.2")
            # CLAUDE_PROJECT_DIR is deliberately absent from env, not just empty.
            env = {"HOME": str(home), "PATH": PATH}
            self.assertNotIn("CLAUDE_PROJECT_DIR", env)
            res = _run("sh", inner, env)
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertEqual(res.stdout.strip(), f"claude-dev-team-v3.2 {mode}")

    def test_two_installs_first_match_wins(self):
        mode, inner = self.hooks["claude-investigator.md"][0]
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp).resolve() / "home"
            home.mkdir()
            _write_stub(home / ".claude" / "skills" / "claude-dev-team-v3.2")
            _write_stub(home / ".claude" / "skills" / "claude-dev-team-v4")
            env = {"HOME": str(home), "PATH": PATH}
            for shell in filter(None, ["sh", DASH]):
                res = _run(shell, inner, env)
                self.assertEqual(res.returncode, 0, f"{shell}: {res.stderr}")
                self.assertEqual(
                    res.stdout.strip(), f"claude-dev-team-v3.2 {mode}",
                    f"{shell}: expected the alphabetically-first install to win, got {res.stdout!r}",
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


class TestSkillMdSpeedCeiling(unittest.TestCase):
    EXPECTED_FRONTMATTER = (
        "---\n"
        "name: claude-dev-team\n"
        "description: >-\n"
        "  Use for ANY non-trivial software-development work in a codebase: implement, build, add,\n"
        "  create, extend a feature; fix or debug a bug; refactor or clean up; migrate, upgrade or\n"
        "  codemod; backfill tests; optimize performance; audit or review code; wire up CI, build,\n"
        "  infra, deploy or config; write technical docs; scaffold a new project; investigate\n"
        "  feasibility or root cause — \"implement X\", \"why is this slow\", \"upgrade us to v3\", \"review\n"
        "  this PR\", \"add tests for …\", \"make it faster\", \"set up CI\", \"start a new service\", even when\n"
        "  they never say \"team\", \"agents\" or \"tests\". Skip only for a trivial one-touch edit or a pure\n"
        "  question you can answer by reading.\n"
        "allowed-tools:\n"
        "  - Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/devteam.py:*)\n"
        "  - Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/devteam.py *)\n"
        "---"
    )

    def setUp(self):
        self.text = SKILL_MD.read_text()

    def _speed_ceiling_section(self):
        # the section moved out of SKILL.md into references/profiles.md (loaded on demand)
        profiles = (SKILL_MD.parent / "references" / "profiles.md").read_text()
        m = re.search(r"## Speed ceiling\n(.*?)(?=\n## |\Z)", profiles, re.DOTALL)
        self.assertIsNotNone(m, "Speed ceiling section not found")
        return " ".join(m.group(1).split())

    def test_frontmatter_unchanged(self):
        idx = self.text.index("---", 3)
        frontmatter = self.text[: idx + 3]
        self.assertEqual(frontmatter, self.EXPECTED_FRONTMATTER)

    def test_speed_ceiling_drops_opening_enumeration(self):
        section = self._speed_ceiling_section()
        for dropped in ("Everything cuttable is cut", "no preamble turn", "cap-2 loops"):
            self.assertNotIn(dropped, section)

    def test_speed_ceiling_keeps_remaining_dials_and_closer(self):
        section = self._speed_ceiling_section()
        self.assertIn("Remaining dials, in order:", section)
        self.assertIn("`/fast`", section)
        self.assertIn("profile `turbo` / `spike`", section)
        self.assertIn("review_batch", section)
        self.assertIn("checkpoint_every", section)
        self.assertIn("effort: low", section)
        self.assertIn("Explore", section)
        self.assertIn(
            "If asked to cut those, say plainly what breaks, and don't.",
            section,
        )


if __name__ == "__main__":
    unittest.main()
