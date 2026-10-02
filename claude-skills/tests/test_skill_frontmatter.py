import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

KEY_RE = re.compile(r"^([A-Za-z_][\w-]*):\s*(.*)$")
BLOCK_MARKERS = {">", "|", ">-", "|-", ">+", "|+"}


def _scalar(parts):
    first = "" if parts[0] in BLOCK_MARKERS else parts[0]
    text = " ".join(p for p in [first] + parts[1:] if p)
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "'\"":
        text = text[1:-1]
    return text


def parse_frontmatter(text):
    """Return the top-level frontmatter keys of a Markdown file as {key: str}."""
    lines = text.split("\n")
    if lines[0].strip() != "---":
        raise ValueError("missing opening ---")
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        raise ValueError("missing closing ---")
    fields = {}
    key = None
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line[0] in " \t" or line.startswith("- "):
            if key is None:
                raise ValueError("value line before any key: " + line)
            fields[key].append(line.strip())
            continue
        match = KEY_RE.match(line)
        if not match:
            raise ValueError("bad frontmatter line: " + line)
        key = match.group(1)
        fields[key] = [match.group(2).strip()]
    return {k: _scalar(v) for k, v in fields.items()}


class ParserTests(unittest.TestCase):
    def test_plain_and_quoted_values(self):
        text = "---\nname: demo\ndescription: \"Quoted text\"\n---\nbody\n"
        self.assertEqual(
            parse_frontmatter(text),
            {"name": "demo", "description": "Quoted text"},
        )

    def test_folded_block_and_continuation_lines(self):
        text = (
            "---\nname: demo\ndescription: >\n  first line\n  second line\n"
            "when_to_use: starts here\n  and continues\n---\n"
        )
        fields = parse_frontmatter(text)
        self.assertEqual(fields["description"], "first line second line")
        self.assertEqual(fields["when_to_use"], "starts here and continues")

    def test_list_values_are_accepted(self):
        text = "---\nname: demo\nallowed-tools:\n  - Read\n  - Bash\n---\n"
        self.assertEqual(parse_frontmatter(text)["allowed-tools"], "- Read - Bash")

    def test_rejects_missing_delimiters_and_bad_lines(self):
        for bad in ("name: demo\n", "---\nname: demo\n", "---\nnot a key line\n---\n"):
            with self.assertRaises(ValueError):
                parse_frontmatter(bad)


SKILL_DIRS = [
    "claude-brainstorming-6.3",
    "claude-dev-team-v3.2",
    "claude-requirements-code-audit",
    "claude-writing-plans-6.2",
    "claude-systematic-debugging-6.3",
    "claude-doc-generator",
    "claude-git-diff-summary",
    "claude-frontend-design-Jun18",
]
EXPECTED_NAMES = {
    "claude-brainstorming-6.3": "claude-brainstorming",
    "claude-dev-team-v3.2": "claude-dev-team",
    "claude-requirements-code-audit": "claude-requirements-code-audit",
    "claude-writing-plans-6.2": "claude-writing-plans",
    "claude-systematic-debugging-6.3": "claude-systematic-debugging",
    "claude-doc-generator": "claude-doc-generator",
    "claude-git-diff-summary": "claude-git-diff-summary",
    "claude-frontend-design-Jun18": "claude-frontend-design",
}
DEFAULT_CAP = 14000
SIZE_CAPS = {
    "claude-brainstorming-6.3": 10000,
    "claude-dev-team-v3.2": 12000,
    "claude-requirements-code-audit": 10000,
    "claude-doc-generator": 10000,
}
DESCRIPTION_BUDGET = 1024


def skill_md(name):
    return ROOT / name / "SKILL.md"


class SkillFileTests(unittest.TestCase):
    def test_every_directory_has_a_skill_file(self):
        for name in SKILL_DIRS:
            with self.subTest(directory=name):
                self.assertTrue(skill_md(name).is_file(), "missing SKILL.md")

    def test_required_fields_present(self):
        for name in SKILL_DIRS:
            with self.subTest(directory=name):
                fields = parse_frontmatter(skill_md(name).read_text(encoding="utf-8"))
                self.assertTrue(fields.get("name"), "missing name")
                self.assertEqual(fields["name"], EXPECTED_NAMES[name])
                self.assertTrue(fields.get("description"), "missing description")

    def test_description_budget(self):
        for name in SKILL_DIRS:
            with self.subTest(directory=name):
                fields = parse_frontmatter(skill_md(name).read_text(encoding="utf-8"))
                used = len(fields.get("description", "")) + len(fields.get("when_to_use", ""))
                self.assertLessEqual(
                    used, DESCRIPTION_BUDGET,
                    "description + when_to_use is %d characters" % used,
                )

    def test_size_cap(self):
        for name in SKILL_DIRS:
            with self.subTest(directory=name):
                size = len(skill_md(name).read_bytes())
                cap = SIZE_CAPS.get(name, DEFAULT_CAP)
                self.assertLessEqual(size, cap, "SKILL.md is %d bytes, cap %d" % (size, cap))


if __name__ == "__main__":
    unittest.main()
