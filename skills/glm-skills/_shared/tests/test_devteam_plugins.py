import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.abspath(
    os.path.join(TESTS_DIR, "..", "..", "dev-team-glm", "opencode", "plugins")
)
V1_PATH = os.path.join(PLUGIN_DIR, "devteam-guard.v1.js")
V2_PATH = os.path.join(PLUGIN_DIR, "devteam-guard.v2.js")

NEEDS_NODE = unittest.skipUnless(shutil.which("node"), "node not installed")

GUARDED_TOOLS = [
    "write",
    "edit",
    "patch",
    "apply_patch",
    "multiedit",
    "shell",
    "bash",
    "execute",
    "batch",
]
UNGUARDED_TOOLS = ["read", "glob", "grep", "todowrite", "webfetch", "skill", "question"]
DEVTEAM_AGENTS = [
    "programmer",
    "programmer-lite",
    "code-reviewer",
    "spot-reviewer",
    "investigator",
    "team-leader",
]
DENY = {
    "hookSpecificOutput": {
        "permissionDecision": "deny",
        "permissionDecisionReason": "guarded",
    }
}


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


def _write_failing_stub(skill_dir):
    scripts_dir = os.path.join(skill_dir, "scripts")
    os.makedirs(scripts_dir, exist_ok=True)
    guard_path = os.path.join(scripts_dir, "guard.py")
    with open(guard_path, "w") as f:
        f.write("import sys\n\nsys.stdin.read()\nsys.exit(1)\n")
    return guard_path


def _load_plugin_source(path, skill_dir):
    with open(path) as f:
        source = f.read()
    return source.replace("{{SKILL_DIR}}", skill_dir)


def _node_env(role):
    env = dict(os.environ)
    if role is None:
        env.pop("DEVTEAM_ROLE", None)
    else:
        env["DEVTEAM_ROLE"] = role
    return env


def _run_v1(tmp_dir, skill_dir, role, tool, args, calls=1):
    source = _load_plugin_source(V1_PATH, skill_dir)
    plugin_path = os.path.join(tmp_dir, "plugin.mjs")
    with open(plugin_path, "w") as f:
        f.write(source)
    driver_path = os.path.join(tmp_dir, "driver.mjs")
    driver = textwrap.dedent(
        """\
        import { DevteamGuard } from "%s";
        const hooks = await DevteamGuard({ directory: "/tmp/work" });
        const out = [];
        for (let i = 0; i < %d; i++) {
          try {
            await hooks["tool.execute.before"](
              { tool: "%s", sessionID: "s", callID: "c" },
              { args: %s }
            );
            out.push("ALLOWED");
          } catch (err) {
            out.push("DENIED:" + err.message);
          }
        }
        process.stdout.write(out.join("\\n"));
        """
    ) % (plugin_path, calls, tool, json.dumps(args))
    with open(driver_path, "w") as f:
        f.write(driver)
    return subprocess.run(
        ["node", driver_path],
        capture_output=True,
        text=True,
        env=_node_env(role),
        timeout=30,
    )


def _run_v2(tmp_dir, skill_dir, role, tool, args, agent="a", calls=1, delayed_hook=False):
    # Drives the plugin the way the real v2 binary does. It imports the
    # default export ({id, setup}) and calls setup(api) with a fake api
    # whose tool.hook(name, fn) records the registered hook. Then it invokes
    # that hook with the real event shape {tool, sessionID, agent, messageID,
    # id, input}. With delayed_hook the fake api registers the hook only
    # after a timer and returns a promise, so a plugin that does not await
    # the registration has no hook yet when setup() resolves.
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
        const delayed = %s;
        const hooks = {};
        const api = {
          tool: {
            hook: (name, fn) => {
              if (!delayed) {
                hooks[name] = fn;
                return undefined;
              }
              return new Promise((resolve) => {
                setTimeout(() => {
                  hooks[name] = fn;
                  resolve();
                }, 20);
              });
            },
          },
        };
        await plugin.setup(api);
        if (typeof hooks["execute.before"] !== "function") {
          throw new Error("plugin did not register an execute.before hook");
        }
        const out = [];
        for (let i = 0; i < %d; i++) {
          try {
            await hooks["execute.before"]({
              tool: "%s",
              sessionID: "s",
              agent: %s,
              messageID: "m",
              id: "c",
              input: %s,
            });
            out.push("ALLOWED");
          } catch (err) {
            out.push("DENIED:" + err.message);
          }
        }
        process.stdout.write(out.join("\\n"));
        """
    ) % (
        plugin_path,
        "true" if delayed_hook else "false",
        calls,
        tool,
        json.dumps(agent),
        json.dumps(args),
    )
    with open(driver_path, "w") as f:
        f.write(driver)
    return subprocess.run(
        ["node", driver_path],
        capture_output=True,
        text=True,
        env=_node_env(role),
        timeout=30,
        cwd=work_dir,
    )


class TestDevteamPlugins(unittest.TestCase):
    def test_plugin_paths_resolve_from_file_not_cwd(self):
        # The module must resolve plugin paths off its own __file__, not the
        # process cwd. Prove it by running this same test file as a
        # subprocess from an unrelated cwd (a tmp dir with no skills/ tree)
        # and confirming it still finds and loads the real plugin sources.
        self.assertTrue(os.path.isfile(V1_PATH), V1_PATH)
        self.assertTrue(os.path.isfile(V2_PATH), V2_PATH)
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
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_v2_shape_has_no_plugin_package(self):
        with open(V2_PATH) as f:
            source = f.read()
        self.assertNotIn("@opencode/plugin", source)
        self.assertNotIn("Plugin.define", source)
        self.assertNotIn("tool.execute.before", source)
        self.assertNotIn("ctx.directory", source)
        self.assertIn("id: \"devteam-guard\"", source)
        self.assertIn("setup:", source)
        self.assertIn("api.tool.hook", source)

    @NEEDS_NODE
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
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "DENIED:blocked command")

    @NEEDS_NODE
    def test_v1_allows_when_decision_is_allow(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            skill_dir = os.path.join(tmp_dir, "skill")
            _write_guard_stub(skill_dir, {})
            result = _run_v1(tmp_dir, skill_dir, "programmer", "bash", {"command": "ls"})
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "ALLOWED")

    @NEEDS_NODE
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
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "ALLOWED")

    @NEEDS_NODE
    def test_v1_records_argv_and_stdin(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            skill_dir = os.path.join(tmp_dir, "skill")
            record_path = os.path.join(tmp_dir, "record.json")
            _write_recording_stub(skill_dir, {}, record_path)
            result = _run_v1(
                tmp_dir, skill_dir, "programmer", "bash", {"command": "ls"}
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "ALLOWED")
            with open(record_path) as f:
                record = json.load(f)
            self.assertEqual(record["argv"], ["oc"])
            self.assertEqual(record["stdin"], {
                "tool": "bash",
                "args": {"command": "ls"},
                "cwd": "/tmp/work",
                "role": "programmer",
            })

    @NEEDS_NODE
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
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "ALLOWED")
            with open(record_path) as f:
                record = json.load(f)
            self.assertEqual(record["argv"], ["oc"])
            expected_cwd = os.path.realpath(os.path.join(tmp_dir, "work"))
            self.assertEqual(record["stdin"], {
                "tool": "edit",
                "args": {"filePath": "a.py", "oldString": "x", "newString": "y"},
                "cwd": expected_cwd,
                "role": "code-reviewer",
            })

    @NEEDS_NODE
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
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "ALLOWED")
            self.assertFalse(os.path.exists(record_path), "guard stub was invoked with no role set")

    @NEEDS_NODE
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
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "ALLOWED")
            self.assertFalse(os.path.exists(record_path), "guard stub was invoked with no role set")

    @NEEDS_NODE
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
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "DENIED:blocked edit")

    @NEEDS_NODE
    def test_v1_skips_unguarded_tools(self):
        for tool in UNGUARDED_TOOLS:
            with self.subTest(tool=tool), tempfile.TemporaryDirectory() as tmp_dir:
                skill_dir = os.path.join(tmp_dir, "skill")
                record_path = os.path.join(tmp_dir, "record.json")
                _write_recording_stub(skill_dir, DENY, record_path)
                result = _run_v1(
                    tmp_dir, skill_dir, "programmer", tool, {"filePath": "a.py"}
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, "ALLOWED")
                self.assertFalse(
                    os.path.exists(record_path), "guard spawned for " + tool
                )

    @NEEDS_NODE
    def test_v1_guards_every_write_and_shell_tool(self):
        for tool in GUARDED_TOOLS:
            with self.subTest(tool=tool), tempfile.TemporaryDirectory() as tmp_dir:
                skill_dir = os.path.join(tmp_dir, "skill")
                _write_guard_stub(skill_dir, DENY)
                result = _run_v1(
                    tmp_dir, skill_dir, "programmer", tool, {"command": "ls"}
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, "DENIED:guarded")

    @NEEDS_NODE
    def test_v1_warns_fail_open_once(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            skill_dir = os.path.join(tmp_dir, "skill")
            _write_failing_stub(skill_dir)
            result = _run_v1(
                tmp_dir, skill_dir, "programmer", "bash", {"command": "ls"}, calls=2
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "ALLOWED\nALLOWED")
            self.assertEqual(result.stderr.count("failing open"), 1, result.stderr)

    def test_v1_source_uses_async_spawn(self):
        with open(V1_PATH) as f:
            source = f.read()
        self.assertNotIn("spawnSync", source)
        self.assertIn("spawn(", source)

    @NEEDS_NODE
    def test_v2_skips_unguarded_tools(self):
        for tool in UNGUARDED_TOOLS:
            with self.subTest(tool=tool), tempfile.TemporaryDirectory() as tmp_dir:
                skill_dir = os.path.join(tmp_dir, "skill")
                record_path = os.path.join(tmp_dir, "record.json")
                _write_recording_stub(skill_dir, DENY, record_path)
                result = _run_v2(
                    tmp_dir, skill_dir, "code-reviewer", tool, {"path": "a.py"}
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, "ALLOWED")
                self.assertFalse(
                    os.path.exists(record_path), "guard spawned for " + tool
                )

    @NEEDS_NODE
    def test_v2_guards_every_write_and_shell_tool(self):
        for tool in GUARDED_TOOLS:
            with self.subTest(tool=tool), tempfile.TemporaryDirectory() as tmp_dir:
                skill_dir = os.path.join(tmp_dir, "skill")
                _write_guard_stub(skill_dir, DENY)
                result = _run_v2(
                    tmp_dir, skill_dir, "code-reviewer", tool, {"command": "ls"}
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, "DENIED:guarded")

    @NEEDS_NODE
    def test_v2_uses_event_agent_as_role_when_env_unset(self):
        for agent in DEVTEAM_AGENTS:
            with self.subTest(agent=agent), tempfile.TemporaryDirectory() as tmp_dir:
                skill_dir = os.path.join(tmp_dir, "skill")
                record_path = os.path.join(tmp_dir, "record.json")
                _write_recording_stub(skill_dir, {}, record_path)
                result = _run_v2(
                    tmp_dir, skill_dir, None, "shell", {"command": "ls"}, agent=agent
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, "ALLOWED")
                self.assertTrue(os.path.exists(record_path), "guard not spawned for " + agent)
                with open(record_path) as f:
                    record = json.load(f)
                self.assertEqual(record["stdin"]["role"], agent)
                self.assertEqual(record["stdin"]["tool"], "shell")
                self.assertEqual(record["stdin"]["args"], {"command": "ls"})

    @NEEDS_NODE
    def test_v2_env_role_wins_over_event_agent(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            skill_dir = os.path.join(tmp_dir, "skill")
            record_path = os.path.join(tmp_dir, "record.json")
            _write_recording_stub(skill_dir, {}, record_path)
            result = _run_v2(
                tmp_dir,
                skill_dir,
                "code-reviewer",
                "shell",
                {"command": "ls"},
                agent="programmer",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            with open(record_path) as f:
                record = json.load(f)
            self.assertEqual(record["stdin"]["role"], "code-reviewer")

    @NEEDS_NODE
    def test_v2_ignores_non_devteam_agent(self):
        for agent in ["general", "build", "a"]:
            with self.subTest(agent=agent), tempfile.TemporaryDirectory() as tmp_dir:
                skill_dir = os.path.join(tmp_dir, "skill")
                record_path = os.path.join(tmp_dir, "record.json")
                _write_recording_stub(skill_dir, DENY, record_path)
                result = _run_v2(
                    tmp_dir, skill_dir, None, "shell", {"command": "rm -rf /"}, agent=agent
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, "ALLOWED")
                self.assertFalse(os.path.exists(record_path), "guard spawned for " + agent)

    @NEEDS_NODE
    def test_v2_awaits_hook_registration(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            skill_dir = os.path.join(tmp_dir, "skill")
            _write_guard_stub(skill_dir, DENY)
            result = _run_v2(
                tmp_dir,
                skill_dir,
                "code-reviewer",
                "edit",
                {"path": "a.py", "oldString": "x", "newString": "y"},
                delayed_hook=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "DENIED:guarded")

    @NEEDS_NODE
    def test_v2_warns_fail_open_once(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            skill_dir = os.path.join(tmp_dir, "skill")
            _write_failing_stub(skill_dir)
            result = _run_v2(
                tmp_dir, skill_dir, "code-reviewer", "edit", {"path": "a.py"}, calls=2
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "ALLOWED\nALLOWED")
            self.assertEqual(result.stderr.count("failing open"), 1, result.stderr)

    def test_v2_source_uses_async_spawn_and_awaits_hook(self):
        with open(V2_PATH) as f:
            source = f.read()
        self.assertNotIn("spawnSync", source)
        self.assertIn("spawn(", source)
        self.assertIn("await api.tool.hook", source)

if __name__ == "__main__":
    unittest.main()
