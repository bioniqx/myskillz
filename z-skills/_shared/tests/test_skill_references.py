"""Spec 2026-11-25: every bundled path a skill names in prose must exist.

A skill body that points at a missing reference file, script or agent is a
broken reference: the reader loads nothing and the step silently degrades.
The scanner is exercised on a temporary fixture first, then run over the tree."""
import os
import re
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
SKILLS = sorted(name for name in os.listdir(ROOT)
                if name.startswith("z-") and os.path.isfile(os.path.join(ROOT, name, "SKILL.md"))
                and "video" not in name)
REFERENCE = re.compile(
    r"(?<![A-Za-z0-9_./-])((?:z-[a-z-]+/)?(?:scripts|references|agents|commands)/[A-Za-z0-9_.\-/]+[A-Za-z0-9_])")


def missing_references(skill_root, text):
    """Paths named in `text` that do not exist under `skill_root`, or under the
    repository root when the path names another skill. A bare word pair whose
    last word has no file extension (`agents/hooks,`) is prose, not a path."""
    missing = []
    for match in REFERENCE.finditer(text):
        path = match.group(1)
        if text[match.end():match.end() + 1] == "," and "." not in path.rsplit("/", 1)[-1]:
            continue
        base = ROOT if path.startswith("z-") else skill_root
        if not os.path.exists(os.path.join(base, path)):
            missing.append(path)
    return missing


class ScannerTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.skill = os.path.join(self._tmp.name, "z-sample")

    def _write(self, rel):
        path = os.path.join(self.skill, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("x")

    def test_an_existing_path_is_not_reported(self):
        self._write("references/rules.md")
        self.assertEqual(missing_references(self.skill, "Read `references/rules.md` first."), [])

    def test_a_broken_reference_is_reported_even_before_a_comma(self):
        # Only a word pair without an extension may hide behind the comma rule.
        self._write("references/rules.md")
        text = "Read references/missing.md, then references/other.py."
        self.assertEqual(missing_references(self.skill, text),
                         ["references/missing.md", "references/other.py"])

    def test_a_bare_word_pair_before_a_comma_is_prose(self):
        text = "After it installs or changes agents/hooks, tell the user."
        self.assertEqual(missing_references(self.skill, text), [])

    def test_another_skill_is_resolved_from_the_repository_root(self):
        present = "Run `z-writing-plans/scripts/plan_tool.py doctor`."
        self.assertEqual(missing_references(self.skill, present), [])
        absent = "Run `z-no-such-skill/scripts/tool.py doctor`."
        self.assertEqual(missing_references(self.skill, absent),
                         ["z-no-such-skill/scripts/tool.py"])

    def test_an_empty_text_reports_nothing(self):
        self.assertEqual(missing_references(self.skill, ""), [])


class TreeTests(unittest.TestCase):
    def _prose_files(self, skill):
        for dirpath, dirnames, filenames in os.walk(os.path.join(ROOT, skill)):
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            for filename in filenames:
                if filename.endswith(".md"):
                    yield os.path.join(dirpath, filename)

    def test_every_skill_prose_file_names_only_existing_paths(self):
        broken = []
        for skill in SKILLS:
            for path in self._prose_files(skill):
                with open(path, encoding="utf-8") as fh:
                    lines = fh.read().splitlines()
                for line_number, line in enumerate(lines, 1):
                    for missing in missing_references(os.path.join(ROOT, skill), line):
                        broken.append("%s:%d %s" % (os.path.relpath(path, ROOT), line_number, missing))
        self.assertEqual(broken, [], "\n".join(broken))


if __name__ == "__main__":
    unittest.main()
