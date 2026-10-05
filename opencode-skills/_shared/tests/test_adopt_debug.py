import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

DEBUG_TOOL = (Path(__file__).resolve().parents[2]
              / "oc-systematic-debugging" / "scripts" / "oc_debug_tool.py")
SKILL_DIR = DEBUG_TOOL.parents[1]


def load_debug_tool():
    spec = importlib.util.spec_from_file_location("debug_tool_under_test", DEBUG_TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestScanPrintsDispatchRows(unittest.TestCase):
    def _run(self):
        mod = load_debug_tool()
        root = tempfile.mkdtemp(prefix="sdlane_test.")
        self.addCleanup(mod.shutil.rmtree, root, True)
        tasks = Path(root) / "tasks.json"
        tasks.write_text(json.dumps([{"id": "t1", "prompt": "p1"}, {"id": "t2", "prompt": "p2"}]))
        a = mod.argparse.Namespace(
            tasks=str(tasks), area=None, question=None, context_file=None,
            context="shared ctx", out=None, dir=root)
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = mod.cmd_scan(a)
        return mod, rc, buf.getvalue(), Path(root) / ".oc-debug" / "scan"

    def test_scan_writes_briefs_and_no_lanes_file(self):
        mod, rc, out, d = self._run()
        assert rc == 0
        assert (d / "t1.txt").is_file() and (d / "t2.txt").is_file()
        assert not (d / "lanes.json").exists()

    def test_output_lists_a_background_dispatch_row_per_brief(self):
        mod, rc, out, d = self._run()
        for tid in ("t1", "t2"):
            line = mod.oc_harness.dispatch_line(
                "oc-debug-worker", str((d / (tid + ".txt")).resolve()), "scan " + tid, 2,
                background=True)
            assert line in out

    def test_next_line_tells_the_model_to_read_the_verdicts(self):
        mod, rc, out, d = self._run()
        nxt = [l for l in out.splitlines() if l.startswith("NEXT: ")]
        assert len(nxt) == 1
        assert "VERDICT:" in nxt[0]
        assert "oc_harness.py run" not in out

    def test_prompts_carry_scripts_dir_in_a_byte_identical_prefix(self):
        mod, rc, out, d = self._run()
        t1 = (d / "t1.txt").read_text()
        t2 = (d / "t2.txt").read_text()
        assert t1.startswith(mod.SYS_PROMPT)
        assert ("S=%s" % mod.SCRIPTS) in t1
        assert t1.split("\n---\nTASK: ")[0] == t2.split("\n---\nTASK: ")[0]
        assert t1.endswith("TASK: p1") and t2.endswith("TASK: p2")

    def test_briefs_carry_the_absolute_root_in_the_shared_prefix(self):
        mod, rc, out, d = self._run()
        root = str(d.parents[1])
        expected = mod.repo_root(root) or mod.os.path.abspath(root)
        sep = "\n---\nTASK: "
        prefixes = set()
        for tid in ("t1", "t2"):
            prefix = (d / (tid + ".txt")).read_text().split(sep)[0]
            assert ("\nROOT=%s\n" % expected) in prefix
            prefixes.add(prefix)
        assert len(prefixes) == 1
        assert mod.os.path.isabs(expected)

    def test_worker_rule_resolves_paths_against_the_root_line(self):
        text = (SKILL_DIR / "opencode" / "agents" / "oc-debug-worker.md").read_text()
        rule1 = next(l for l in text.splitlines() if l.startswith("1. "))
        assert "ROOT=" in rule1

    def test_scan_without_tasks_or_area_returns_2(self):
        mod = load_debug_tool()
        root = tempfile.mkdtemp(prefix="sdlane_test.")
        self.addCleanup(mod.shutil.rmtree, root, True)
        a = mod.argparse.Namespace(tasks=None, area=None, question=None, context_file=None,
                                   context=None, out=None, dir=root)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            assert mod.cmd_scan(a) == 2
        assert "scan needs" in err.getvalue()

    def test_scan_dispatch_rows_come_in_waves_of_6_by_default(self):
        mod = load_debug_tool()
        root = tempfile.mkdtemp(prefix="sdlane_test.")
        self.addCleanup(mod.shutil.rmtree, root, True)
        tasks = root + "/t.json"
        Path(tasks).write_text(json.dumps([{"id": "a%d" % i, "prompt": "p"} for i in range(20)]))
        buf = io.StringIO()
        with redirect_stdout(buf):
            assert mod.main(["scan", "--tasks", tasks, "--dir", root, "--out", root + "/out"]) == 0
        out = buf.getvalue()
        assert mod.MAX_LANES == 6
        assert out.count("subagent(") == 20
        assert "WAVE 4 of 4 (2 workers):" in out
        assert "WAVE 1 of 4 (6 workers):" in out

    def test_scan_has_no_model_or_api_flags(self):
        mod = load_debug_tool()
        root = tempfile.mkdtemp(prefix="sdlane_test.")
        self.addCleanup(mod.shutil.rmtree, root, True)
        extras = (["--tier", "std"], ["--model", "m"], ["--effort", "low"], ["--base", "u"],
                  ["--max-tokens", "5"], ["-j", "1"], ["--print-prompts"], ["--lane", "agent"])
        for extra in extras:
            argv = ["scan", "--area", "x", "--dir", root, "--out", root + "/out"] + extra
            with contextlib.redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as cm:
                    mod.main(argv)
            assert cm.exception.code == 2, extra


class TestCmdSetup(unittest.TestCase):
    def test_setup_prints_only_the_opencode_block(self):
        mod = load_debug_tool()
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = mod.cmd_setup(mod.argparse.Namespace())
        out = buf.getvalue()
        assert rc == 0
        assert "oc-debug-worker" in out and "background" in out
        assert "oc_harness.py run" not in out

    def test_setup_accepts_only_the_opencode_harness(self):
        mod = load_debug_tool()
        with redirect_stdout(io.StringIO()):
            assert mod.main(["setup", "--harness", "opencode"]) == 0
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as cm:
                mod.main(["setup", "--harness", "other"])
        assert cm.exception.code == 2


class TestNoDirectApiCode(unittest.TestCase):
    def test_source_has_no_direct_api_code(self):
        src = DEBUG_TOOL.read_text()
        for word in ("TIERS", "urllib", "find_key", "api_call", "--tier",
                     "--effort", "--base", "lanes.json", "run_lanes"):
            self.assertNotIn(word, src, word)


def frontmatter(text):
    lines = text.split("\n")
    assert lines[0] == "---"
    return lines[1:lines.index("---", 1)]


class TestSkillFiles(unittest.TestCase):
    DOCS = ("SKILL.md", "README.md", "references/parallel-playbook.md",
            "opencode/agents/oc-debug-worker.md")
    BANNED = ("--tier", "--effort", "--lane", "lanes.json", "oc_harness.py run")

    def test_skill_frontmatter_holds_only_name_description_metadata(self):
        fm = frontmatter((SKILL_DIR / "SKILL.md").read_text())
        keys = [l.split(":", 1)[0] for l in fm if l and not l[0].isspace()]
        self.assertEqual(keys, ["name", "description", "metadata"])
        self.assertIn("name: oc-systematic-debugging", fm)
        desc = next(l for l in fm if l.startswith("description:"))[len("description:"):].strip()
        self.assertTrue(0 < len(desc) <= 1024, len(desc))

    def test_docs_carry_no_removed_terms(self):
        for rel in self.DOCS:
            text = (SKILL_DIR / rel).read_text()
            for word in self.BANNED:
                self.assertNotIn(word, text, rel + ": " + word)

    def test_opencode_agent_declares_no_model(self):
        mod = load_debug_tool()
        text = (SKILL_DIR / "opencode" / "agents" / "oc-debug-worker.md").read_text()
        keys = [l.split(":", 1)[0] for l in frontmatter(text) if l and not l[0].isspace()]
        for gone in ("model", "effort", "variant", "reasoningEffort"):
            self.assertNotIn(gone, keys)
        rendered = mod.oc_harness.render_agent(text, 2)
        self.assertIn("description:", rendered)
        self.assertNotRegex(rendered, r"(?m)^(model|effort|variant|reasoningEffort):")

    def test_skill_and_readme_describe_the_dispatch_rows(self):
        for rel in ("SKILL.md", "README.md"):
            text = (SKILL_DIR / rel).read_text()
            self.assertIn("background: true", text, rel)
            self.assertIn("VERDICT", text, rel)


class TestQuestionKeywords(unittest.TestCase):
    def test_stopwords_dropped_and_order_kept(self):
        mod = load_debug_tool()
        assert mod.question_keywords("why does the parser drop the trailing token") == [
            "parser", "drop", "trailing", "token"]

    def test_limit_and_case_insensitive_dedupe(self):
        mod = load_debug_tool()
        assert mod.question_keywords("Parser parser alpha beta gamma delta", limit=3) == [
            "Parser", "alpha", "beta"]

    def test_no_question_gives_no_keywords(self):
        mod = load_debug_tool()
        assert mod.question_keywords(None) == []


class TestBuildTasksCodeWindows(unittest.TestCase):
    def test_area_prompt_carries_code_around_the_match(self):
        mod = load_debug_tool()
        root = tempfile.mkdtemp(prefix="sdscan_test.")
        self.addCleanup(mod.shutil.rmtree, root, True)
        pkg = Path(root) / "pkg"
        pkg.mkdir()
        (pkg / "parse.py").write_text(
            "def parse(text):\n"
            "    tokens = text.split()\n"
            "    return tokens[:-1]  # drops the trailing token\n")
        a = mod.argparse.Namespace(tasks=None, area=["pkg"],
                                   question="why does the parser drop the trailing token")
        tasks = mod.build_tasks(a, root)
        assert len(tasks) == 1
        prompt = tasks[0]["prompt"]
        assert "pkg/parse.py:3:" in prompt
        assert "CODE:" in prompt
        assert "return tokens[:-1]" in prompt.split("CODE:", 1)[1]


class TestBuildTasksGrepsAreaOnce(unittest.TestCase):
    def test_one_area_scoped_grep_per_area(self):
        mod = load_debug_tool()
        calls = []

        def fake_grep_area(root, area, words, cap):
            calls.append((area, list(words)))
            return ""

        def no_repo_wide_grep(*_a, **_k):
            raise AssertionError("build_tasks must not run a repo-wide grep per keyword")

        a = mod.argparse.Namespace(tasks=None, area=["src/a", "src/b"],
                                   question="why does the parser drop the trailing token")
        with patch.object(mod, "grep_area", fake_grep_area), \
                patch.object(mod, "grep", no_repo_wide_grep), \
                patch.object(mod, "sh", lambda *_a, **_k: (0, "x.py\n")):
            tasks = mod.build_tasks(a, ".")
        kw = ["parser", "drop", "trailing", "token"]
        assert calls == [("src/a", kw), ("src/b", kw)]
        assert [t["id"] for t in tasks] == ["src/a", "src/b"]


if __name__ == "__main__":
    unittest.main()
