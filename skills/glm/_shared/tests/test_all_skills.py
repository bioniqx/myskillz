"""All-skill hygiene checks and the root installer script.

Verifies: shared modules are vendored byte-identically into each Phase 1
skill's scripts/, every .py file in skills/glm compiles, every SKILL.md has
name == directory (no -glm suffix) and a description <= 1024 chars, and
install-opencode.sh installs the five Phase 1 skills and prints the snippet.
"""

import hashlib
import json
import os
import py_compile
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
GLM_ROOT = os.path.dirname(os.path.dirname(HERE))
REPO_ROOT = os.path.dirname(os.path.dirname(GLM_ROOT))

PHASE1_SKILLS = [
    "systematic-debugging-glm",
    "writing-plans-glm",
    "requirements-code-audit-glm",
    "brainstorming-glm",
    "doc-generator-glm",
]


def extract_description(frontmatter):
    """Read the 'description' YAML value: quoted, plain, or a >-/>/|-/| block scalar."""
    lines = frontmatter.split("\n")
    for i, line in enumerate(lines):
        m = re.match(r"^description:\s*(.*)$", line)
        if not m:
            continue
        rest = m.group(1).strip()
        if rest in (">-", ">", "|-", "|"):
            block = []
            for cont in lines[i + 1:]:
                if cont.strip() == "":
                    continue
                if cont.startswith(" ") or cont.startswith("\t"):
                    block.append(cont.strip())
                else:
                    break
            return " ".join(block)
        if len(rest) >= 2 and rest[0] == rest[-1] and rest[0] in ('"', "'"):
            return rest[1:-1]
        return rest
    return None


class TestVendoredCopies(unittest.TestCase):
    def test_vendored_copies_match_shared(self):
        """Every skill's scripts/{zai_client,oc_harness}.py that exists matches _shared/."""
        shared_dir = os.path.join(GLM_ROOT, "_shared")
        found_any = False
        for shared_file in ("zai_client.py", "oc_harness.py"):
            shared_path = os.path.join(shared_dir, shared_file)
            with open(shared_path, "rb") as fh:
                shared_hash = hashlib.sha256(fh.read()).hexdigest()
            for skill in PHASE1_SKILLS:
                vendor_path = os.path.join(GLM_ROOT, skill, "scripts", shared_file)
                if not os.path.exists(vendor_path):
                    continue
                found_any = True
                with open(vendor_path, "rb") as fh:
                    vendor_hash = hashlib.sha256(fh.read()).hexdigest()
                self.assertEqual(
                    shared_hash, vendor_hash,
                    "%s does not match %s" % (vendor_path, shared_path))
        self.assertTrue(found_any, "no vendored copies found under any Phase 1 skill/scripts/")


class TestScriptsCompile(unittest.TestCase):
    def test_all_scripts_compile(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            n = 0
            for root, dirs, files in os.walk(GLM_ROOT):
                if "__pycache__" in dirs:
                    dirs.remove("__pycache__")
                for fname in files:
                    if fname.endswith(".py"):
                        filepath = os.path.join(root, fname)
                        n += 1
                        cfile = os.path.join(tmpdir, "%d.pyc" % n)
                        try:
                            py_compile.compile(filepath, cfile=cfile, doraise=True)
                        except py_compile.PyCompileError as exc:
                            self.fail("%s has syntax error: %s" % (filepath, exc))


class TestSkillMdHygiene(unittest.TestCase):
    def test_skill_md_hygiene(self):
        for skill in PHASE1_SKILLS:
            expected_name = skill[:-4] if skill.endswith("-glm") else skill
            skill_md = os.path.join(GLM_ROOT, skill, "SKILL.md")
            with open(skill_md, encoding="utf-8") as fh:
                content = fh.read()

            match = re.search(r"^---\n(.*?)\n---", content, re.DOTALL)
            self.assertIsNotNone(match, "%s has no frontmatter" % skill_md)
            frontmatter = match.group(1)

            name_match = re.search(r"^name:\s*[\"']?([^\"'\n]+)[\"']?\s*$", frontmatter, re.M)
            self.assertIsNotNone(name_match, "%s missing 'name' field" % skill_md)
            name = name_match.group(1).strip()
            self.assertEqual(name, expected_name,
                              "%s name is %r, expected %r" % (skill_md, name, expected_name))

            desc = extract_description(frontmatter)
            self.assertIsNotNone(desc, "%s missing 'description' field" % skill_md)
            self.assertLessEqual(len(desc), 1024,
                                  "%s description is %d chars, max 1024" % (skill_md, len(desc)))


class TestInstallOpencodeScript(unittest.TestCase):
    def setUp(self):
        self.script = os.path.join(GLM_ROOT, "install-opencode.sh")

    def test_install_opencode_script_exists(self):
        self.assertTrue(os.path.exists(self.script), "%s does not exist" % self.script)
        self.assertTrue(os.access(self.script, os.X_OK), "%s is not executable" % self.script)

    def test_install_opencode_installs_and_prints_snippet(self):
        home = tempfile.mkdtemp()
        try:
            result = subprocess.run(
                ["sh", self.script, "--major", "1", "--home", home],
                capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr)
            for skill in PHASE1_SKILLS:
                expected_name = skill[:-4] if skill.endswith("-glm") else skill
                dst = os.path.join(home, ".config", "opencode", "skills", expected_name)
                self.assertTrue(os.path.isdir(dst), "missing installed skill dir %s" % dst)
            self.assertIn('"$schema"', result.stdout)
            self.assertIn("opencode.ai/config.json", result.stdout)
        finally:
            shutil.rmtree(home, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
