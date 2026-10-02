"""Black-box tests for claude-writing-plans-6.2/scripts/plan_tool.py lint (slice K13).

Covers: W8-2 (fence-aware heading check), W8-3 (portability scan skips fenced/
backticked text and URLs; TODO/TBD/FIXME/XXX are case-sensitive), W8-4
(files_block accepts bare filenames like Makefile and ignores a second
backtick span on a Files line), W8-5 (a chained `git add a b && git commit`
step is not flagged), W8-9 (the spec heading map ignores '#' lines inside
code fences).

Runs the real script against throwaway git repos built under the system
temp dir. Never touches the real ~/.claude or this repo's own state.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(TESTS_DIR)  # claude-skills/
WP_DIR = os.path.join(BASE_DIR, "claude-writing-plans-6.2")
TOOL = os.path.join(WP_DIR, "scripts", "plan_tool.py")


def run_tool(args, cwd, env=None, timeout=25):
    e = dict(os.environ)
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    if env:
        e.update(env)
    return subprocess.run(
        [sys.executable, TOOL] + list(args),
        cwd=cwd, env=e, capture_output=True, text=True, timeout=timeout,
    )


def make_repo():
    d = os.path.realpath(tempfile.mkdtemp())
    subprocess.run(["git", "init", "-q"], cwd=d, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=d, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=d, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=d, check=True)
    with open(os.path.join(d, "README.md"), "w") as f:
        f.write("seed\n")
    subprocess.run(["git", "add", "-A"], cwd=d, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=d, check=True)
    return d


def write_plan(repo, contracts_md, name="plan.md"):
    plan = os.path.join(repo, name)
    with open(plan, "w") as f:
        f.write("# P\n\n## Contracts\n\n" + contracts_md)
    return plan


def write_task(repo, body, tid="T01"):
    task = os.path.join(repo, tid + ".md")
    with open(task, "w") as f:
        f.write(body)
    return task


def base_body(extra_mid="", tail=""):
    """A minimally valid T01 task body: Files -> one file, one step, one
    python code block, a git commit mention. extra_mid is inserted right
    after the Files list; tail is appended at the very end."""
    parts = ["**Files:**", "- Modify: `demo.py`", ""]
    if extra_mid:
        parts += [extra_mid, ""]
    parts += ["- [ ] **Step 1: implement**", "", "```python", "x = 1", "```", "",
              "Then `git commit -m \"feat\"`.", ""]
    if tail:
        parts.append(tail)
    return "\n".join(parts) + "\n"


class HeadingFenceAwareTests(unittest.TestCase):
    """W8-2: '#'/'##'/'###' lines inside code fences don't break the plan-structure check."""

    def setUp(self):
        self.repo = make_repo()
        self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)

    def test_hashes_inside_python_bash_markdown_fences_pass(self):
        plan = write_plan(self.repo, "#### T01: Demo\n- Files: `demo.py`\n\n")
        body = (
            "**Files:**\n- Modify: `demo.py`\n\n"
            "```python\n# comment\nx = 1\n```\n\n"
            "```bash\n# comment\necho hi\n```\n\n"
            "```markdown\n# Title\nsome text\n```\n\n"
            "- [ ] **Step 1: implement**\n\n"
            "Then `git commit -m \"feat\"`.\n"
        )
        task = write_task(self.repo, body)
        p = run_tool(["lint-task", plan, task], cwd=self.repo)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_single_hash_task_id_comments_inside_code_fences_pass(self):
        plan = write_plan(self.repo, "#### T01: Demo\n- Files: `demo.py`\n\n")
        body = base_body(extra_mid="```python\n# T05: note\nz = 2\n```\n\n```bash\n# T05: note\necho hi\n```")
        task = write_task(self.repo, body)
        p = run_tool(["lint-task", plan, task], cwd=self.repo)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_bare_task_heading_anywhere_in_body_still_fails(self):
        plan = write_plan(self.repo, "#### T01: Demo\n- Files: `demo.py`\n\n")
        body = base_body(extra_mid="### T05: sneaky heading")
        task = write_task(self.repo, body)
        p = run_tool(["lint-task", plan, task], cwd=self.repo)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("heading inside a task body breaks plan structure", p.stdout)

    def test_task_heading_inside_closed_markdown_fence_still_fails(self):
        plan = write_plan(self.repo, "#### T01: Demo\n- Files: `demo.py`\n\n")
        body = base_body(extra_mid="```markdown\n### T05: x\n```")
        task = write_task(self.repo, body)
        p = run_tool(["lint-task", plan, task], cwd=self.repo)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("heading inside a task body breaks plan structure", p.stdout)

    def test_tilde_fence_hash_is_ignored(self):
        plan = write_plan(self.repo, "#### T01: Demo\n- Files: `demo.py`\n\n")
        body = base_body(extra_mid="~~~python\n# comment\ny = 1\n~~~")
        task = write_task(self.repo, body)
        p = run_tool(["lint-task", plan, task], cwd=self.repo)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_nested_longer_fence_hash_is_ignored(self):
        plan = write_plan(self.repo, "#### T01: Demo\n- Files: `demo.py`\n\n")
        inner = "````text\nExample:\n```\n# fake heading between fences\n```\nstill same block\n````"
        body = base_body(extra_mid=inner)
        task = write_task(self.repo, body)
        p = run_tool(["lint-task", plan, task], cwd=self.repo)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_unterminated_fence_does_not_crash_and_still_flags_task_heading(self):
        plan = write_plan(self.repo, "#### T01: Demo\n- Files: `demo.py`\n\n")
        body = (
            "**Files:**\n- Modify: `demo.py`\n\n"
            "```python\nx = 1\n```\n\n"
            "- [ ] **Step 1: implement**\n\n"
            "Then `git commit -m \"feat\"`.\n\n"
            "```text\n### T05: fake heading trapped in unterminated fence\n"
        )
        task = write_task(self.repo, body)
        p = run_tool(["lint-task", plan, task], cwd=self.repo)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("unbalanced code fence", p.stdout)
        self.assertIn("heading inside a task body breaks plan structure", p.stdout)
        self.assertEqual(p.stderr.strip(), "", p.stderr)


class PortabilityScanTests(unittest.TestCase):
    """W8-3: scan ignores fenced/backticked text and URLs; TODO/TBD/FIXME/XXX are case-sensitive."""

    def setUp(self):
        self.repo = make_repo()
        self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)

    def test_backticked_and_url_mentions_are_exempt_but_prose_is_flagged(self):
        plan = write_plan(self.repo, "#### T01: Demo\n- Files: `demo.py`\n\n")
        para = (
            "Config uses `CLAUDE.md`, `.claude/state`, `import anthropic`, and "
            "`docs/superpowers/specs/2024-01-01-thing.md`, see https://example.com/Claude for reference.\n\n"
            "This relies on Claude to plan the steps.\n"
        )
        body = base_body(extra_mid=para)
        task = write_task(self.repo, body)
        p = run_tool(["lint-task", plan, task], cwd=self.repo)
        self.assertNotEqual(p.returncode, 0)
        self.assertNotIn("CLAUDE.md", p.stdout)
        self.assertNotIn(".claude/state", p.stdout)
        self.assertNotIn("anthropic", p.stdout.lower())
        self.assertNotIn("superpowers", p.stdout)
        self.assertIn("'Claude'", p.stdout)

    def test_placeholder_inside_python_fence_fails(self):
        plan = write_plan(self.repo, "#### T01: Demo\n- Files: `demo.py`\n\n")
        body = base_body(extra_mid="```python\n# TODO: implement later\ny = 2\n```")
        task = write_task(self.repo, body)
        p = run_tool(["lint-task", plan, task], cwd=self.repo)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("placeholder", p.stdout)
        self.assertIn("'TODO'", p.stdout)

    def test_plain_comment_fence_and_backticked_claude_md_pass(self):
        plan = write_plan(self.repo, "#### T01: Demo\n- Files: `demo.py`\n\n")
        body = base_body(extra_mid="See `CLAUDE.md`.\n\n```python\n# comment\ny = 2\n```")
        task = write_task(self.repo, body)
        p = run_tool(["lint-task", plan, task], cwd=self.repo)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_portability_words_inside_fence_are_still_skipped(self):
        plan = write_plan(self.repo, "#### T01: Demo\n- Files: `demo.py`\n\n")
        body = base_body(extra_mid="```text\nAsk Claude via https://example.com/Claude\n```")
        task = write_task(self.repo, body)
        p = run_tool(["lint-task", plan, task], cwd=self.repo)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_todo_tbd_fixme_xxx_are_case_sensitive(self):
        plan = write_plan(self.repo, "#### T01: Demo\n- Files: `demo.py`\n\n")
        para = "TODO: revisit this. Todo: keep this note. XXX bad marker. xxx fine marker.\n"
        body = base_body(extra_mid=para)
        task = write_task(self.repo, body)
        p = run_tool(["lint-task", plan, task], cwd=self.repo)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("'TODO'", p.stdout)
        self.assertIn("'XXX'", p.stdout)
        self.assertNotIn("'Todo'", p.stdout)
        self.assertNotIn("'xxx'", p.stdout)


class FilesBlockTests(unittest.TestCase):
    """W8-4: files_block accepts bare project filenames and ignores a second backtick span."""

    def setUp(self):
        self.repo = make_repo()
        self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)

    def test_bare_filenames_and_trailing_annotation_are_handled(self):
        plan = write_plan(
            self.repo,
            "#### T01: Demo\n- Files: `Makefile`, `Dockerfile`, `LICENSE`, `server.py`\n\n",
        )
        body = (
            "**Files:**\n"
            "- Modify: `Makefile`\n"
            "- Modify: `Dockerfile`\n"
            "- Modify: `LICENSE`\n"
            "- Modify: `server.py` (wires up `app.run()`)\n\n"
            "- [ ] **Step 1: implement**\n\n"
            "```python\nx = 1\n```\n\n"
            "Then `git commit -m \"feat\"`.\n"
        )
        task = write_task(self.repo, body)
        p = run_tool(["lint-task", plan, task], cwd=self.repo)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)


class GitAddChainTests(unittest.TestCase):
    """W8-5: a `git add a b && git commit -m "msg"` step yields no false 'not in contract' errors."""

    def setUp(self):
        self.repo = make_repo()
        self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)

    def test_chained_git_add_and_commit_is_not_flagged(self):
        plan = write_plan(self.repo, "#### T01: Demo\n- Files: `a.py`, `b.py`\n\n")
        body = (
            "**Files:**\n- Modify: `a.py`\n- Modify: `b.py`\n\n"
            "- [ ] **Step 1: implement**\n\n"
            "```bash\ngit add a.py b.py && git commit -m \"demo\"\n```\n"
        )
        task = write_task(self.repo, body)
        p = run_tool(["lint-task", plan, task], cwd=self.repo)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)


class SpecHeadingMapFenceAwareTests(unittest.TestCase):
    """W8-9: the spec heading map used for coverage ignores '#' lines inside code fences."""

    def test_fenced_hash_does_not_create_a_spurious_uncovered_section(self):
        repo = make_repo()
        self.addCleanup(shutil.rmtree, repo, ignore_errors=True)
        spec = os.path.join(repo, "spec.md")
        spec_lines = [
            "## Section A",             # L1
            "",                         # L2
            "Intro line covered.",      # L3
            "",                         # L4
            "```text",                  # L5
            "# fake heading inside fence",  # L6
            "```",                      # L7
            "Tail line still part of Section A.",  # L8
            "",                         # L9
            "## Section B",             # L10
            "",                         # L11
            "Section B content covered too.",  # L12
        ]
        with open(spec, "w") as f:
            f.write("\n".join(spec_lines) + "\n")
        contracts = (
            "#### T01: Demo\n- Files: `demo.py`\n- Spec: L1-L4\n\n"
            "#### T02: Demo2\n- Files: `other.py`\n- Spec: L10-L12\n\n"
        )
        plan = write_plan(repo, contracts)
        p = run_tool(["contracts", plan, "--spec", spec], cwd=repo)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertNotIn("spec uncovered", p.stdout)


if __name__ == "__main__":
    unittest.main()
