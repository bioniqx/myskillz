"""OpenCode v2 contract tests.

The harness-surface checks and the fake-provider self-tests always run. The real-binary classes
run only with OC_CONTRACT=1: they drive the `opencode` v2 binary on PATH against fake_provider.py
inside a sandboxed HOME/XDG_* tree and block all non-localhost network with macOS sandbox-exec
(skipped without it unless OC_CONTRACT_NO_SANDBOX=1). They check what OpenCode v2 does for a
dispatched agent and that installed skills, agents and commands are discovered.
"""

import base64
import contextlib
import io
import json
import os
import re
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
SHARED = os.path.dirname(HERE)
ROOT = os.path.dirname(SHARED)
for _path in (HERE, SHARED):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import oc_harness  # noqa: E402
from fake_provider import FakeProvider, fill_args, message_texts, tool_names  # noqa: E402

REMOVED = ("PROVIDER", "MODELS", "EFFORTS", "config_snippet", "WEBSEARCH_NOTE", "THROTTLE_CODES",
           "is_throttle_event", "RUN_FLAGS", "check_run_flags", "build_run_cmd", "run_lanes",
           "lane_results", "lane_stall", "STALL_BY_ROLE", "STANDALONE_RACE", "V1_DB_RACES",
           "RACE_RETRIES", "probe_effort", "reasoning_tokens", "PROBE_AGENT", "PROBE_BRIEF")
KEPT = ("detect", "harness", "major", "parse_frontmatter", "render_agent", "render_command",
        "dispatch_line", "install", "check", "skill_name", "main")
SKILL_MD = "---\nname: demo\ndescription: demo skill\n---\nBody\n"


class HarnessSurfaceTest(unittest.TestCase):
    def _main(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = oc_harness.main(argv)
        return code, out.getvalue() + err.getvalue()

    def _tmp(self):
        tmp = tempfile.mkdtemp(prefix="oc-surface-")
        self.addCleanup(shutil.rmtree, tmp, True)
        return tmp

    def test_removed_names_are_gone(self):
        self.assertEqual([n for n in REMOVED if hasattr(oc_harness, n)], [])

    def test_kept_functions_remain(self):
        self.assertEqual([n for n in KEPT if not callable(getattr(oc_harness, n, None))], [])

    def test_source_has_no_process_or_provider_code(self):
        with open(oc_harness.__file__) as fh:
            src = fh.read()
        for needle in ("Popen", "killpg", '"run"'):
            with self.subTest(needle=needle):
                self.assertNotIn(needle, src)

    def test_help_lists_only_kept_subcommands(self):
        code, text = self._main(["--help"])
        self.assertEqual(code, 0)
        self.assertIn("{detect,install,check,harness}", text)

    def test_lane_and_snippet_subcommands_rejected(self):
        for argv in (["snippet", "2"], ["result", self._tmp()]):
            with self.subTest(argv=argv[0]):
                code, text = self._main(argv)
                self.assertEqual(code, 2, text)
                self.assertIn("invalid choice", text)

    def test_render_agent_writes_no_model_or_effort(self):
        src = ("---\ndescription: probe\nmodel: flash\neffort: high\naccess: read\n"
               "bash: false\nweb: false\n---\nBody text\n")
        text = oc_harness.render_agent(src, 2)
        for key in ("model:", "variant:", "reasoningEffort:"):
            with self.subTest(key=key):
                self.assertNotRegex(text, r"(?m)^\s*%s" % key)
        self.assertIn("\nmode: subagent\n", text)
        self.assertIn("\n  execute: deny\n", text)
        self.assertTrue(text.endswith("Body text"), text)

    def test_check_spawns_no_run_probe(self):
        tmp = self._tmp()
        skill = os.path.join(tmp, "demo")
        os.makedirs(skill)
        with open(os.path.join(skill, "SKILL.md"), "w") as fh:
            fh.write(SKILL_MD)
        home = os.path.join(tmp, "home")
        marker_dir = os.path.join(home, ".config", "opencode", "skills", "demo")
        os.makedirs(marker_dir)
        with open(os.path.join(marker_dir, ".oc-major"), "w") as fh:
            fh.write("2")
        with mock.patch.object(oc_harness, "detect", return_value=2), \
                mock.patch.object(oc_harness.subprocess, "run", side_effect=AssertionError("spawned opencode")):
            lines = oc_harness.check(skill, home)
        self.assertEqual(lines, ["INSTALLED: demo (major 2)"])


SHELL_TOOL = [{
    "type": "function",
    "function": {
        "name": "shell",
        "parameters": {
            "type": "object",
            "properties": {"command": {"type": "string"}, "timeout": {"type": "number"}},
            "required": ["command"],
        },
    },
}]


def _post(url: str, body: dict) -> tuple:
    req = urllib.request.Request(url + "/chat/completions", data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status, resp.read().decode("utf-8")


class FakeProviderTest(unittest.TestCase):
    def setUp(self):
        self.fake = FakeProvider()
        self.url = self.fake.start()

    def tearDown(self):
        self.fake.stop()

    def test_default_json_reply_and_log(self):
        status, text = _post(self.url, {"model": "fake-model",
                                        "messages": [{"role": "user", "content": "hi there"}]})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(text)["choices"][0]["message"]["content"], "ok")
        self.assertEqual(message_texts(self.fake.bodies()[0], "user"), ["hi there"])

    def test_stream_tool_call_picks_offered_name(self):
        self.fake.rules = [{"fresh": True, "tool": ["bash", "shell"], "args": {"command": "echo hi"}}]
        status, text = _post(self.url, {
            "model": "fake-model", "stream": True, "tools": SHELL_TOOL,
            "messages": [{"role": "user", "content": [{"type": "text", "text": "run"}]}],
        })
        self.assertEqual(status, 200)
        chunks = [json.loads(line[6:]) for line in text.splitlines() if line.startswith("data: {")]
        call = chunks[0]["choices"][0]["delta"]["tool_calls"][0]["function"]
        self.assertEqual(call["name"], "shell")
        self.assertEqual(json.loads(call["arguments"]), {"command": "echo hi"})
        self.assertEqual(chunks[-1]["choices"][0]["finish_reason"], "tool_calls")
        self.assertTrue(text.rstrip().endswith("data: [DONE]"))
        self.assertEqual(tool_names(self.fake.bodies()[0]), ["shell"])

    def test_fresh_rule_skipped_after_tool_result(self):
        self.fake.rules = [{"fresh": True, "tool": ["shell"], "args": {"command": "x"}}, {"text": "done"}]
        status, text = _post(self.url, {
            "model": "fake-model", "tools": SHELL_TOOL,
            "messages": [
                {"role": "user", "content": "run"},
                {"role": "assistant", "content": None, "tool_calls": [
                    {"id": "c1", "type": "function", "function": {"name": "shell", "arguments": "{}"}}]},
                {"role": "tool", "tool_call_id": "c1", "content": "x"},
            ],
        })
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(text)["choices"][0]["message"]["content"], "done")

    def test_auto_fill_from_schema(self):
        schema = {
            "type": "object",
            "properties": {"subagent_type": {"type": "string"}, "prompt": {"type": "string"},
                           "description": {"type": "string"}, "background": {"type": "boolean"}},
            "required": ["subagent_type", "prompt", "description", "background"],
        }
        args = fill_args(schema, {"agent": "contract-hidden", "prompt": "Reply with sub-done."})
        self.assertEqual(args, {"subagent_type": "contract-hidden", "prompt": "Reply with sub-done.",
                                "description": "contract", "background": False})

    def test_status_rule_returns_error(self):
        self.fake.rules = [{"match": "LIMIT", "status": 429,
                            "body": {"error": {"code": "rate_limit_exceeded", "message": "rate limited"}}}]
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            _post(self.url, {"model": "fake-model", "messages": [{"role": "user", "content": "LIMIT me"}]})
        self.assertEqual(ctx.exception.code, 429)
        self.assertIn("rate_limit_exceeded", ctx.exception.read().decode("utf-8"))
        ctx.exception.close()


ENABLED = os.environ.get("OC_CONTRACT") == "1"
NO_SANDBOX = os.environ.get("OC_CONTRACT_NO_SANDBOX") == "1"
SANDBOX_EXEC = shutil.which("sandbox-exec") or ""
SKIP_MSG = "set OC_CONTRACT=1 to run the real-binary OpenCode contract tests"
SANDBOX_PROFILE = (
    "(version 1)\n"
    "(allow default)\n"
    '(deny network-outbound (remote ip "*:*"))\n'
    '(allow network-outbound (remote ip "localhost:*"))\n'
)
# Tools a dispatched write/shell/web agent must be offered; render_agent denies `execute`, and v2
# drops a denied tool from the request.
DISPATCHED_TOOLS = {"edit", "glob", "grep", "read", "shell", "webfetch", "write"}
ABSENT_TOOLS = {"bash", "task", "todowrite", "apply_patch", "execute"}
V2_HOOK_KEYS = {"tool", "sessionID", "agent", "messageID", "id", "input"}
SKILLS = {"oc-brainstorming", "oc-dev-team", "oc-doc-generator", "oc-requirements-code-audit",
          "oc-systematic-debugging", "oc-writing-plans"}
AGENT_PATHS = ("/agent", "/api/agent")
COMMAND_PATHS = ("/command", "/api/command")
SKILL_PATHS = ("/skill", "/api/skill", "/experimental/skill")
SERVE_PASSWORD = "contract-pass"
SERVE_AUTH = "Basic " + base64.b64encode(("opencode:" + SERVE_PASSWORD).encode("ascii")).decode("ascii")
PARENT_MODEL = "fake-model"
OTHER_MODEL = "fake-model-b"
PROBE_MARKER = "PROBE-AGENT-MARKER-5C1D"
HIDDEN_MARKER = "HIDDEN-AGENT-MARKER-7F3A"
PROBE_AGENT_SRC = (
    "---\n"
    "description: contract probe agent\n"
    "access: write\n"
    "bash: true\n"
    "web: true\n"
    "---\n"
    "%s You are a contract probe. Call the tools you are offered, then answer briefly.\n" % PROBE_MARKER
)
HIDDEN_AGENT_SRC = (
    "---\n"
    "description: contract hidden subagent\n"
    "access: read\n"
    "bash: false\n"
    "web: false\n"
    "---\n"
    "%s Reply with sub-done.\n" % HIDDEN_MARKER
)
# v2 loads only a default export shaped {id, setup(api)}; a function default is silently ignored.
PLUGIN_JS = r"""import { appendFileSync } from "node:fs";

const LOG = process.env.CONTRACT_HOOK_LOG || "";
const DENY = (process.env.CONTRACT_DENY || "").split(",").filter(Boolean);

function record(entry) {
  if (LOG) appendFileSync(LOG, JSON.stringify(entry) + "\n");
  if (DENY.includes(entry.tool)) throw new Error("contract-deny: " + entry.tool);
}

export default {
  id: "contract-probe",
  setup: async (api) => {
    await api.tool.hook("execute.before", async (event) => {
      record({ hook: "execute.before", tool: event && event.tool,
               args: (event && event.input) || {}, keys: Object.keys(event || {}).sort() });
    });
  },
};
"""


def _xdg(home: str) -> dict:
    return {
        "HOME": home,
        "XDG_CONFIG_HOME": os.path.join(home, ".config"),
        "XDG_DATA_HOME": os.path.join(home, ".local", "share"),
        "XDG_CACHE_HOME": os.path.join(home, ".cache"),
        "XDG_STATE_HOME": os.path.join(home, ".local", "state"),
    }


def _v2_binary() -> str:
    found = shutil.which("opencode")
    if not found:
        return ""
    with tempfile.TemporaryDirectory(prefix="oc-detect-") as scratch:
        with mock.patch.dict(os.environ, _xdg(scratch)):
            major = oc_harness.detect(found)
    return os.path.abspath(found) if major == 2 else ""


def sandbox_env(home: str, bindir: str, tmp: str) -> dict:
    env = _xdg(home)
    env.update({
        "PATH": bindir + os.pathsep + os.environ.get("PATH", "/usr/bin:/bin"),
        "TMPDIR": tmp,
        "LANG": "en_US.UTF-8",
        "TERM": "dumb",
    })
    return env


def write_wrapper(bindir: str, real_bin: str, tmp: str) -> str:
    path = os.path.join(bindir, "opencode")
    if SANDBOX_EXEC:
        profile = os.path.join(tmp, "sandbox.sb")
        with open(profile, "w") as fh:
            fh.write(SANDBOX_PROFILE)
        line = 'exec %s -f %s %s "$@"\n' % (shlex.quote(SANDBOX_EXEC), shlex.quote(profile), shlex.quote(real_bin))
    else:
        line = 'exec %s "$@"\n' % shlex.quote(real_bin)
    with open(path, "w") as fh:
        fh.write("#!/bin/sh\n" + line)
    os.chmod(path, 0o755)
    return path


def fake_config(url: str) -> dict:
    return {
        "$schema": "https://opencode.ai/config.json",
        "enabled_providers": ["fake"],
        "provider": {
            "fake": {
                "npm": "@ai-sdk/openai-compatible",
                "name": "Fake",
                "options": {"baseURL": url, "apiKey": "fake-key"},
                "models": {PARENT_MODEL: {"name": PARENT_MODEL}, OTHER_MODEL: {"name": OTHER_MODEL}},
            }
        },
    }


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _names(data) -> set:
    if isinstance(data, dict):
        for key in ("data", "items", "agents", "commands", "skills"):
            if isinstance(data.get(key), list):
                return _names(data[key])
        return set(str(k) for k in data)
    names = set()
    for item in data or []:
        if isinstance(item, dict):
            name = item.get("name") or item.get("id")
            if name:
                names.add(str(name))
        elif isinstance(item, str):
            names.add(item)
    return names


@unittest.skipUnless(ENABLED, SKIP_MSG)
class V2ContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not SANDBOX_EXEC and not NO_SANDBOX:
            raise unittest.SkipTest("no sandbox-exec network sandbox; set OC_CONTRACT_NO_SANDBOX=1 to run unsandboxed")
        cls.real_bin = _v2_binary()
        if not cls.real_bin:
            raise unittest.SkipTest("no opencode v2 binary on PATH")

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="oc-contract-")
        self.home = os.path.join(self.tmp, "home")
        self.work = os.path.join(self.tmp, "work")
        self.bindir = os.path.join(self.tmp, "bin")
        self.config_dir = os.path.join(self.home, ".config", "opencode")
        for path in (self.work, self.bindir, os.path.join(self.config_dir, "agents"),
                     os.path.join(self.config_dir, "commands"), os.path.join(self.config_dir, "plugins")):
            os.makedirs(path)
        self.hook_log = os.path.join(self.tmp, "hook.jsonl")
        self.fake = FakeProvider()
        self.fake.start()
        self._write(os.path.join(self.config_dir, "opencode.json"), json.dumps(fake_config(self.fake.url), indent=2))
        self._write(os.path.join(self.config_dir, "plugins", "contract-probe.js"), PLUGIN_JS)
        self._write_agent("contract-probe", oc_harness.render_agent(PROBE_AGENT_SRC, 2))
        self._write_agent("contract-hidden", oc_harness.render_agent(HIDDEN_AGENT_SRC, 2))
        self.wrapper = write_wrapper(self.bindir, self.real_bin, self.tmp)
        self.env = sandbox_env(self.home, self.bindir, self.tmp)
        self.env["CONTRACT_HOOK_LOG"] = self.hook_log

    def tearDown(self):
        self.fake.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write(self, path, text):
        with open(path, "w") as fh:
            fh.write(text)

    def _write_agent(self, name, text):
        self._write(os.path.join(self.config_dir, "agents", name + ".md"), text)

    def _run(self, brief, model=PARENT_MODEL, extra_env=None, timeout=300):
        # Only this test starts a parent session headlessly; the skills themselves never spawn opencode.
        cmd = [self.wrapper, "run", "--standalone", "--model", "fake/" + model, "--format", "json", "--auto"]
        env = dict(self.env)
        env["PWD"] = self.work
        env.update(extra_env or {})
        return subprocess.run(cmd, input=brief, capture_output=True, text=True, timeout=timeout,
                              cwd=self.work, env=env)

    def _dispatch_rules(self, agent, child_rules):
        # Child requests carry the agent's marker in their system prompt; parent requests never do.
        # The parent dispatches in the foreground so the headless run waits for the child.
        return list(child_rules) + [
            {"fresh": True, "tool": ["subagent"],
             "fill": {"agent": agent, "prompt": "Do the contract task.", "message": "Do the contract task.",
                      "description": "contract dispatch", "background": False}},
            {"text": "done"},
        ]

    def _child_bodies(self, marker):
        return [b for b in self.fake.bodies() if any(marker in t for t in message_texts(b, "system"))]

    def _hooks(self):
        if not os.path.isfile(self.hook_log):
            return []
        with open(self.hook_log) as fh:
            return [json.loads(line) for line in fh if line.strip()]

    def _shell_rule(self, command):
        return {"match": PROBE_MARKER, "fresh": True, "tool": ["shell"],
                "fill": {"command": command, "workdir": self.work, "timeout": 60000,
                         "background": False, "description": "contract marker"}}

    def _tail(self, proc):
        return "stdout: %s\nstderr: %s" % (proc.stdout[-1500:], proc.stderr[-1500:])

    def test_dispatched_agent_sees_v2_tools(self):
        self.fake.rules = self._dispatch_rules("contract-probe", [{"match": PROBE_MARKER, "text": "probe-done"}])
        proc = self._run("Dispatch the contract probe.")
        self.assertEqual(proc.returncode, 0, self._tail(proc))
        bodies = [b for b in self._child_bodies(PROBE_MARKER) if tool_names(b)]
        self.assertTrue(bodies, "contract-probe was never dispatched; " + self._tail(proc))
        seen = set(tool_names(bodies[0]))
        self.assertTrue(DISPATCHED_TOOLS <= seen, "missing %s; seen %s" % (sorted(DISPATCHED_TOOLS - seen), sorted(seen)))
        self.assertFalse(ABSENT_TOOLS & seen, sorted(seen))

    def test_dispatched_agent_inherits_parent_model(self):
        for model in (OTHER_MODEL, PARENT_MODEL):
            with self.subTest(parent=model):
                del self.fake.requests[:]
                self.fake.rules = self._dispatch_rules("contract-hidden", [{"match": HIDDEN_MARKER, "text": "sub-done"}])
                proc = self._run("Dispatch the hidden agent.", model=model)
                self.assertEqual(proc.returncode, 0, self._tail(proc))
                child = self._child_bodies(HIDDEN_MARKER)
                self.assertTrue(child, "contract-hidden was never dispatched; " + self._tail(proc))
                self.assertEqual({b.get("model") for b in child}, {model})

    def test_hook_sees_shell_in_dispatched_agent(self):
        target = os.path.join(self.work, "shell-marker")
        command = "touch " + shlex.quote(target)
        self.fake.rules = self._dispatch_rules("contract-probe", [
            self._shell_rule(command), {"match": PROBE_MARKER, "text": "probe-done"}])
        proc = self._run("Dispatch the contract probe.")
        self.assertEqual(proc.returncode, 0, self._tail(proc))
        self.assertTrue(os.path.exists(target), self._tail(proc))
        hooks = [h for h in self._hooks() if h.get("tool") == "shell"]
        self.assertTrue(hooks, "plugin hook never saw shell: %s" % self._hooks())
        self.assertEqual(hooks[0]["args"].get("command"), command)
        self.assertTrue(V2_HOOK_KEYS <= set(hooks[0]["keys"]), hooks[0]["keys"])

    def test_write_in_dispatched_agent(self):
        target = os.path.join(self.work, "written.txt")
        self.fake.rules = self._dispatch_rules("contract-probe", [
            {"match": PROBE_MARKER, "fresh": True, "tool": ["write"],
             "args": {"path": target, "content": "contract-write\n"}},
            {"match": PROBE_MARKER, "text": "probe-done"}])
        proc = self._run("Dispatch the contract probe.")
        self.assertEqual(proc.returncode, 0, self._tail(proc))
        with open(target) as fh:
            self.assertEqual(fh.read(), "contract-write\n")
        hooks = [h for h in self._hooks() if h.get("tool") == "write"]
        self.assertTrue(hooks, self._hooks())
        self.assertIn("path", hooks[0]["args"])

    def test_plugin_deny_blocks_shell_in_dispatched_agent(self):
        target = os.path.join(self.work, "denied-marker")
        self.fake.rules = self._dispatch_rules("contract-probe", [
            self._shell_rule("touch " + shlex.quote(target)), {"match": PROBE_MARKER, "text": "probe-done"}])
        proc = self._run("Dispatch the contract probe.", extra_env={"CONTRACT_DENY": "shell"})
        self.assertEqual(proc.returncode, 0, self._tail(proc))
        self.assertFalse(os.path.exists(target), "deny did not block the tool")
        self.assertTrue(any(h.get("tool") == "shell" for h in self._hooks()), self._hooks())

    def _get_first(self, base, paths, timeout=15):
        tried = []
        for path in paths:
            req = urllib.request.Request(base + path, headers={"Authorization": SERVE_AUTH})
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return json.loads(resp.read().decode("utf-8", "replace"))
            except (urllib.error.HTTPError, ValueError) as exc:
                tried.append("%s: %s" % (path, exc))
        self.fail("no endpoint answered: " + "; ".join(tried))

    def _get_names(self, base, paths, expected, timeout=30):
        # v2 boots the instance on the first request and loads agents/commands/skills after it
        # answers, so the first listing can be empty: poll until `expected` shows up.
        deadline = time.monotonic() + timeout
        names = _names(self._get_first(base, paths))
        while not expected <= names and time.monotonic() < deadline:
            time.sleep(1)
            names = _names(self._get_first(base, paths))
        return names

    def _wait_port(self, port, proc, log_path, timeout=90):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                with open(log_path) as fh:
                    self.fail("opencode serve exited %s: %s" % (proc.returncode, fh.read()[-2000:]))
            try:
                socket.create_connection(("127.0.0.1", port), 1).close()
                return
            except OSError:
                time.sleep(0.5)
        self.fail("opencode serve did not listen on %d within %ds" % (port, timeout))

    def _logs(self, serve_log):
        chunks = []
        log_dir = os.path.join(self.env["XDG_DATA_HOME"], "opencode", "log")
        paths = [serve_log]
        if os.path.isdir(log_dir):
            paths += [os.path.join(log_dir, f) for f in sorted(os.listdir(log_dir))]
        for path in paths:
            if os.path.isfile(path):
                with open(path, errors="replace") as fh:
                    chunks.append(fh.read())
        return "\n".join(chunks)

    def test_install_discovery(self):
        skill_dirs = sorted(os.path.join(ROOT, d) for d in os.listdir(ROOT)
                            if not d.startswith((".", "_")) and os.path.isfile(os.path.join(ROOT, d, "SKILL.md")))
        self.assertEqual(len(skill_dirs), 6, skill_dirs)
        for skill_dir in skill_dirs:
            oc_harness.install(skill_dir, 2, self.home)
        skills_dir = os.path.join(self.config_dir, "skills")
        self.assertEqual(set(os.listdir(skills_dir)), SKILLS)
        agents_dir = os.path.join(self.config_dir, "agents")
        installed_agents = {f[:-3] for f in os.listdir(agents_dir)
                            if f.endswith(".md") and not f.startswith("contract-")}
        commands_dir = os.path.join(self.config_dir, "commands")
        installed_commands = {f[:-3] for f in os.listdir(commands_dir) if f.endswith(".md")}
        port = _free_port()
        serve_log = os.path.join(self.tmp, "serve.log")
        with open(serve_log, "w") as log:
            # v2 serve requires HTTP Basic auth (user `opencode`); the password comes from this env var.
            server = subprocess.Popen([self.wrapper, "serve", "--port", str(port), "--hostname", "127.0.0.1"],
                                      cwd=self.work, env=dict(self.env, PWD=self.work,
                                                              OPENCODE_SERVER_PASSWORD=SERVE_PASSWORD),
                                      stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            self._wait_port(port, server, serve_log)
            base = "http://127.0.0.1:%d" % port
            agents = self._get_names(base, AGENT_PATHS, installed_agents)
            commands = self._get_names(base, COMMAND_PATHS, installed_commands)
            skills = self._get_names(base, SKILL_PATHS, SKILLS)
        finally:
            try:
                os.killpg(server.pid, signal.SIGTERM)
                server.wait(10)
            except (OSError, subprocess.TimeoutExpired):
                os.killpg(server.pid, signal.SIGKILL)
                server.wait(10)
        self.assertGreaterEqual(len(installed_agents), 13, sorted(installed_agents))
        self.assertFalse(installed_agents - agents, "agents not discovered: %s" % sorted(installed_agents - agents))
        self.assertEqual(len(installed_commands), 6, sorted(installed_commands))
        self.assertFalse(installed_commands - commands,
                         "commands not discovered: %s" % sorted(installed_commands - commands))
        self.assertTrue(SKILLS <= skills, "skills not discovered: %s" % sorted(SKILLS - skills))
        self.assertTrue(os.path.isfile(os.path.join(self.config_dir, "plugins", "oc-devteam-guard.js")))
        for name in installed_agents:
            with open(os.path.join(agents_dir, name + ".md")) as fh:
                self.assertNotRegex(fh.read(), r"(?m)^(model|variant|reasoningEffort):", name)
        lines = self._logs(serve_log).splitlines()
        load_errors = [l for l in lines if re.search(r"(?i)(failed to load|load error|parse error|invalid config)", l)]
        clashes = [l for l in lines if re.search(r"(?i)(clash|duplicate|conflict)", l)]
        self.assertFalse(load_errors, "\n".join(load_errors[:20]))
        self.assertFalse(clashes, "\n".join(clashes[:20]))


@unittest.skipUnless(ENABLED, SKIP_MSG)
@unittest.skipUnless(SANDBOX_EXEC, "no sandbox-exec on this host")
class SandboxProfileTest(unittest.TestCase):
    def test_blocks_remote_allows_localhost(self):
        tmp = tempfile.mkdtemp(prefix="oc-sandbox-")
        fake = FakeProvider()
        fake.start()
        try:
            profile = os.path.join(tmp, "sandbox.sb")
            with open(profile, "w") as fh:
                fh.write(SANDBOX_PROFILE)
            probe = "import socket, sys; socket.create_connection((sys.argv[1], int(sys.argv[2])), 5).close()"
            remote = subprocess.run([SANDBOX_EXEC, "-f", profile, sys.executable, "-c", probe, "1.1.1.1", "443"],
                                    capture_output=True, text=True, timeout=30)
            local = subprocess.run([SANDBOX_EXEC, "-f", profile, sys.executable, "-c", probe, "127.0.0.1",
                                    str(fake.port)], capture_output=True, text=True, timeout=30)
        finally:
            fake.stop()
            shutil.rmtree(tmp, ignore_errors=True)
        self.assertNotEqual(remote.returncode, 0, "sandbox let a remote connection through")
        self.assertEqual(local.returncode, 0, local.stderr)


class SkillFolderNameTests(unittest.TestCase):
    """The folder of each skill carries the same name as its frontmatter."""

    def test_folder_name_matches_frontmatter_name(self):
        for name in sorted(SKILLS):
            self.assertEqual(oc_harness.skill_name(os.path.join(ROOT, name)), name)


if __name__ == "__main__":
    unittest.main()
