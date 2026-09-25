import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(TESTS_DIR, "..", "..", "..", ".."))
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
    # Drives the plugin the way the real v2.0.16 binary does: import its
    # default export ({id, setup}), call setup(api) with a fake api whose
    # tool.hook(name, fn) records the registered hook, then invoke that hook
    # with the real event shape {tool, sessionID, agent, messageID, id,
    # input}.
    source = _load_plugin_source(V2_PATH, skill_dir)
    plugin_path = os.path.join(tmp_dir, "plugin.mjs")
    with open(plugin_path, "w") as f:
        f.write(source)
    work_dir = os.path.join(tmp_dir, "work")
    os.makedirs(work_dir, exist_ok=True)
    driver_path = os.path.join(tmp_dir, "driver.mjs")
    driver = textwrap.dedent(
        """\
        import plugin from "%s";
        if (typeof plugin.id !== "string" || plugin.id.length === 0) {
          throw new Error("plugin.id must be a non-empty string");
        }
        if (typeof plugin.setup !== "function") {
          throw new Error("plugin.setup must be a function");
        }
        const hooks = {};
        const api = {
          tool: {
            hook: (name, fn) => {
              hooks[name] = fn;
            },
          },
        };
        await plugin.setup(api);
        if (typeof hooks["execute.before"] !== "function") {
          throw new Error("plugin did not register an execute.before hook");
        }
        try {
          await hooks["execute.before"]({
            tool: "%s",
            sessionID: "s",
            agent: "a",
            messageID: "m",
            id: "c",
            input: %s,
          });
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
        ["node", driver_path],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
        cwd=work_dir,
    )


class TestDevteamPlugins(unittest.TestCase):
    def test_plugin_paths_resolve_from_file_not_cwd(self):
        # The module must resolve plugin paths off its own __file__, not the
        # process cwd. Prove it by running this same test file as a
        # subprocess from an unrelated cwd (a tmp dir with no skills/ tree)
        # and confirming it still finds and loads the real plugin sources.
        assert os.path.isfile(V1_PATH), V1_PATH
        assert os.path.isfile(V2_PATH), V2_PATH
        with tempfile.TemporaryDirectory() as unrelated_cwd:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "unittest",
                    "discover",
                    "-s",
                    TESTS_DIR,
                    "-t",
                    TESTS_DIR,
                    "-p",
                    os.path.basename(__file__),
                    "-k",
                    "test_v2_shape_has_no_plugin_package",
                ],
                cwd=unrelated_cwd,
                capture_output=True,
                text=True,
                timeout=60,
            )
            assert result.returncode == 0, result.stdout + result.stderr

    def test_v2_shape_has_no_plugin_package(self):
        with open(V2_PATH) as f:
            source = f.read()
        assert "@opencode/plugin" not in source
        assert "Plugin.define" not in source
        assert "tool.execute.before" not in source
        assert "ctx.directory" not in source
        assert "id: \"devteam-guard\"" in source
        assert "setup:" in source
        assert "api.tool.hook" in source

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
            expected_cwd = os.path.realpath(os.path.join(tmp_dir, "work"))
            assert record["stdin"] == {
                "tool": "edit",
                "args": {"filePath": "a.py", "oldString": "x", "newString": "y"},
                "cwd": expected_cwd,
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
