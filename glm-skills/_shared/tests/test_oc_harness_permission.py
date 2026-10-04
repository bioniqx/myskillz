"""render_agent must emit the v2 shell permission key next to bash, with identical rules.

opencode v2.0.22 names its shell tool "shell"; an agent that sets only "bash" has every shell
command denied. v1 has no "shell" tool and keeps only "bash".
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import oc_harness


def agent_text(bash, access="read", write_paths=None):
    lines = ["---", 'description: "lane"', "model: flash", "access: %s" % access,
             "bash: %s" % ("true" if bash else "false")]
    if write_paths:
        lines.append("write_paths: %s" % write_paths)
    lines += ["---", "", "body"]
    return "\n".join(lines)


def permission_lines(rendered):
    """The indented lines under `permission:` up to the next top-level key, in order."""
    out, inside = [], False
    for line in rendered.split("\n"):
        if line == "permission:":
            inside = True
        elif inside and line.startswith("  "):
            out.append(line)
        elif inside and not line.startswith(" "):
            break
    return out


def value_of(rendered, key):
    prefix = "  %s: " % key
    for line in permission_lines(rendered):
        if line.startswith(prefix):
            return line[len(prefix):]
    return None


class ShellPermissionKeyTests(unittest.TestCase):
    def test_v2_shell_matches_bash_when_allowed(self):
        rendered = oc_harness.render_agent(agent_text(True), 2)
        self.assertEqual(value_of(rendered, "bash"), "allow")
        self.assertEqual(value_of(rendered, "shell"), "allow")

    def test_v2_shell_matches_bash_when_denied(self):
        rendered = oc_harness.render_agent(agent_text(False), 2)
        self.assertEqual(value_of(rendered, "bash"), "deny")
        self.assertEqual(value_of(rendered, "shell"), "deny")

    def test_v2_shell_follows_bash_for_a_write_lane(self):
        rendered = oc_harness.render_agent(agent_text(True, "write", "docs/**"), 2)
        self.assertEqual(value_of(rendered, "shell"), value_of(rendered, "bash"))
        self.assertIn('    "docs/**": allow', permission_lines(rendered))

    def test_v2_keeps_execute_denied(self):
        rendered = oc_harness.render_agent(agent_text(True), 2)
        self.assertEqual(value_of(rendered, "execute"), "deny")

    def test_v1_has_no_shell_key(self):
        rendered = oc_harness.render_agent(agent_text(True), 1)
        self.assertEqual(value_of(rendered, "bash"), "allow")
        self.assertIsNone(value_of(rendered, "shell"))


if __name__ == "__main__":
    unittest.main()
