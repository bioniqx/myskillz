import json
import os
import subprocess
import tempfile
import textwrap
import unittest

REPO_ROOT = os.getcwd()
PLUGIN_DIR = os.path.join(REPO_ROOT, "skills/glm/dev-team-glm/opencode/plugins")
V1_PATH = os.path.join(PLUGIN_DIR, "devteam-guard.v1.js")
V2_PATH = os.path.join(PLUGIN_DIR, "devteam-guard.v2.js")


def _write_guard_stub(skill_dir, decision):
    scripts_dir = os.path.join(skill_dir, "scripts")
    os.makedirs(scripts_dir, exist_ok=True)
    guard_path = os.path.join(scripts_dir, "guard.py")
    with open(guard_path, "w") as f:
        f.write(
            "import json\nimport sys\n\nsys.stdin.read()\nprint(json.dumps(%s))\n"
            % json.dumps(decision)
        )
    return guard_path


def _write_recording_stub(skill_dir, decision, record_path):
    scripts_dir = os.path.join(skill_dir, "scripts")
    os.makedirs(scripts_dir, exist_ok=True)
    guard_path = os.path.join(scripts_dir, "guard.py")
    with open(guard_path, "w") as f:
        f.write(
            "import json\nimport sys\n\n"
            "argv = sys.argv[1:]\n"
            "stdin_data = json.loads(sys.stdin.read())\n"
            "with open(%s, 'w') as rec:\n"
            "    json.dump({'argv': argv, 'stdin': stdin_data}, rec)\n"
            "print(json.dumps(%s))\n"
            % (json.dumps(record_path), json.dumps(decision))
        )
    return guard_path


def _load_plugin_source(path, skill_dir):
    with open(path) as f:
        source = f.read()
    return source.replace("{{SKILL_DIR}}", skill_dir)


def _run_v1(tmp_dir, skill_dir, role, tool, args):
    source = _load_plugin_source(V1_PATH, skill_dir)
    plugin_path = os.path.join(tmp_dir, "plugin.mjs")
    with open(plugin_path, "w") as f:
        f.write(source)
    driver_path = os.path.join(tmp_dir, "driver.mjs")
    driver = textwrap.dedent(
        """\
        import { DevteamGuard } from "%s";
        const hooks = await DevteamGuard({ directory: "/tmp/work" });
        try {
          await hooks["tool.execute.before"](
            { tool: "%s" },
            { args: %s }
          );
          process.stdout.write("ALLOWED");
        } catch (err) {
          process.stdout.write("DENIED:" + err.message);
        }
        """
    ) % (plugin_path, tool, json.dumps(args))
    with open(driver_path, "w") as f:
        f.write(driver)
    env = dict(os.environ)
    if role is None:
        env.pop("DEVTEAM_ROLE", None)
    else:
        env["DEVTEAM_ROLE"] = role
    return subprocess.run(
        ["node", driver_path], capture_output=True, text=True, env=env, timeout=30
    )


def _run_v2(tmp_dir, skill_dir, role, tool, args):
    source = _load_plugin_source(V2_PATH, skill_dir)
    plugin_path = os.path.join(tmp_dir, "plugin.mjs")
    with open(plugin_path, "w") as f:
        f.write(source)
    driver_path = os.path.join(tmp_dir, "driver.mjs")
    driver = textwrap.dedent(
        """\
        import plugin from "%s";
        const hooks = await plugin({ directory: "/tmp/work" });
        try {
          await hooks["tool.execute.before"](
            { tool: "%s" },
            { args: %s }
          );
          process.stdout.write("ALLOWED");
        } catch (err) {
          process.stdout.write("DENIED:" + err.message);
        }
        """
    ) % (plugin_path, tool, json.dumps(args))
    with open(driver_path, "w") as f:
        f.write(driver)
    env = dict(os.environ)
    if role is None:
        env.pop("DEVTEAM_ROLE", None)
    else:
        env["DEVTEAM_ROLE"] = role
    return subprocess.run(
        ["node", driver_path], capture_output=True, text=True, env=env, timeout=30
    )


class TestDevteamPlugins(unittest.TestCase):
    def test_v2_shape_has_no_plugin_package(self):
        with open(V2_PATH) as f:
            source = f.read()
        assert "@opencode/plugin" not in source
        assert "Plugin.define" not in source
        assert "ctx.directory" in source

    def test_v1_denies_and_throws(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            skill_dir = os.path.join(tmp_dir, "skill")
            _write_guard_stub(
                skill_dir,
                {
                    "hookSpecificOutput": {
                        "permissionDecision": "deny",
                        "permissionDecisionReason": "blocked command",
                    }
                },
            )
            result = _run_v1(
                tmp_dir, skill_dir, "programmer", "bash", {"command": "rm -rf /"}
            )
            assert result.returncode == 0, result.stderr
            assert result.stdout == "DENIED:blocked command"

    def test_v1_allows_when_decision_is_allow(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            skill_dir = os.path.join(tmp_dir, "skill")
            _write_guard_stub(skill_dir, {})
            result = _run_v1(tmp_dir, skill_dir, "programmer", "bash", {"command": "ls"})
            assert result.returncode == 0, result.stderr
            assert result.stdout == "ALLOWED"

    def test_v1_fails_open_without_role(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            skill_dir = os.path.join(tmp_dir, "skill")
            guard_path = _write_guard_stub(
                skill_dir,
                {
                    "hookSpecificOutput": {
                        "permissionDecision": "deny",
                        "permissionDecisionReason": "should never run",
                    }
                },
            )
            os.remove(guard_path)
            result = _run_v1(tmp_dir, skill_dir, None, "bash", {"command": "ls"})
            assert result.returncode == 0, result.stderr
            assert result.stdout == "ALLOWED"

    def test_v1_records_argv_and_stdin(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            skill_dir = os.path.join(tmp_dir, "skill")
            record_path = os.path.join(tmp_dir, "record.json")
            _write_recording_stub(skill_dir, {}, record_path)
            result = _run_v1(
                tmp_dir, skill_dir, "programmer", "bash", {"command": "ls"}
            )
            assert result.returncode == 0, result.stderr
            assert result.stdout == "ALLOWED"
            with open(record_path) as f:
                record = json.load(f)
            assert record["argv"] == ["oc"]
            assert record["stdin"] == {
                "tool": "bash",
                "args": {"command": "ls"},
                "cwd": "/tmp/work",
                "role": "programmer",
            }

    def test_v2_records_argv_and_stdin(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            skill_dir = os.path.join(tmp_dir, "skill")
            record_path = os.path.join(tmp_dir, "record.json")
            _write_recording_stub(skill_dir, {}, record_path)
            result = _run_v2(
                tmp_dir,
                skill_dir,
                "code-reviewer",
                "edit",
                {"filePath": "a.py", "oldString": "x", "newString": "y"},
            )
            assert result.returncode == 0, result.stderr
            assert result.stdout == "ALLOWED"
            with open(record_path) as f:
                record = json.load(f)
            assert record["argv"] == ["oc"]
            assert record["stdin"] == {
                "tool": "edit",
                "args": {"filePath": "a.py", "oldString": "x", "newString": "y"},
                "cwd": "/tmp/work",
                "role": "code-reviewer",
            }

    def test_v1_no_role_allows_and_never_invokes_stub(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            skill_dir = os.path.join(tmp_dir, "skill")
            record_path = os.path.join(tmp_dir, "record.json")
            _write_recording_stub(
                skill_dir,
                {
                    "hookSpecificOutput": {
                        "permissionDecision": "deny",
                        "permissionDecisionReason": "should never run",
                    }
                },
                record_path,
            )
            result = _run_v1(tmp_dir, skill_dir, None, "bash", {"command": "rm -rf /"})
            assert result.returncode == 0, result.stderr
            assert result.stdout == "ALLOWED"
            assert not os.path.exists(record_path), "guard stub was invoked with no role set"

    def test_v2_no_role_allows_and_never_invokes_stub(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            skill_dir = os.path.join(tmp_dir, "skill")
            record_path = os.path.join(tmp_dir, "record.json")
            _write_recording_stub(
                skill_dir,
                {
                    "hookSpecificOutput": {
                        "permissionDecision": "deny",
                        "permissionDecisionReason": "should never run",
                    }
                },
                record_path,
            )
            result = _run_v2(
                tmp_dir, skill_dir, None, "bash", {"command": "rm -rf /"}
            )
            assert result.returncode == 0, result.stderr
            assert result.stdout == "ALLOWED"
            assert not os.path.exists(record_path), "guard stub was invoked with no role set"

    def test_v2_denies_and_throws(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            skill_dir = os.path.join(tmp_dir, "skill")
            _write_guard_stub(
                skill_dir,
                {
                    "hookSpecificOutput": {
                        "permissionDecision": "deny",
                        "permissionDecisionReason": "blocked edit",
                    }
                },
            )
            result = _run_v2(
                tmp_dir,
                skill_dir,
                "code-reviewer",
                "edit",
                {"filePath": "a.py", "oldString": "x", "newString": "y"},
            )
            assert result.returncode == 0, result.stderr
            assert result.stdout == "DENIED:blocked edit"


if __name__ == "__main__":
    unittest.main()
