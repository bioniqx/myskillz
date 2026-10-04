"""Snippet and content tests for the oc doc-generator SKILL.md (T29).

The bash blocks of SKILL.md are extracted and executed against fixtures under the system
temp dir; nothing runs inside the repository.
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[2] / "oc-doc-generator"
SKILL = SKILL_DIR / "SKILL.md"
WRITER = SKILL_DIR / "opencode" / "agents" / "oc-doc-writer.md"
REVIEWER = SKILL_DIR / "opencode" / "agents" / "oc-doc-reviewer.md"
COMMAND = SKILL_DIR / "opencode" / "commands" / "oc-docs.md"
STATE = Path(".opencode") / "oc-doc-gen"
FENCE = "`" * 3
HUMAN_MARK = "TO" + "DO(human)"


def read(path):
    return path.read_text(encoding="utf-8")


def section(text, prefix):
    start = text.index("\n## " + prefix)
    end = text.find("\n## ", start + 4)
    return text[start:] if end == -1 else text[start:end]


def bash_blocks(text):
    return re.findall(FENCE + r"bash\n(.*?)\n" + FENCE, text, re.S)


def fence_after(text, marker):
    tail = text[text.index(marker):]
    return re.search(FENCE + r"[a-z]*\n(.*?)\n" + FENCE, tail, re.S).group(1)


def template(text, start_marker):
    tail = text[text.index(start_marker):]
    return tail[:tail.index(FENCE)]


def run_bash(script, cwd):
    env = {"PATH": os.environ.get("PATH", ""), "HOME": str(cwd)}
    return subprocess.run(["bash", "-c", script], cwd=str(cwd), env=env,
                          capture_output=True, text=True, timeout=120)


class ScriptTests(unittest.TestCase):
    def setUp(self):
        self.repo = Path(os.path.realpath(tempfile.mkdtemp()))
        self.addCleanup(shutil.rmtree, str(self.repo), True)
        subprocess.run(["git", "init", "-q"], cwd=str(self.repo), check=True)
        (self.repo / "hello.py").write_text("print('hi')\n", encoding="utf-8")
        subprocess.run(["git", "add", "hello.py"], cwd=str(self.repo), check=True)
        subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                        "-c", "commit.gpgsign=false", "commit", "-q", "-m", "init"],
                       cwd=str(self.repo), check=True)
        self.text = read(SKILL)

    def test_recon_cache_hits_once_the_manifest_is_saved(self):
        recon = bash_blocks(section(self.text, "2. TURN 1"))[0]
        first = run_bash(recon, self.repo)
        self.assertEqual(first.returncode, 0, first.stderr)
        head = re.search(r"^HEAD: (\S+)$", first.stdout, re.M).group(1)
        manifest = fence_after(self.text, "into this manifest")
        (self.repo / STATE).mkdir(parents=True, exist_ok=True)
        (self.repo / STATE / "recon.md").write_text(
            "HEAD: %s\n%s\n" % (head, manifest), encoding="utf-8")
        second = run_bash(recon, self.repo)
        self.assertIn("=== CACHE HIT ===", second.stdout)

    def test_turn2_bash_writes_manifest_state_and_index(self):
        script = bash_blocks(section(self.text, "3. TURN 2"))[0]
        script = (script.replace("<output dir>", "docs").replace("<HEAD>", "abc1234")
                  .replace("<HIGH files>", "overview.md api-reference.md")
                  .replace("<LOW files>", "user-guide.md"))
        result = run_bash(script, self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)
        recon = (self.repo / STATE / "recon.md").read_text(encoding="utf-8").splitlines()
        self.assertEqual([l for l in recon if l.startswith("HEAD:")], ["HEAD: abc1234"])
        state = json.loads((self.repo / STATE / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["head"], "abc1234")
        index = (self.repo / "docs" / "README.md").read_text(encoding="utf-8")
        self.assertIn("(./overview.md)", index)
        self.assertIn("(./user-guide.md)", index)

    def test_finish_flags_broken_local_links_but_not_urls_and_keeps_the_manifest(self):
        script = bash_blocks(section(self.text, "5. TURN 4"))[0]
        script = (script.replace("<output dir>", "docs")
                  .replace("<all selected files>", "overview.md user-guide.md")
                  .replace("<LOW files>", "user-guide.md"))
        docs = self.repo / "docs"
        docs.mkdir()
        (docs / "overview.md").write_text(
            "# Overview\n[ext](https://example.com/guide.md) [ok](./user-guide.md) "
            "[bad](missing.md)\n", encoding="utf-8")
        (docs / "user-guide.md").write_text("# Guide\nplain text\n", encoding="utf-8")
        (self.repo / STATE).mkdir(parents=True)
        (self.repo / STATE / "recon.md").write_text("HEAD: abc\nkeep me\n", encoding="utf-8")
        result = run_bash(script, self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("BROKEN_LINK: missing.md", result.stdout)
        self.assertNotIn("example.com", result.stdout)
        self.assertNotIn("BROKEN_LINK: ./user-guide.md", result.stdout)
        self.assertTrue((self.repo / STATE / "state.json").is_file())
        self.assertEqual((self.repo / STATE / "recon.md").read_text(encoding="utf-8"),
                         "HEAD: abc\nkeep me\n")


class ContentTests(unittest.TestCase):
    def setUp(self):
        self.text = read(SKILL)

    def test_gate_section_is_restored(self):
        gate = self.text[self.text.index("### 3.0"):self.text.index("### 3.1")]
        for needle in ("[create]", "[update]", '"ok"', "non-interactive", "which packages"):
            self.assertIn(needle, gate)

    def test_catalog_rows_and_readme_rule(self):
        rows = [[c.strip() for c in line.strip().strip("|").split("|")]
                for line in self.text.splitlines() if line.startswith("|")]
        by_file = {r[2].strip("`"): r for r in rows if len(r) == 6 and r[2].startswith("`")}
        for name in ("overview.md", "test-plan.md", "deployment.md", "feature-spec.md",
                     "traceability.md", "technical-overview.md", "admin-guide.md",
                     "dependencies.md", "qa-checklist.md"):
            self.assertIn(name, by_file)
        self.assertNotIn("README.md", by_file)
        starred = {name for name, row in by_file.items() if row[0] == "★"}
        self.assertEqual(starred, {"overview.md", "setup-guide.md", "architecture.md",
                                   "api-reference.md", "data-model.md", "user-guide.md",
                                   "test-plan.md", "deployment.md"})
        self.assertIn("reserved for this index", self.text)

    def test_writer_template_has_update_mode_fidelity_and_language(self):
        tmpl = template(self.text, "ROLE: Technical writer")
        self.assertNotIn("sed -n", tmpl)
        self.assertNotIn("Do not read this project's docs", tmpl)
        for needle in ("TAG: <create|update>", "Language: <language>", "offset and limit",
                       "read the existing", "mismatch", "Mermaid", HUMAN_MARK):
            self.assertIn(needle, tmpl)

    def test_reviewer_template_has_fidelity_completeness_and_diagram_checks(self):
        tmpl = template(self.text, "ROLE: Technical fact-checker")
        for needle in ("Requirements fidelity", "Completeness", "Mermaid", "broadly-wrong",
                       "do NOT rewrite"):
            self.assertIn(needle, tmpl)

    def test_final_summary_surfaces_reviewer_fields(self):
        self.assertIn("`unresolved=` and `human=`", section(self.text, "5. TURN 4"))

    def test_header_does_not_claim_there_are_no_other_files(self):
        self.assertNotIn("there are none", self.text)
        self.assertIn("oc_harness.py", self.text)

    def test_agent_files_and_command(self):
        writer, reviewer, command = read(WRITER), read(REVIEWER), read(COMMAND)
        self.assertIn("bash: false", writer)
        for needle in ("offset and limit", "existing doc", "mismatch"):
            self.assertIn(needle, writer)
        for needle in ("Mermaid", "broadly-wrong", "requirements", "completeness"):
            self.assertIn(needle, reviewer)
        self.assertIn("non-interactive", command)


if __name__ == "__main__":
    unittest.main()
