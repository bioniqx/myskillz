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
    os.path.join(TESTS_DIR, "..", "..", "oc-dev-team", "opencode", "plugins")
)
V2_PATH = os.path.join(PLUGIN_DIR, "oc-devteam-guard.v2.js")

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
    "oc-programmer",
    "oc-code-reviewer",
    "oc-spot-reviewer",
    "oc-investigator",
    "oc-team-leader",
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
    guard_path = os.path.join(scripts_dir, "oc_guard.py")
    with open(guard_path, "w") as f:
        f.write(
            "import json\nimport sys\n\nsys.stdin.read()\nprint(json.dumps(%s))\n"
            % json.dumps(decision)
        )
    return guard_path


def _write_recording_stub(skill_dir, decision, record_path):
    scripts_dir = os.path.join(skill_dir, "scripts")
    os.makedirs(scripts_dir, exist_ok=True)
    guard_path = os.path.join(scripts_dir, "oc_guard.py")
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
    guard_path = os.path.join(scripts_dir, "oc_guard.py")
    with open(guard_path, "w") as f:
        f.write("import sys\n\nsys.stdin.read()\nsys.exit(1)\n")
    return guard_path


def _load_plugin_source(path, skill_dir):
    with open(path) as f:
        source = f.read()
    return source.replace("{{SKILL_DIR}}", skill_dir)


def _run_v2(tmp_dir, skill_dir, agent, tool, args, calls=1, delayed_hook=False, env_role=None):
    # Drives the plugin the way the real v2 binary does: import the default export ({id, setup}), call
    # setup(api) with a fake api whose tool.hook(name, fn) records the hook, then invoke that hook with the
    # real event shape {tool, sessionID, agent, messageID, id, input}. With delayed_hook the fake api
    # registers the hook only after a timer and returns a promise, so a plugin that does not await the
    # registration has no hook yet when setup() resolves. env_role sets DEVTEAM_ROLE, which the plugin
    # must ignore.
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
    env = dict(os.environ)
    env.pop("DEVTEAM_ROLE", None)
    if env_role:
        env["DEVTEAM_ROLE"] = env_role
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
        # The module must resolve plugin paths off its own __file__, not the process cwd: run this same
        # test file from an unrelated cwd and confirm it still finds and loads the real plugin source.
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
        self.assertIn("id: \"oc-devteam-guard\"", source)
        self.assertIn("setup:", source)
        self.assertIn("api.tool.hook", source)

    def test_v2_reads_the_role_only_from_the_event(self):
        with open(V2_PATH) as f:
            source = f.read()
        self.assertNotIn("process.env", source)

    def test_plugin_dir_holds_only_the_v2_plugin(self):
        self.assertEqual(sorted(os.listdir(PLUGIN_DIR)), ["oc-devteam-guard.v2.js"])

    def test_v2_source_uses_async_spawn_and_awaits_hook(self):
        with open(V2_PATH) as f:
            source = f.read()
        self.assertNotIn("spawnSync", source)
        self.assertIn("spawn(", source)
        self.assertIn("await api.tool.hook", source)

    @NEEDS_NODE
    def test_v2_records_argv_and_stdin(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            skill_dir = os.path.join(tmp_dir, "skill")
            record_path = os.path.join(tmp_dir, "record.json")
            _write_recording_stub(skill_dir, {}, record_path)
            result = _run_v2(
                tmp_dir,
                skill_dir,
                "oc-code-reviewer",
                "edit",
                {"path": "/w/a.py", "oldString": "x", "newString": "y"},
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "ALLOWED")
            with open(record_path) as f:
                record = json.load(f)
            self.assertEqual(record["argv"], ["oc"])
            expected_cwd = os.path.realpath(os.path.join(tmp_dir, "work"))
            self.assertEqual(record["stdin"], {
                "tool": "edit",
                "args": {"path": "/w/a.py", "oldString": "x", "newString": "y"},
                "cwd": expected_cwd,
                "role": "code-reviewer",
            })

    @NEEDS_NODE
    def test_v2_every_devteam_agent_is_a_role(self):
        for agent in DEVTEAM_AGENTS:
            with self.subTest(agent=agent), tempfile.TemporaryDirectory() as tmp_dir:
                skill_dir = os.path.join(tmp_dir, "skill")
                record_path = os.path.join(tmp_dir, "record.json")
                _write_recording_stub(skill_dir, {}, record_path)
                result = _run_v2(tmp_dir, skill_dir, agent, "shell", {"command": "ls", "workdir": "/w"})
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, "ALLOWED")
                with open(record_path) as f:
                    record = json.load(f)
                self.assertEqual(record["stdin"]["role"], agent[len("oc-"):])
                self.assertEqual(record["stdin"]["tool"], "shell")
                self.assertEqual(record["stdin"]["args"], {"command": "ls", "workdir": "/w"})

    @NEEDS_NODE
    def test_v2_other_agents_are_never_checked(self):
        for agent in ["general", "build", "programmer-lite", "programmer", "team-leader", None]:
            with self.subTest(agent=agent), tempfile.TemporaryDirectory() as tmp_dir:
                skill_dir = os.path.join(tmp_dir, "skill")
                record_path = os.path.join(tmp_dir, "record.json")
                _write_recording_stub(skill_dir, DENY, record_path)
                result = _run_v2(tmp_dir, skill_dir, agent, "shell", {"command": "rm -rf /"})
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, "ALLOWED")
                self.assertFalse(os.path.exists(record_path), "guard spawned for %r" % agent)

    @NEEDS_NODE
    def test_v2_ignores_the_devteam_role_env(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            skill_dir = os.path.join(tmp_dir, "skill")
            record_path = os.path.join(tmp_dir, "record.json")
            _write_recording_stub(skill_dir, DENY, record_path)
            result = _run_v2(tmp_dir, skill_dir, "general", "shell", {"command": "rm -rf /"},
                             env_role="code-reviewer")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "ALLOWED")
            self.assertFalse(os.path.exists(record_path))

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
            result = _run_v2(tmp_dir, skill_dir, "oc-code-reviewer", "edit",
                             {"path": "a.py", "oldString": "x", "newString": "y"})
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "DENIED:blocked edit")

    @NEEDS_NODE
    def test_v2_skips_unguarded_tools(self):
        for tool in UNGUARDED_TOOLS:
            with self.subTest(tool=tool), tempfile.TemporaryDirectory() as tmp_dir:
                skill_dir = os.path.join(tmp_dir, "skill")
                record_path = os.path.join(tmp_dir, "record.json")
                _write_recording_stub(skill_dir, DENY, record_path)
                result = _run_v2(tmp_dir, skill_dir, "oc-code-reviewer", tool, {"path": "a.py"})
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, "ALLOWED")
                self.assertFalse(os.path.exists(record_path), "guard spawned for " + tool)

    @NEEDS_NODE
    def test_v2_guards_every_write_and_shell_tool(self):
        for tool in GUARDED_TOOLS:
            with self.subTest(tool=tool), tempfile.TemporaryDirectory() as tmp_dir:
                skill_dir = os.path.join(tmp_dir, "skill")
                _write_guard_stub(skill_dir, DENY)
                result = _run_v2(tmp_dir, skill_dir, "oc-code-reviewer", tool, {"command": "ls"})
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, "DENIED:guarded")

    @NEEDS_NODE
    def test_v2_denies_nested_dispatch_from_devteam_agents(self):
        for agent in DEVTEAM_AGENTS:
            for tool in ["subagent", "task"]:
                with self.subTest(agent=agent, tool=tool), tempfile.TemporaryDirectory() as tmp_dir:
                    skill_dir = os.path.join(tmp_dir, "skill")
                    record_path = os.path.join(tmp_dir, "record.json")
                    _write_recording_stub(skill_dir, {}, record_path)
                    result = _run_v2(tmp_dir, skill_dir, agent, tool, {"prompt": "go"})
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertTrue(result.stdout.startswith("DENIED:"), result.stdout)
                    self.assertIn("subagent", result.stdout)

    @NEEDS_NODE
    def test_v2_allows_dispatch_from_other_agents(self):
        for agent in ["build", "general", None]:
            with self.subTest(agent=agent), tempfile.TemporaryDirectory() as tmp_dir:
                skill_dir = os.path.join(tmp_dir, "skill")
                _write_guard_stub(skill_dir, DENY)
                result = _run_v2(tmp_dir, skill_dir, agent, "subagent", {"prompt": "go"})
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, "ALLOWED")

    @NEEDS_NODE
    def test_v2_awaits_hook_registration(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            skill_dir = os.path.join(tmp_dir, "skill")
            _write_guard_stub(skill_dir, DENY)
            result = _run_v2(tmp_dir, skill_dir, "oc-code-reviewer", "edit",
                             {"path": "a.py", "oldString": "x", "newString": "y"}, delayed_hook=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "DENIED:guarded")

    @NEEDS_NODE
    def test_v2_warns_fail_open_once(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            skill_dir = os.path.join(tmp_dir, "skill")
            _write_failing_stub(skill_dir)
            result = _run_v2(tmp_dir, skill_dir, "oc-code-reviewer", "edit", {"path": "a.py"}, calls=2)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "ALLOWED\nALLOWED")
            self.assertEqual(result.stderr.count("failing open"), 1, result.stderr)


if __name__ == "__main__":
    unittest.main()
