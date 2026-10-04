"""render_agent emits the shell permission under `shell` (opencode v2.0.22) and `bash`, with one rule."""
import importlib.util
import os
import re
import sys
import unittest

SHARED = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ROOT = os.path.dirname(SHARED)
sys.path.insert(0, SHARED)

import oc_harness  # noqa: E402

SKILLS = ("oc-brainstorming", "oc-dev-team", "oc-doc-generator",
          "oc-requirements-code-audit", "oc-systematic-debugging", "oc-writing-plans")


def agent_text(bash, write_paths=None):
    lines = ["---", 'description: "probe"']
    if write_paths:
        lines += ["access: write", 'write_paths: "%s"' % write_paths]
    lines += ["bash: %s" % ("true" if bash else "false"), "---", "", "Body"]
    return "\n".join(lines)


def permission_value(rendered, key):
    found = re.search(r"^  %s: (\S+)$" % re.escape(key), rendered, re.M)
    return found.group(1) if found else None


class ShellPermissionKey(unittest.TestCase):
    def test_shell_rule_equals_bash_rule(self):
        for bash, expected in ((True, "allow"), (False, "deny")):
            for write_paths in (None, "src/**"):
                with self.subTest(bash=bash, write_paths=write_paths):
                    out = oc_harness.render_agent(agent_text(bash, write_paths), 2)
                    self.assertEqual(permission_value(out, "bash"), expected)
                    self.assertEqual(permission_value(out, "shell"), expected)

    def test_shell_line_follows_bash_line(self):
        out = oc_harness.render_agent(agent_text(True), 2).splitlines()
        self.assertEqual(out[out.index("  bash: allow") + 1], "  shell: allow")

    def test_vendored_copies_emit_shell(self):
        for skill in SKILLS:
            with self.subTest(skill=skill):
                path = os.path.join(ROOT, skill, "scripts", "oc_harness.py")
                spec = importlib.util.spec_from_file_location("vendored_" + skill.replace("-", "_"), path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                out = module.render_agent(agent_text(True), 2)
                self.assertEqual(permission_value(out, "shell"), "allow")

    def test_vendored_copies_byte_identical(self):
        with open(os.path.join(SHARED, "oc_harness.py"), "rb") as fh:
            source = fh.read()
        for skill in SKILLS:
            with self.subTest(skill=skill):
                with open(os.path.join(ROOT, skill, "scripts", "oc_harness.py"), "rb") as fh:
                    self.assertEqual(fh.read(), source)


if __name__ == "__main__":
    unittest.main()
