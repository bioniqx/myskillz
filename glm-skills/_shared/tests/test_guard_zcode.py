import os
import subprocess
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
GUARD = os.path.join(os.path.dirname(os.path.dirname(HERE)), "glm-dev-team", "scripts", "guard.py")
sys.path.insert(0, os.path.dirname(GUARD))

import guard  # noqa: E402


class TestGuardZcode(unittest.TestCase):
    """zcode hook mode: foreign or missing roles silently allow; lane roles
    route to the shared checks with silent allows turned into explicit denies;
    Stop gates only programmer roles; malformed payloads fail open."""

    def payload(self, **over):
        base = {"hook_event_name": "PreToolUse", "cwd": "/repo"}
        base.update(over)
        return base

    def run_zcode(self, inp):
        """What guard_zcode printed (it always ends in sys.exit), stdout captured."""
        return guard.oc_capture(guard.guard_zcode, inp)

    def test_missing_or_foreign_agent_type_silently_allows(self):
        payloads = [
            {},
            {"agent_type": ""},
            {"agent_type": "general-purpose"},
            {"agent_type": "some-other-agent", "tool_name": "Write",
             "tool_input": {"file_path": "/tmp/notes.txt", "content": "x"}},
            {"agent_type": "glm-doc-writer", "tool_name": "Write",
             "tool_input": {"file_path": "docs/x.md", "content": "x"}},
        ]
        for inp in payloads:
            with mock.patch.object(guard, "guard_edit") as ge, \
                    mock.patch.object(guard, "guard_bash") as gb, \
                    mock.patch.object(guard, "guard_edit_ro") as gro, \
                    mock.patch.object(guard, "guard_bash_ro") as bro, \
                    mock.patch.object(guard, "guard_stop") as stop:
                self.assertEqual(self.run_zcode(inp), "", inp)
            for patched in (ge, gb, gro, bro, stop):
                patched.assert_not_called()

    def test_programmer_write_and_edit_route_to_edit_check(self):
        for tool in ("Write", "Edit"):
            inp = self.payload(agent_type="glm-programmer", tool_name=tool,
                               tool_input={"file_path": "src/app.py", "content": "print('hi')"})
            with mock.patch.object(guard, "guard_edit",
                                   side_effect=lambda i: guard.deny("outside the repo")) as ge:
                out = self.run_zcode(inp)
            ge.assert_called_once_with(inp)
            self.assertIn('"permissionDecision": "deny"', out, tool)
            self.assertIn("outside the repo", out, tool)

    def test_programmer_bash_routes_to_bash_check(self):
        inp = self.payload(agent_type="glm-programmer", tool_name="Bash",
                           tool_input={"command": "python3 -m unittest"})
        with mock.patch.object(guard, "guard_bash",
                               side_effect=lambda i: guard.deny("dangerous command")) as gb:
            out = self.run_zcode(inp)
        gb.assert_called_once_with(inp)
        self.assertIn('"permissionDecision": "deny"', out)
        self.assertIn("dangerous command", out)

    def test_silent_allow_from_edit_check_becomes_explicit_deny(self):
        inp = self.payload(agent_type="glm-programmer", tool_name="Write",
                           tool_input={"file_path": "src/app.py", "content": "x"})
        with mock.patch.object(guard, "guard_edit",
                               side_effect=lambda i: guard.allow()) as ge:
            out = self.run_zcode(inp)
        ge.assert_called_once_with(inp)
        self.assertIn("zcode lane cannot defer to the ask flow: Write", out)
        self.assertIn('"permissionDecision": "deny"', out)

    def test_silent_allow_from_bash_check_becomes_explicit_deny(self):
        inp = self.payload(agent_type="glm-programmer", tool_name="Bash",
                           tool_input={"command": "python3 -m unittest"})
        with mock.patch.object(guard, "guard_bash",
                               side_effect=lambda i: guard.allow()) as gb:
            out = self.run_zcode(inp)
        gb.assert_called_once_with(inp)
        self.assertIn("zcode lane cannot defer to the ask flow: Bash", out)

    def test_read_only_roles_route_to_read_only_checks(self):
        for role in ("glm-code-reviewer", "glm-team-leader", "glm-investigator"):
            inp = self.payload(agent_type=role, tool_name="Write",
                               tool_input={"file_path": "src/app.py"})
            with mock.patch.object(guard, "guard_edit_ro",
                                   side_effect=lambda i: guard.deny("read-only lane")) as gro, \
                    mock.patch.object(guard, "guard_bash_ro") as bro:
                out = self.run_zcode(inp)
            gro.assert_called_once_with(inp)
            bro.assert_not_called()
            self.assertIn("read-only lane", out, role)
        inp = self.payload(agent_type="glm-investigator", tool_name="Bash",
                           tool_input={"command": "grep -rn needle src"})
        with mock.patch.object(guard, "guard_bash_ro",
                               side_effect=lambda i: guard.allow("investigator bash ok")) as bro:
            out = self.run_zcode(inp)
        bro.assert_called_once_with(inp)
        self.assertIn('"permissionDecision": "allow"', out)
        self.assertIn("investigator bash ok", out)

    def test_stop_gates_only_programmer_roles(self):
        inp = self.payload(agent_type="glm-programmer", hook_event_name="Stop")
        with mock.patch.object(guard, "guard_stop",
                               side_effect=lambda i: guard.deny("lane not finished")) as stop:
            out = self.run_zcode(inp)
        stop.assert_called_once_with(inp)
        self.assertIn("lane not finished", out)
        for role in ("glm-team-leader", "glm-investigator", "general-purpose"):
            inp = self.payload(agent_type=role, hook_event_name="Stop")
            with mock.patch.object(guard, "guard_stop") as stop:
                self.assertEqual(self.run_zcode(inp), "", role)
            stop.assert_not_called()
        with mock.patch.object(guard, "guard_stop") as stop:
            self.assertEqual(self.run_zcode({"hook_event_name": "Stop"}), "")
        stop.assert_not_called()

    def test_non_dict_payloads_fail_open_to_allow(self):
        for bad in ([], ["x"], "not-a-dict", 42, None):
            with mock.patch.object(guard, "guard_edit") as ge, \
                    mock.patch.object(guard, "guard_bash") as gb:
                self.assertEqual(self.run_zcode(bad), "", bad)
            ge.assert_not_called()
            gb.assert_not_called()

    def test_malformed_stdin_fails_open_through_the_cli(self):
        r = subprocess.run([sys.executable, GUARD, "zcode"], input="{not json",
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_camelcase_and_snake_case_keys_both_accepted(self):
        # zcode hook stdin carries snake_case + camelCase fields: a payload
        # spelled entirely in camelCase (agentType, toolName, toolInput,
        # hookEventName) routes exactly like the snake_case one.
        camel = {"hookEventName": "PreToolUse", "cwd": "/repo",
                 "agentType": "glm-programmer", "toolName": "Write",
                 "toolInput": {"file_path": "src/app.py", "content": "x"}}
        snake = self.payload(agent_type="glm-programmer", tool_name="Write",
                             tool_input={"file_path": "src/app.py", "content": "x"})
        for inp in (camel, snake):
            with mock.patch.object(guard, "guard_edit",
                                   side_effect=lambda i: guard.deny("outside the repo")) as ge:
                out = self.run_zcode(inp)
            ge.assert_called_once_with(inp)
            self.assertIn('"permissionDecision": "deny"', out)
        camel_stop = {"hookEventName": "Stop", "cwd": "/repo", "agentType": "glm-programmer"}
        snake_stop = self.payload(agent_type="glm-programmer", hook_event_name="Stop")
        for inp in (camel_stop, snake_stop):
            with mock.patch.object(guard, "guard_stop",
                                   side_effect=lambda i: guard.deny("lane not finished")) as stop:
                out = self.run_zcode(inp)
            stop.assert_called_once_with(inp)
            self.assertIn("lane not finished", out)
