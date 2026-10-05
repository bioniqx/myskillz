import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import oc_harness

SKILL_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "brainstorming-glm"
)
SKILL_MD = os.path.join(SKILL_DIR, "SKILL.md")
EXPLORER_MD = os.path.join(SKILL_DIR, "opencode", "agents", "explorer.md")
RESEARCHER_MD = os.path.join(SKILL_DIR, "opencode", "agents", "researcher.md")
BRAINSTORM_MD = os.path.join(SKILL_DIR, "opencode", "commands", "brainstorm.md")

PLACEHOLDERS = ("[TASK", "[ROOT", "[SLICE", "[ONE precise question]")


def read(path):
    with open(path) as f:
        return f.read()


class TestBrainstormOcSkillMd(unittest.TestCase):
    def setUp(self):
        self.text = read(SKILL_MD)

    def test_gives_exact_run_command(self):
        self.assertIn(
            'python3 "$H/oc_harness.py" run .brainstorm/drafts/lanes.json --out "$OUT"',
            self.text,
        )

    def test_resolver_checks_for_oc_harness_script(self):
        self.assertIn("scripts/oc_harness.py", self.text)

    def test_gives_lane_fields(self):
        for field in ("id", "agent", "model", "dir", "brief"):
            self.assertIn("`%s`" % field, self.text)

    def _opencode_lane_section(self):
        start = self.text.find("Running `oc_harness.py run`")
        self.assertNotEqual(start, -1, "OpenCode run section not found")
        end = self.text.find("## Visual companion", start)
        self.assertNotEqual(end, -1, "OpenCode lane section end marker not found")
        return self.text[start:end]

    def test_states_what_brief_contains(self):
        section = self._opencode_lane_section()
        self.assertIn("brief", section.lower())
        self.assertIn("task", section.lower())
        self.assertIn("question", section.lower())

    def test_states_where_and_how_lane_output_is_read(self):
        section = self._opencode_lane_section()
        self.assertIn('python3 "$H/oc_harness.py" result "$OUT"', section)
        self.assertIn("python3 oc_harness.py result OUT_DIR", section)
        self.assertIn(".jsonl", section)
        self.assertIn("--out", section)

    def test_resolver_guards_empty_h(self):
        section = self._opencode_lane_section()
        self.assertIn('[ -n "$H" ]', section)
        self.assertIn("not found", section.lower())

    def test_run_command_uses_temp_out_dir(self):
        section = self._opencode_lane_section()
        self.assertNotIn('OUT=".brainstorm/drafts/lanes"', section)
        self.assertIn('OUT="$(mktemp -d .brainstorm/drafts/lanes.XXXXXX)"', section)
        self.assertIn("mkdir -p .brainstorm/drafts", section)
        self.assertIn('--out "$OUT"', section)

    def test_run_section_uses_lanes_json_and_result(self):
        section = self._opencode_lane_section()
        self.assertIn(
            'python3 "$H/oc_harness.py" run .brainstorm/drafts/lanes.json --out "$OUT"',
            section,
        )
        self.assertIn('python3 "$H/oc_harness.py" result "$OUT"', section)

    def test_changelog_states_fresh_lane_dir_per_run(self):
        changelog = read(os.path.join(os.path.dirname(SKILL_MD), "CHANGELOG.md"))
        entry = changelog.split("# 9.2-glm", 1)[0]
        self.assertIn("fresh dir per run under `.brainstorm/drafts/`", entry)

    def test_states_task_tool_is_only_fallback(self):
        idx = self.text.find("`task`")
        self.assertNotEqual(idx, -1, "no `task` mention found")
        window = self.text[max(0, idx - 200):idx + 200]
        self.assertIn("fallback", window.lower())
        self.assertIn("unavailable", window.lower())

    def test_line_2_is_still_name_brainstorming(self):
        lines = self.text.split("\n")
        self.assertEqual(lines[1], "name: brainstorming")

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


class TestBrainstormOcAgentBodies(unittest.TestCase):
    def test_explorer_body_has_no_placeholders(self):
        text = read(EXPLORER_MD)
        _, body = oc_harness.parse_frontmatter(text)
        for placeholder in PLACEHOLDERS:
            self.assertNotIn(placeholder, body)

    def test_explorer_body_keeps_output_labels(self):
        text = read(EXPLORER_MD)
        _, body = oc_harness.parse_frontmatter(text)
        self.assertIn("FINDINGS:", body)
        self.assertIn("PATTERNS:", body)
        self.assertIn("RISKS:", body)
        self.assertIn("UNKNOWN:", body)

    def test_researcher_body_has_no_placeholders(self):
        text = read(RESEARCHER_MD)
        _, body = oc_harness.parse_frontmatter(text)
        for placeholder in PLACEHOLDERS:
            self.assertNotIn(placeholder, body)

    def test_researcher_body_keeps_output_labels(self):
        text = read(RESEARCHER_MD)
        _, body = oc_harness.parse_frontmatter(text)
        self.assertIn("ANSWER:", body)
        self.assertIn("CLAIMS:", body)
        self.assertIn("CONFLICTS:", body)
        self.assertIn("VERSION_NOTES:", body)
        self.assertIn("UNVERIFIED:", body)


class TestBrainstormOcRenderedDescriptions(unittest.TestCase):
    def test_explorer_rendered_description_starts_with_letter(self):
        rendered = oc_harness.render_agent(read(EXPLORER_MD), 2)
        match = re.search(r'description: (".*")', rendered)
        self.assertIsNotNone(match)
        value = json.loads(match.group(1))
        self.assertRegex(value, r"^[A-Za-z]")
        self.assertFalse(value.startswith('\\"'))

    def test_researcher_rendered_description_starts_with_letter(self):
        rendered = oc_harness.render_agent(read(RESEARCHER_MD), 2)
        match = re.search(r'description: (".*")', rendered)
        self.assertIsNotNone(match)
        value = json.loads(match.group(1))
        self.assertRegex(value, r"^[A-Za-z]")
        self.assertFalse(value.startswith('\\"'))

    def test_brainstorm_command_rendered_description_starts_with_letter(self):
        rendered = oc_harness.render_command(read(BRAINSTORM_MD), 2, "/tmp/skill")
        match = re.search(r'description: (".*")', rendered)
        self.assertIsNotNone(match)
        value = json.loads(match.group(1))
        self.assertRegex(value, r"^[A-Za-z]")
        self.assertFalse(value.startswith('\\"'))


class TestBrainstormCommandFallback(unittest.TestCase):
    def test_keeps_preload_and_runs_context_sh_when_raw(self):
        text = read(BRAINSTORM_MD)
        preload = "!`sh {{SKILL_DIR}}/scripts/context.sh`"
        self.assertIn(preload, text)
        rest = text.split(preload, 1)[1]
        self.assertIn("raw `!` line", rest)
        self.assertIn("run `sh {{SKILL_DIR}}/scripts/context.sh`", rest)


CONTEXT_SH = os.path.join(SKILL_DIR, "scripts", "context.sh")

FAKE_CLI = (
    "import sys\n"
    "with open(__file__ + '.args', 'w') as f:\n"
    "    f.write(' '.join(sys.argv[1:]))\n"
    "sys.stdout.write(%r)\n"
    "sys.exit(%d)\n"
)


def make_skill(root, cli_output=None, cli_exit=0, oc_major=None):
    scripts = os.path.join(root, "scripts")
    os.makedirs(scripts)
    shutil.copy(CONTEXT_SH, os.path.join(scripts, "context.sh"))
    if cli_output is not None:
        with open(os.path.join(scripts, "oc_harness.py"), "w") as f:
            f.write(FAKE_CLI % (cli_output, cli_exit))
    if oc_major is not None:
        with open(os.path.join(root, ".oc-major"), "w") as f:
            f.write(oc_major)
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
        return os.path.join(self.tmp, "plain", "brainstorming")

    def line_starting(self, out, prefix):
        for line in out.splitlines():
            if line.startswith(prefix):
                return line
        self.fail("no %r line in:\n%s" % (prefix, out))


class TestBrainstormContextHarness(ContextCase):
    def test_cli_result_sets_harness_and_major(self):
        root = make_skill(self.plain_root(), cli_output="opencode 2\n")
        proc = run_context(root, self.home)
        self.assertEqual(
            self.line_starting(proc.stdout, "harness: "),
            "harness: opencode oc_major=2",
        )

    def test_cli_receives_harness_subcommand_and_script(self):
        root = make_skill(self.plain_root(), cli_output="opencode 2\n")
        run_context(root, self.home)
        with open(os.path.join(root, "scripts", "oc_harness.py.args")) as f:
            args = f.read()
        self.assertTrue(args.startswith("harness --script "), args)
        self.assertTrue(args.endswith("/scripts/context.sh"), args)

    def test_opencode_terminal_env_without_cli(self):
        root = make_skill(self.plain_root())
        proc = run_context(root, self.home, {"OPENCODE_TERMINAL": "1"})
        self.assertEqual(
            self.line_starting(proc.stdout, "harness: "),
            "harness: opencode oc_major=unknown",
        )

    def test_oc_major_file_without_cli(self):
        root = make_skill(self.plain_root(), oc_major="1\n")
        proc = run_context(root, self.home)
        self.assertEqual(
            self.line_starting(proc.stdout, "harness: "),
            "harness: opencode oc_major=1",
        )

    def test_install_location_without_cli(self):
        root = make_skill(
            os.path.join(self.home, ".config", "opencode", "skills", "brainstorming")
        )
        proc = run_context(root, self.home)
        self.assertEqual(
            self.line_starting(proc.stdout, "harness: "),
            "harness: opencode oc_major=unknown",
        )

    def test_failing_cli_falls_back_to_sh_mirror(self):
        root = make_skill(self.plain_root(), cli_output="", cli_exit=1)
        proc = run_context(root, self.home, {"OPENCODE_TERMINAL": "1"})
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(
            self.line_starting(proc.stdout, "harness: "),
            "harness: opencode oc_major=unknown",
        )

    def test_cli_unknown_without_signals_stays_unknown(self):
        root = make_skill(self.plain_root(), cli_output="unknown 0\n")
        proc = run_context(root, self.home)
        self.assertEqual(
            self.line_starting(proc.stdout, "harness: "), "harness: unknown"
        )

    def test_cli_claude_answer_keeps_sh_chain_result(self):
        root = make_skill(self.plain_root(), cli_output="claude 0\n")
        proc = run_context(root, self.home, {"GITHUB_COPILOT_CLI": "1"})
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(
            self.line_starting(proc.stdout, "harness: "), "harness: copilot-cli"
        )

    def test_cli_claude_answer_without_signals_stays_unknown(self):
        root = make_skill(self.plain_root(), cli_output="claude 0\n")
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

    def test_claude_code_env_wins_over_cli(self):
        root = make_skill(self.plain_root(), cli_output="opencode 2\n")
        proc = run_context(root, self.home, {"CLAUDECODE": "1"})
        self.assertEqual(
            self.line_starting(proc.stdout, "harness: "), "harness: claude-code"
        )


class TestBrainstormContextCaps(ContextCase):
    def test_opencode_caps_default_width_is_6(self):
        root = make_skill(self.plain_root())
        proc = run_context(root, self.home, {"OPENCODE_TERMINAL": "1"})
        caps = self.line_starting(proc.stdout, "caps: ")
        self.assertIn("lanes=6", caps)
        self.assertIn("--width", caps)
        self.assertNotIn("subagents=", caps)

    def test_opencode_caps_honours_oc_max_lanes(self):
        root = make_skill(self.plain_root())
        proc = run_context(
            root, self.home, {"OPENCODE_TERMINAL": "1", "OC_MAX_LANES": "4"}
        )
        self.assertIn("lanes=4", self.line_starting(proc.stdout, "caps: "))

    def test_opencode_caps_clamps_oc_max_lanes_to_8(self):
        root = make_skill(self.plain_root(), oc_major="2\n")
        proc = run_context(
            root, self.home, {"OPENCODE_TERMINAL": "1", "OC_MAX_LANES": "64"}
        )
        self.assertIn("lanes=8", self.line_starting(proc.stdout, "caps: "))

    def test_opencode_caps_oc_max_lanes_edge_values(self):
        root = make_skill(self.plain_root())
        for val, want in (("0", "lanes=1"), ("abc", "lanes=6"), ("", "lanes=6"), ("8", "lanes=8")):
            proc = run_context(
                root, self.home, {"OPENCODE_TERMINAL": "1", "OC_MAX_LANES": val}
            )
            self.assertIn(want, self.line_starting(proc.stdout, "caps: "), val)

    def test_opencode_caps_prints_oc_major(self):
        root = make_skill(self.plain_root(), oc_major="2\n")
        proc = run_context(root, self.home)
        self.assertIn("oc_major=2", self.line_starting(proc.stdout, "caps: "))

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

    def test_opencode_output_is_bounded_and_exits_zero(self):
        root = make_skill(self.plain_root(), oc_major="2\n")
        proc = run_context(root, self.home, {"OPENCODE_TERMINAL": "1"})
        self.assertEqual(proc.returncode, 0)
        self.assertLessEqual(len(proc.stdout.splitlines()), 55)


if __name__ == "__main__":
    unittest.main()
