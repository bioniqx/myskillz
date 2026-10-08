import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


SKILL_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "glm-brainstorming"
)
SKILL_MD = os.path.join(SKILL_DIR, "SKILL.md")
EXPLORER_MD = os.path.join(SKILL_DIR, "agents", "glm-explorer.md")
RESEARCHER_MD = os.path.join(SKILL_DIR, "agents", "glm-researcher.md")
BRAINSTORM_MD = os.path.join(SKILL_DIR, "commands", "glm-brainstorm.md")

PLACEHOLDERS = ("[TASK", "[ROOT", "[SLICE", "[ONE precise question]")


def read(path):
    with open(path) as f:
        return f.read()


class TestBrainstormOcSkillMd(unittest.TestCase):
    def setUp(self):
        self.text = read(SKILL_MD)

    def test_changelog_states_fresh_lane_dir_per_run(self):
        changelog = read(os.path.join(os.path.dirname(SKILL_MD), "CHANGELOG.md"))
        entry = changelog.split("# 9.2", 1)[0]
        self.assertIn("fresh dir per run under `.brainstorm/drafts/`", entry)

    def test_line_2_is_still_name_brainstorming(self):
        lines = self.text.split("\n")
        self.assertEqual(lines[1], "name: glm-brainstorming")

    def test_allowed_tools_unchanged(self):
        expected = (
            "allowed-tools:\n"
            '  - Bash(sh "${CLAUDE_SKILL_DIR}/scripts/context.sh")\n'
            "  - Bash(${CLAUDE_SKILL_DIR}/scripts/start-server.sh:*)\n"
            "  - Bash(${CLAUDE_SKILL_DIR}/scripts/stop-server.sh:*)\n"
            "  - Bash(kill -0:*)\n"
            "  - Read\n"
            "  - Grep\n"
            "  - Glob\n"
            "  - WebSearch\n"
            "  - WebFetch\n"
        )
        self.assertIn(expected, self.text)

    def test_preload_line_unchanged(self):
        self.assertIn('!`sh "${CLAUDE_SKILL_DIR}/scripts/context.sh"`', self.text)


def body_of(path):
    text = read(path)
    m = re.match(r"^---\n.*?\n---\n(.*)$", text, re.S)
    assert m, "no frontmatter in " + str(path)
    return m.group(1)


class TestBrainstormLaneAgentBodies(unittest.TestCase):
    def test_explorer_body_has_no_placeholders(self):
        body = body_of(EXPLORER_MD)
        for placeholder in PLACEHOLDERS:
            self.assertNotIn(placeholder, body)

    def test_explorer_body_keeps_output_labels(self):
        body = body_of(EXPLORER_MD)
        self.assertIn("FINDINGS:", body)
        self.assertIn("PATTERNS:", body)
        self.assertIn("RISKS:", body)
        self.assertIn("UNKNOWN:", body)

    def test_researcher_body_has_no_placeholders(self):
        body = body_of(RESEARCHER_MD)
        for placeholder in PLACEHOLDERS:
            self.assertNotIn(placeholder, body)

    def test_researcher_body_keeps_output_labels(self):
        body = body_of(RESEARCHER_MD)
        self.assertIn("ANSWER:", body)
        self.assertIn("CLAIMS:", body)
        self.assertIn("CONFLICTS:", body)
        self.assertIn("VERSION_NOTES:", body)
        self.assertIn("UNVERIFIED:", body)


class TestBrainstormCommandFallback(unittest.TestCase):
    def test_keeps_preload_and_runs_context_sh_when_raw(self):
        text = read(BRAINSTORM_MD)
        preload = "!`sh {{SKILL_DIR}}/scripts/context.sh`"
        self.assertIn(preload, text)
        rest = text.split(preload, 1)[1]
        self.assertIn("raw `!` line", rest)
        self.assertIn("run `sh {{SKILL_DIR}}/scripts/context.sh`", rest)


CONTEXT_SH = os.path.join(SKILL_DIR, "scripts", "context.sh")

def make_skill(root):
    scripts = os.path.join(root, "scripts")
    os.makedirs(scripts)
    shutil.copy(CONTEXT_SH, os.path.join(scripts, "context.sh"))
    return root


def run_context(skill_root, home, extra_env=None):
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": home}
    env.update(extra_env or {})
    return subprocess.run(
        ["sh", os.path.join(skill_root, "scripts", "context.sh")],
        cwd=home,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


class ContextCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.home = os.path.join(self.tmp, "home")
        os.makedirs(self.home)

    def plain_root(self):
        return os.path.join(self.tmp, "plain", "glm-brainstorming")

    def line_starting(self, out, prefix):
        for line in out.splitlines():
            if line.startswith(prefix):
                return line
        self.fail("no %r line in:\n%s" % (prefix, out))


class TestBrainstormContextHarness(ContextCase):
    def test_zcode_install_location_is_detected(self):
        root = make_skill(os.path.join(self.home, ".zcode", "skills", "glm-brainstorming"))
        proc = run_context(root, self.home)
        self.assertEqual(
            self.line_starting(proc.stdout, "harness: "), "harness: zcode"
        )

    def test_copilot_cli_env_marks_the_harness(self):
        root = make_skill(self.plain_root())
        proc = run_context(root, self.home, {"GITHUB_COPILOT_CLI": "1"})
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(
            self.line_starting(proc.stdout, "harness: "), "harness: copilot-cli"
        )

    def test_no_signal_stays_unknown(self):
        root = make_skill(self.plain_root())
        proc = run_context(root, self.home)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(
            self.line_starting(proc.stdout, "harness: "), "harness: unknown"
        )

    def test_context_sh_syntax_is_clean(self):
        proc = subprocess.run(
            ["sh", "-n", CONTEXT_SH], capture_output=True, text=True, timeout=60
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stderr, "")

    def test_claude_code_env_marks_the_harness(self):
        root = make_skill(self.plain_root())
        proc = run_context(root, self.home, {"CLAUDECODE": "1"})
        self.assertEqual(
            self.line_starting(proc.stdout, "harness: "), "harness: claude-code"
        )


class TestBrainstormContextCaps(ContextCase):
    def test_zcode_caps_default_width_is_8(self):
        root = make_skill(os.path.join(self.home, ".zcode", "skills", "glm-brainstorming"))
        proc = run_context(root, self.home)
        caps = self.line_starting(proc.stdout, "caps: ")
        self.assertIn("lanes=8", caps)
        self.assertNotIn("subagents=", caps)

    def test_zcode_caps_honour_oc_max_lanes(self):
        root = make_skill(os.path.join(self.home, ".zcode", "skills", "glm-brainstorming"))
        proc = run_context(root, self.home, {"OC_MAX_LANES": "4"})
        self.assertIn("lanes=4", self.line_starting(proc.stdout, "caps: "))

    def test_zcode_caps_clamp_to_8(self):
        root = make_skill(os.path.join(self.home, ".zcode", "skills", "glm-brainstorming"))
        proc = run_context(root, self.home, {"OC_MAX_LANES": "64"})
        self.assertIn("lanes=8", self.line_starting(proc.stdout, "caps: "))

    def test_zcode_caps_edge_values(self):
        root = make_skill(os.path.join(self.home, ".zcode", "skills", "glm-brainstorming"))
        for val, want in (("0", "lanes=1"), ("abc", "lanes=8"), ("", "lanes=8"), ("8", "lanes=8")):
            proc = run_context(root, self.home, {"OC_MAX_LANES": val})
            self.assertIn(want, self.line_starting(proc.stdout, "caps: "), val)

    def test_claude_caps_default_8(self):
        root = make_skill(self.plain_root())
        proc = run_context(root, self.home, {"CLAUDECODE": "1"})
        self.assertIn("subagents=8", self.line_starting(proc.stdout, "caps: "))

    def test_claude_caps_clamped_to_8(self):
        root = make_skill(self.plain_root())
        env = {"CLAUDECODE": "1", "CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS": "64",
               "CLAUDE_CODE_WORKFLOW_MAX_CONCURRENT_AGENTS": "16"}
        caps = self.line_starting(run_context(root, self.home, env).stdout, "caps: ")
        self.assertIn("subagents=8", caps)
        self.assertIn("workflow=8", caps)

    def test_output_is_bounded_and_exits_zero(self):
        root = make_skill(self.plain_root())
        proc = run_context(root, self.home)
        self.assertEqual(proc.returncode, 0)
        self.assertLessEqual(len(proc.stdout.splitlines()), 55)


import os
import shutil
import subprocess
import tempfile
import unittest


class ZcodeSurfaceTests(unittest.TestCase):
    """The zcode surface: the context.sh harness branch and the harness-scoped skill docs."""

    SKILL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "glm-brainstorming")

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.home = self._tmp.name

    def read(self, *parts):
        with open(os.path.join(self.SKILL, *parts), encoding="utf-8") as fh:
            return fh.read()

    @staticmethod
    def flat(text):
        return " ".join(text.split())

    @staticmethod
    def prose_lines(text):
        out, fence = [], False
        for line in text.splitlines():
            if line.lstrip().startswith("```"):
                fence = not fence
            elif not fence:
                out.append(line)
        return out

    def setup_skill(self, rel_scripts):
        """Copy context.sh into a fake skill dir under HOME; return the script path."""
        scripts = os.path.join(self.home, rel_scripts)
        os.makedirs(scripts)
        shutil.copy(os.path.join(self.SKILL, "scripts", "context.sh"),
                    os.path.join(scripts, "context.sh"))
        return os.path.join(scripts, "context.sh")

    def run_script(self, script, env_extra=None):
        env = {"HOME": self.home, "PATH": os.environ.get("PATH", "/usr/bin:/bin")}
        env.update(env_extra or {})
        return subprocess.run(["sh", script],
                              capture_output=True, text=True, timeout=60, env=env)

    def run_context(self, rel_scripts, env_extra=None):
        return self.run_script(self.setup_skill(rel_scripts), env_extra)

    def home_files(self):
        found = set()
        for root, _dirs, files in os.walk(self.home):
            for name in files:
                found.add(os.path.join(root, name))
        return found

    def test_context_sh_detects_zcode_with_width_cap_8(self):
        r = self.run_context(".zcode/skills/glm-brainstorming/scripts")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("harness: zcode", r.stdout)
        self.assertIn("caps: lanes=8 (default 8, hard max 8)", r.stdout)
        self.assertNotIn("subagents=", r.stdout)
        self.assertNotIn("workflow=", r.stdout)

    def test_context_sh_zcode_path_arm_outranks_opencode_path_arm(self):
        r = self.run_context("opencode/x/.zcode/skills/glm-brainstorming/scripts")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("harness: zcode", r.stdout)
        self.assertIn("caps: lanes=8 (default 8, hard max 8)", r.stdout)
        self.assertNotIn("harness: opencode", r.stdout)

    def test_context_sh_zcode_outranks_when_home_sits_under_opencode_dir(self):
        self.home = os.path.join(self._tmp.name, "opencode")
        os.makedirs(self.home)
        r = self.run_context(".zcode/skills/glm-brainstorming/scripts")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("harness: zcode", r.stdout)
        self.assertIn("caps: lanes=8 (default 8, hard max 8)", r.stdout)

    def test_context_sh_claude_code_caps_still_printed(self):
        r = self.run_context("plain/scripts", {"CLAUDECODE": "1"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("harness: claude-code", r.stdout)
        self.assertIn("subagents=8", r.stdout)
        self.assertIn("workflow=8", r.stdout)

    def test_context_sh_zcode_run_is_read_only_bounded_and_exits_zero(self):
        script = self.setup_skill(".zcode/skills/glm-brainstorming/scripts")
        before = self.home_files()
        r = self.run_script(script)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertLessEqual(len(r.stdout.splitlines()), 55)
        self.assertEqual(self.home_files() - before, set(),
                         "context.sh must not write anything under HOME")

    def test_skill_md_zcode_surface(self):
        text = self.read("SKILL.md")
        lines = self.prose_lines(text)
        self.assertIn("~/.zcode/skills/glm-brainstorming", self.flat(text))
        self.assertTrue(any("TaskCreate" in ln and "TodoWrite" in ln for ln in lines),
                        "the TaskCreate fallback row must name TodoWrite")
        self.assertTrue(any("AskUserQuestion" in ln and "ZCode" in ln for ln in lines),
                        "the AskUserQuestion fallback row must name ZCode")
        self.assertTrue(any("Workflow" in ln and "Claude Code" in ln for ln in lines),
                        "Workflow facts must be scoped to Claude Code")
        for ln in lines:
            if "CLAUDE_CODE_" in ln:
                self.assertIn("Claude Code", ln, ln)
        # ZCode-only surface: no OpenCode harness instructions remain.
        self.assertNotIn("OpenCode", self.flat(text))
        self.assertNotIn("oc_harness", self.flat(text))
        self.assertNotIn("todowrite", self.flat(text))
        self.assertNotIn("webfetch", self.flat(text))

    def test_fanout_playbook_scopes_claude_code_facts_and_covers_zcode(self):
        text = self.read("fanout-playbook.md")
        for ln in self.prose_lines(text):
            if "CLAUDE_CODE_" in ln or "Workflow" in ln:
                self.assertIn("Claude Code", ln, ln)
        self.assertIn("SendMessage` exists (Claude-Code-compatible)", self.flat(text))
        self.assertNotIn("On ZCode no continue tool is documented", self.flat(text))

    def test_architectural_taskstop_note_covers_zcode(self):
        self.assertIn("TaskStop` exists (Claude-Code-compatible)",
                      self.flat(self.read("architectural.md")))
        self.assertNotIn("On ZCode no stop tool is documented",
                         self.flat(self.read("architectural.md")))

    def test_visual_companion_platform_notes_gain_zcode(self):
        self.assertIn("ZCode — no ZCode-specific server behavior is documented",
                      self.flat(self.read("visual-companion.md")))

    def test_glm_tuning_gains_zcode_runtime_section(self):
        flat = self.flat(self.read("glm-tuning.md"))
        self.assertIn("ZCode runtime", flat)
        self.assertIn("NEW ZCode session", flat)
        self.assertIn("no `!` preload support", flat)

    def test_changelog_records_the_zcode_surface(self):
        text = self.read("CHANGELOG.md")
        self.assertIn("9.4 (from 9.3)", text)
        self.assertLess(text.find("9.4 (from 9.3)"), text.find("9.3 (from 9.2)"))


if __name__ == "__main__":
    unittest.main()
