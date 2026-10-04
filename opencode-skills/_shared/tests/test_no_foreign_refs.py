"""Tracked files must not name other model vendors or harnesses.

The few files below keep one intentional mention each (OpenCode scans the foreign skills folder, plan
bodies are linted for vendor names, repos may carry a convention file of another harness, the repo guide
`CLAUDE.md` names the sibling folders it is derived from). The banned words are
assembled from fragments so this file never matches itself.
"""
import os
import re
import subprocess
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BANNED = re.compile(
    r"\b(" + "|".join(["gl" + "m", "zc" + "ode", "za" + "i", "anthro" + "pic", "son" + "net", "op" + "us", "hai" + "ku"])
    + r")\b|z\." + "ai|cla" + "ude", re.I)
ALLOWED = {
    "install-opencode.sh",
    "CLAUDE.md",
    "oc-writing-plans/scripts/oc_plan_tool.py",
    "_shared/tests/test_plan_perf.py",
    "_shared/tests/test_plan_lint.py",
    "_shared/tests/test_oc_install.py",
    "_shared/tests/test_oc_debug_port.py",
    "_shared/tests/test_oc_devteam_port.py",
    "_shared/tests/test_oc_guard_port.py",
    "_shared/tests/test_oc_plan_lint_port.py",
    "_shared/tests/test_parity_markers.py",
    "_shared/tests/test_no_foreign_refs.py",
    "oc-systematic-debugging/scripts/oc-find-polluter.sh",
}


class NoForeignRefs(unittest.TestCase):
    def test_tracked_files_name_no_other_vendor(self):
        files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
        hits = []
        for rel in files:
            path = os.path.join(ROOT, rel)
            if rel in ALLOWED or not os.path.isfile(path):
                continue
            with open(path, encoding="utf-8", errors="ignore") as f:
                for n, line in enumerate(f, 1):
                    if BANNED.search(line):
                        hits.append(f"{rel}:{n}: {line.strip()[:100]}")
        self.assertEqual(hits, [])

    def test_allowlist_names_only_existing_files(self):
        missing = [rel for rel in sorted(ALLOWED) if not os.path.isfile(os.path.join(ROOT, rel))]
        self.assertEqual(missing, [])

    def test_allowlist_contains_repo_guide_and_installer(self):
        self.assertIn("CLAUDE.md", ALLOWED)
        self.assertIn("install-opencode.sh", ALLOWED)

    def test_allowlist_uses_oc_prefixed_plan_tool_key(self):
        self.assertIn("oc-writing-plans/scripts/oc_plan_tool.py", ALLOWED)
        self.assertNotIn("writing-plans/scripts/oc_plan_tool.py", ALLOWED)

    def test_docstring_explains_repo_guide_mention(self):
        self.assertIn("repo guide", " ".join(__doc__.split()))
        self.assertIn("sibling folders it is derived from", " ".join(__doc__.split()))


if __name__ == "__main__":
    unittest.main()
