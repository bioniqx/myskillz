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
    os.path.dirname(__file__), "..", "..", "oc-brainstorming"
)
SKILL_MD = os.path.join(SKILL_DIR, "SKILL.md")
EXPLORER_MD = os.path.join(SKILL_DIR, "opencode", "agents", "oc-explorer.md")
RESEARCHER_MD = os.path.join(SKILL_DIR, "opencode", "agents", "oc-researcher.md")
BRAINSTORM_MD = os.path.join(SKILL_DIR, "opencode", "commands", "oc-brainstorm.md")
CONTEXT_SH = os.path.join(SKILL_DIR, "scripts", "oc-context.sh")

DOCS = [SKILL_MD, EXPLORER_MD, RESEARCHER_MD, BRAINSTORM_MD] + [
    os.path.join(SKILL_DIR, name)
    for name in (
        "fanout-playbook.md",
        "research-playbook.md",
        "architectural.md",
        "visual-companion.md",
        "spec-document-reviewer-prompt.md",
    )
]

BANNED = re.compile(
    r"reasoning|effort|lanes\.json|oc_harness|general-purpose|\bExplore\b|AskUserQuestion"
    r"|ToolSearch|TaskCreate|TaskStop|SendMessage|todowrite|WebSearch|WebFetch"
    r"|\bWorkflow\b|\bAgent\b|(?<!/)\bv1\b|\.oc-major|allowed-tools|when_to_use"
)

PLACEHOLDERS = ("[TASK", "[ROOT", "[SLICE", "[ONE precise question]")


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def split_doc(text):
    match = re.match(r"---\n(.*?)\n---\n(.*)", text, re.S)
    assert match, "no frontmatter"
    return match.group(1), match.group(2)


def top_keys(front):
    return re.findall(r"^([A-Za-z_-]+):", front, re.M)


def description(front):
    value = re.search(r"^description: (.*)$", front, re.M).group(1)
    return json.loads(value) if value.startswith('"') else value


def line_starting(test, out, prefix):
    for line in out.splitlines():
        if line.startswith(prefix):
            return line
    test.fail("no %r line in:\n%s" % (prefix, out))


class TestSkillMd(unittest.TestCase):
    def setUp(self):
        self.text = read(SKILL_MD)
        self.front, self.body = split_doc(self.text)

    def test_frontmatter_has_only_name_description_metadata(self):
        self.assertEqual(top_keys(self.front), ["name", "description", "metadata"])

    def test_name_is_brainstorming(self):
        self.assertEqual(self.text.split("\n")[1], "name: oc-brainstorming")

    def test_description_fits_and_carries_the_triggers(self):
        desc = description(self.front)
        self.assertLessEqual(len(desc), 1024)
        self.assertIn("You MUST use this before any creative work", desc)
        self.assertIn("build/add/implement X", desc)

    def test_no_preload_line(self):
        self.assertIsNone(re.search(r"^!`", self.text, re.M))

    def test_single_bootstrap_call(self):
        self.assertIn("sh <Base directory>/scripts/oc-context.sh", self.text)

    def test_rules_r0_to_r12_present(self):
        for n in range(13):
            self.assertRegex(self.text, r"(?m)^## R%d " % n)

    def test_lane_dispatch_uses_background_subagent(self):
        for needle in (
            'agent: "oc-explorer"',
            'agent: "oc-researcher"',
            "`general`",
            "background: true",
        ):
            self.assertIn(needle, self.text)

    def test_names_v2_tools(self):
        for tool in ("subagent", "question", "websearch", "webfetch", "shell"):
            self.assertIn("`%s`" % tool, self.text)

    def test_lane_brief_fields(self):
        for field in ("Task:", "Slice:", "Siblings cover", "Question:", "Angle:"):
            self.assertIn(field, self.text)


class TestDocsClean(unittest.TestCase):
    def test_no_stale_terms(self):
        for path in DOCS:
            match = BANNED.search(read(path))
            self.assertIsNone(
                match, "%s: %r" % (os.path.basename(path), match and match.group(0))
            )

    def test_referenced_markdown_files_exist(self):
        for path in DOCS:
            for name in re.findall(r"`([a-z][a-z-]*\.md)`", read(path)):
                self.assertTrue(
                    os.path.exists(os.path.join(SKILL_DIR, name)),
                    "%s references missing %s" % (os.path.basename(path), name),
                )


class TestAgents(unittest.TestCase):
    def check_agent(self, path, labels):
        front, body = split_doc(read(path))
        self.assertEqual(
            sorted(top_keys(front)), ["access", "bash", "description", "steps", "web"]
        )
        for placeholder in PLACEHOLDERS:
            self.assertNotIn(placeholder, body)
        for label in labels:
            self.assertIn(label, body)
        rendered = oc_harness.render_agent(read(path), 2)
        self.assertIsNone(
            re.search(r"(?m)^(model|variant|effort|reasoningEffort):", rendered)
        )
        match = re.search(r'description: (".*")', rendered)
        self.assertIsNotNone(match)
        value = json.loads(match.group(1))
        self.assertRegex(value, r"^[A-Za-z]")
        self.assertFalse(value.startswith('\\"'))

    def test_explorer(self):
        self.check_agent(
            EXPLORER_MD, ("FINDINGS:", "PATTERNS:", "RISKS:", "UNKNOWN:")
        )

    def test_researcher(self):
        self.check_agent(
            RESEARCHER_MD,
            ("ANSWER:", "CLAIMS:", "CONFLICTS:", "VERSION_NOTES:", "UNVERIFIED:"),
        )


class TestBrainstormCommand(unittest.TestCase):
    def setUp(self):
        self.text = read(BRAINSTORM_MD)
        self.front, self.body = split_doc(self.text)

    def test_frontmatter_is_description_only(self):
        self.assertEqual(top_keys(self.front), ["description"])
        self.assertRegex(description(self.front), r"^[A-Za-z]")

    def test_runs_context_script_itself(self):
        self.assertIsNone(re.search(r"(?m)^!`", self.text))
        self.assertIn("Run `sh {{SKILL_DIR}}/scripts/oc-context.sh`", self.body)

    def test_loads_skill_with_arguments(self):
        self.assertIn("Load skill oc-brainstorming with $ARGUMENTS.", self.body)


class ContextCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.home = os.path.join(self.tmp, "home")
        self.proj = os.path.join(self.tmp, "proj")
        os.makedirs(self.home)
        os.makedirs(self.proj)

    def run_context(self, extra_env=None):
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": self.home}
        env.update(extra_env or {})
        return subprocess.run(
            ["sh", CONTEXT_SH],
            cwd=self.proj,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )


class TestBrainstormContext(ContextCase):
    def test_syntax_is_clean(self):
        proc = subprocess.run(
            ["sh", "-n", CONTEXT_SH], capture_output=True, text=True, timeout=60
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stderr, "")

    def test_prints_opencode_facts_only(self):
        proc = self.run_context()
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(
            line_starting(self, proc.stdout, "harness: "),
            "harness: opencode oc_major=2",
        )
        for stale in ("route:", "models:", "subagents="):
            self.assertNotIn(stale, proc.stdout)

    def test_caps_default_width_is_8(self):
        proc = self.run_context()
        caps = line_starting(self, proc.stdout, "caps: ")
        self.assertIn("lanes=8", caps)
        self.assertIn("OC_MAX_LANES", caps)

    def test_caps_honours_oc_max_lanes(self):
        proc = self.run_context({"OC_MAX_LANES": "4"})
        self.assertIn("lanes=4", line_starting(self, proc.stdout, "caps: "))

    def test_lists_agents_md(self):
        with open(os.path.join(self.proj, "AGENTS.md"), "w") as f:
            f.write("rules\n")
        proc = self.run_context()
        self.assertIn("AGENTS.md", line_starting(self, proc.stdout, "docs: "))

    def test_bare_directory_is_bounded_and_exits_zero(self):
        proc = self.run_context()
        self.assertEqual(proc.returncode, 0)
        self.assertLessEqual(len(proc.stdout.splitlines()), 55)

    def test_git_repo_output_is_bounded_and_lists_dependencies(self):
        with open(os.path.join(self.proj, "package.json"), "w") as f:
            f.write('{\n  "dependencies": {\n    "left-pad": "1.3.0"\n  }\n}\n')
        git = ["git", "-c", "user.name=t", "-c", "user.email=t@example.com"]
        for args in (["init", "-q"], ["add", "package.json"], ["commit", "-q", "-m", "init"]):
            subprocess.run(
                git + args,
                cwd=self.proj,
                env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": self.home},
                check=True,
                capture_output=True,
            )
        proc = self.run_context()
        self.assertEqual(proc.returncode, 0)
        self.assertLessEqual(len(proc.stdout.splitlines()), 55)
        self.assertIn("root=", line_starting(self, proc.stdout, "git: "))
        self.assertIn("left-pad", line_starting(self, proc.stdout, "npm_deps: "))


if __name__ == "__main__":
    unittest.main()
