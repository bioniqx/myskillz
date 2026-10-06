"""OpenCode real-binary contract tests (opt-in: OC_CONTRACT=1) plus fake-provider self-tests.

The fake-provider self-tests always run. The real-binary classes run only with OC_CONTRACT=1:
they drive `opencode` against fake_provider.py inside a sandboxed HOME/XDG_* tree and block all
non-localhost network with macOS sandbox-exec (skipped without it unless
OC_CONTRACT_NO_SANDBOX=1). v2 is the `opencode` on PATH, v1 comes from OC_V1_BIN.
"""

import base64
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
        self.fake.rules = [{"match": "THROTTLE", "status": 429,
                            "body": {"error": {"code": "1302", "message": "rate limited"}}}]
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            _post(self.url, {"model": "fake-model", "messages": [{"role": "user", "content": "THROTTLE me"}]})
        self.assertEqual(ctx.exception.code, 429)
        self.assertIn("1302", ctx.exception.read().decode("utf-8"))
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
# render_agent always sets `execute: deny`, and v2 drops a denied tool from the request.
V2_TOOLS = {"edit", "glob", "grep", "question", "read", "shell", "skill", "subagent",
            "webfetch", "websearch", "write"}
V2_DENIED_TOOLS = {"execute"}
V1_TOOLS = {"bash", "edit", "glob", "grep", "read", "skill", "task", "todowrite", "webfetch", "write"}
V1_ONLY_TOOLS = {"bash", "task", "todowrite", "apply_patch"}
V2_EVENT_TYPES = {"step_start", "tool_use", "step_finish", "text", "error"}
V2_HOOK_KEYS = {"tool", "sessionID", "agent", "messageID", "id", "input"}
SKILLS = {"glm-brainstorming", "glm-dev-team", "glm-doc-generator", "glm-requirements-code-audit",
          "glm-systematic-debugging", "glm-writing-plans"}
AGENT_PATHS = ("/agent", "/api/agent")
COMMAND_PATHS = ("/command", "/api/command")
SKILL_PATHS = ("/skill", "/api/skill", "/experimental/skill")
SERVE_PASSWORD = "contract-pass"
SERVE_AUTH = "Basic " + base64.b64encode(("opencode:" + SERVE_PASSWORD).encode("ascii")).decode("ascii")
HIDDEN_MARKER = "HIDDEN-AGENT-MARKER-7F3A"
PROBE_AGENT_SRC = (
    "---\n"
    "description: contract probe agent\n"
    "model: flash\n"
    "effort: high\n"
    "access: write\n"
    "bash: true\n"
    "web: true\n"
    "---\n"
    "You are a contract probe. Call the tools you are offered, then answer briefly.\n"
)
HIDDEN_AGENT_SRC = (
    "---\n"
    "description: contract hidden subagent\n"
    "model: flash\n"
    "effort: high\n"
    "access: read\n"
    "bash: false\n"
    "web: false\n"
    "---\n"
    "%s Reply with sub-done.\n" % HIDDEN_MARKER
)
BANG_COMMAND = "---\ndescription: contract bang probe\n---\nMarker: !`echo BANG-$((40+2))`\n"
PLUGIN_JS = r"""import { appendFileSync } from "node:fs";

const LOG = process.env.CONTRACT_HOOK_LOG || "";
const DENY = (process.env.CONTRACT_DENY || "").split(",").filter(Boolean);

function record(entry) {
  if (LOG) appendFileSync(LOG, JSON.stringify(entry) + "\n");
  if (DENY.includes(entry.tool)) throw new Error("contract-deny: " + entry.tool);
}

export const ContractProbe = async () => ({
  "tool.execute.before": async (input, output) => {
    record({ hook: "tool.execute.before", tool: input && input.tool,
             args: (output && output.args) || {}, keys: Object.keys(input || {}).sort() });
  },
  "execute.before": async (event) => {
    record({ hook: "execute.before", tool: event && event.tool,
             args: (event && event.input) || {}, keys: Object.keys(event || {}).sort() });
  },
});

export default ContractProbe;
"""
# v2 loads only a default export shaped {id, setup(api)}; a function default is silently ignored.
PLUGIN_JS_V2 = PLUGIN_JS.split("export const ContractProbe")[0] + r"""export default {
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


def _binary_for(major: int) -> str:
    candidates = []
    if major == 1 and os.environ.get("OC_V1_BIN"):
        candidates.append(os.environ["OC_V1_BIN"])
    if shutil.which("opencode"):
        candidates.append(shutil.which("opencode"))
    with tempfile.TemporaryDirectory(prefix="oc-detect-") as scratch:
        with mock.patch.dict(os.environ, _xdg(scratch)):
            for cand in candidates:
                path = os.path.abspath(shutil.which(cand) or cand)
                if os.path.isfile(path) and oc_harness.detect(path) == major:
                    return path
    return ""


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


def _snippet_json(text: str) -> dict:
    # config_snippet returns JSONC: leading `//` note lines, then the object.
    return json.loads("\n".join(l for l in text.splitlines() if not l.strip().startswith("//")))


def fake_config(url: str, major: int) -> dict:
    snippet = _snippet_json(oc_harness.config_snippet(major, ["contract-denied-*"]))
    return {
        "$schema": snippet["$schema"],
        "enabled_providers": ["fake"],
        "permission": snippet["permission"],
        "provider": {
            "fake": {
                "npm": "@ai-sdk/openai-compatible",
                "name": "Fake",
                "options": {"baseURL": url, "apiKey": "fake-key"},
                "models": {
                    "fake-model": {
                        "name": "fake-model",
                        "variants": {"low": {"reasoningEffort": "low"}, "high": {"reasoningEffort": "high"}},
                    }
                },
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


class ContractCases:
    MAJOR = 0
    SHELL = ""
    WRITE_PATH_KEY = ""
    TOOLS = set()

    @classmethod
    def setUpClass(cls):
        if not SANDBOX_EXEC and not NO_SANDBOX:
            raise unittest.SkipTest("no sandbox-exec network sandbox; set OC_CONTRACT_NO_SANDBOX=1 to run unsandboxed")
        cls.real_bin = _binary_for(cls.MAJOR)
        if not cls.real_bin:
            raise unittest.SkipTest("no opencode v%d binary (opencode on PATH or OC_V1_BIN)" % cls.MAJOR)

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
        self._write(os.path.join(self.config_dir, "opencode.json"),
                    json.dumps(fake_config(self.fake.url, self.MAJOR), indent=2))
        self._write(os.path.join(self.config_dir, "plugins", "contract-probe.js"),
                    PLUGIN_JS_V2 if self.MAJOR == 2 else PLUGIN_JS)
        self._write_agent("contract-probe", self._rendered(PROBE_AGENT_SRC))
        self._write_agent("contract-hidden", self._rendered(HIDDEN_AGENT_SRC))
        self.wrapper = write_wrapper(self.bindir, self.real_bin, self.tmp)
        self.env = sandbox_env(self.home, self.bindir, self.tmp)
        self.env["CONTRACT_HOOK_LOG"] = self.hook_log

    def tearDown(self):
        self.fake.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write(self, path, text):
        with open(path, "w") as fh:
            fh.write(text)

    def _rendered(self, src):
        text = oc_harness.render_agent(src, self.MAJOR)
        return re.sub(r"(?m)^model: .*$", "model: fake/fake-model", text, count=1)

    def _write_agent(self, name, text):
        self._write(os.path.join(self.config_dir, "agents", name + ".md"), text)

    def _lane(self, brief, effort="", agent="contract-probe"):
        return {"id": "contract", "agent": agent, "model": "fake/fake-model", "effort": effort,
                "dir": self.work, "brief": brief}

    def _exec(self, cmd, brief, extra_env=None, timeout=300):
        env = dict(self.env)
        env["PWD"] = self.work
        env.update(extra_env or {})
        stdin_text = "" if brief in cmd else brief
        proc = subprocess.run(cmd, input=stdin_text, capture_output=True, text=True, timeout=timeout,
                              cwd=self.work, env=env)
        events = []
        for line in proc.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if isinstance(event, dict):
                events.append(event)
        return proc, events

    def _run(self, brief, effort="", agent="contract-probe", extra_env=None, timeout=300):
        cmd = oc_harness.build_run_cmd(self._lane(brief, effort, agent), self.MAJOR, self.wrapper)
        return self._exec(cmd, brief, extra_env, timeout)

    def _tool_bodies(self):
        return [b for b in self.fake.bodies() if tool_names(b)]

    def _hooks(self):
        if not os.path.isfile(self.hook_log):
            return []
        with open(self.hook_log) as fh:
            return [json.loads(line) for line in fh if line.strip()]

    def _shell_rule(self, command):
        return {"fresh": True, "tool": [self.SHELL],
                "fill": {"command": command, "workdir": self.work, "timeout": 60000,
                         "background": False, "description": "contract marker"}}

    def _tail(self, proc):
        return "stdout: %s\nstderr: %s" % (proc.stdout[-1500:], proc.stderr[-1500:])

    def test_model_sees_expected_tools(self):
        proc, _ = self._run("List your tools, then answer ok.")
        self.assertEqual(proc.returncode, 0, self._tail(proc))
        bodies = self._tool_bodies()
        self.assertTrue(bodies, "no request carried tools")
        seen = set(tool_names(bodies[0]))
        self.assertTrue(self.TOOLS <= seen, "missing %s; seen %s" % (sorted(self.TOOLS - seen), sorted(seen)))
        if self.MAJOR == 2:
            self.assertFalse((V1_ONLY_TOOLS | V2_DENIED_TOOLS) & seen, sorted(seen))

    def test_hook_sees_shell_tool_and_args(self):
        target = os.path.join(self.work, "shell-marker")
        command = "touch " + shlex.quote(target)
        self.fake.rules = [self._shell_rule(command), {"text": "done"}]
        proc, events = self._run("Run the marker command.")
        self.assertEqual(proc.returncode, 0, self._tail(proc))
        self.assertTrue(os.path.exists(target), self._tail(proc))
        hooks = [h for h in self._hooks() if h.get("tool") == self.SHELL]
        self.assertTrue(hooks, "plugin hook never saw %s: %s" % (self.SHELL, self._hooks()))
        self.assertEqual(hooks[0]["args"].get("command"), command)
        if self.MAJOR == 2:
            v2_hooks = [h for h in hooks if h["hook"] == "execute.before"]
            self.assertTrue(v2_hooks, hooks)
            self.assertTrue(V2_HOOK_KEYS <= set(v2_hooks[0]["keys"]), v2_hooks[0]["keys"])
        self.assertIn("tool_use", [e.get("type") for e in events])

    def test_write_tool_args(self):
        target = os.path.join(self.work, "written.txt")
        self.fake.rules = [{"fresh": True, "tool": ["write"],
                            "args": {self.WRITE_PATH_KEY: target, "content": "contract-write\n"}},
                           {"text": "done"}]
        proc, _ = self._run("Write the file.")
        self.assertEqual(proc.returncode, 0, self._tail(proc))
        with open(target) as fh:
            self.assertEqual(fh.read(), "contract-write\n")
        hooks = [h for h in self._hooks() if h.get("tool") == "write"]
        self.assertTrue(hooks, self._hooks())
        self.assertIn(self.WRITE_PATH_KEY, hooks[0]["args"])

    def test_plugin_deny_blocks_tool(self):
        target = os.path.join(self.work, "denied-marker")
        self.fake.rules = [self._shell_rule("touch " + shlex.quote(target)), {"text": "done"}]
        proc, _ = self._run("Run the marker command.", extra_env={"CONTRACT_DENY": self.SHELL})
        self.assertFalse(os.path.exists(target), "deny did not block the tool")
        self.assertTrue(any(h.get("tool") == self.SHELL for h in self._hooks()), self._hooks())
        if self.MAJOR == 2:
            self.assertEqual(proc.returncode, 0, self._tail(proc))

    def test_reasoning_effort_reaches_request(self):
        # v2: the lane's #low suffix must beat the agent's `variant: high`; v1: frontmatter reasoningEffort.
        expected = "low" if self.MAJOR == 2 else "high"
        proc, _ = self._run("Answer ok.", effort=expected)
        self.assertEqual(proc.returncode, 0, self._tail(proc))
        efforts = [b.get("reasoning_effort") for b in self._tool_bodies()]
        self.assertIn(expected, efforts)

    def test_json_event_schema(self):
        self.fake.rules = [self._shell_rule("echo schema"), {"text": "done"}]
        proc, events = self._run("Run the schema command.")
        self.assertEqual(proc.returncode, 0, self._tail(proc))
        types = [e.get("type") for e in events]
        self.assertTrue(types and all(types), types)
        self.assertTrue({"tool_use", "text"} <= set(types), types)
        if self.MAJOR == 2:
            self.assertTrue(set(types) <= V2_EVENT_TYPES, types)
            self.assertIn("step_start", types)
            self.assertEqual(types[-1], "text", types)

    def test_brief_arrives_verbatim_via_stdin(self):
        brief = 'Contract brief "quoted" $HOME `tick`\n  indented\tline\nünïcode ✓ end'
        cmd = oc_harness.build_run_cmd(self._lane(brief), self.MAJOR, self.wrapper)
        self.assertNotIn(brief, cmd)
        proc, _ = self._run(brief)
        self.assertEqual(proc.returncode, 0, self._tail(proc))
        texts = [t for b in self._tool_bodies() for t in message_texts(b, "user")]
        self.assertIn(brief, texts)

    def test_rate_limit_error_and_governor(self):
        # The slow lane outlives the throttled lane's built-in retries (v2 ~86 s, v1 ~77 s), so
        # the third lane starts only after the governor has halved the width from 2 to 1.
        self.fake.rules = [
            {"match": "THROTTLE-LANE", "status": 429,
             "body": {"error": {"code": "1302", "message": "rate limit reached for requests"}}},
            {"match": "SLOW-LANE", "delay": 130, "text": "slow-done"},
            {"text": "ok"},
        ]
        lanes = [{"id": "throttle", "brief": "THROTTLE-LANE answer ok"},
                 {"id": "slow", "brief": "SLOW-LANE answer ok"},
                 {"id": "after", "brief": "AFTER-LANE answer ok"}]
        for lane in lanes:
            lane.update({"agent": "contract-probe", "model": "fake/fake-model", "dir": self.work, "timeout": 600})
        out_dir = os.path.join(self.tmp, "lanes")
        with mock.patch.dict(os.environ, self.env, clear=True):
            rows = oc_harness.run_lanes(lanes, out_dir, width=2, stall=300, binary=self.wrapper, major=self.MAJOR)
        throttled, slow, after = rows
        with open(throttled["out"]) as fh:
            out = fh.read()
        self.assertGreaterEqual(throttled["throttles"], 1, out[-1500:])
        if self.MAJOR == 2:
            self.assertEqual(throttled["status"], "FAIL")
            self.assertIn("provider.rate-limit", out)
        else:
            self.assertIn("APIError", out)
            self.assertIn("1302", out)
        self.assertEqual(slow["status"], "OK", slow["error"])
        self.assertEqual(after["width"], 1)

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
        install = subprocess.run(["sh", os.path.join(ROOT, "install-opencode.sh"), "--home", self.home],
                                 cwd=ROOT, env=self.env, capture_output=True, text=True, timeout=300)
        self.assertEqual(install.returncode, 0, install.stdout[-1500:] + install.stderr[-1500:])
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
            if self.MAJOR == 1:
                # v1 holds the first /agent request until the instance boots: ~70 s in the sandbox,
                # where its network fetches (models.dev, ...) fail. /api/agent answers empty meanwhile.
                self._get_first(base, ("/agent",), timeout=240)
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
        self.assertFalse([n for n in skills if n.endswith("-glm")], sorted(skills))
        self.assertTrue(os.path.isfile(os.path.join(self.config_dir, "plugins", "glm-devteam-guard.js")))
        lines = self._logs(serve_log).splitlines()
        load_errors = [l for l in lines if re.search(r"(?i)(failed to load|load error|parse error|invalid config)", l)]
        clashes = [l for l in lines if re.search(r"(?i)(clash|duplicate|conflict)", l)]
        self.assertFalse(load_errors, "\n".join(load_errors[:20]))
        self.assertFalse(clashes, "\n".join(clashes[:20]))


@unittest.skipUnless(ENABLED, SKIP_MSG)
class V2ContractTest(ContractCases, unittest.TestCase):
    MAJOR = 2
    SHELL = "shell"
    WRITE_PATH_KEY = "path"
    TOOLS = V2_TOOLS

    def _dispatch(self, name):
        self.fake.rules = [
            {"match": HIDDEN_MARKER, "text": "sub-done"},
            {"fresh": True, "tool": ["subagent"],
             "fill": {"agent": name, "prompt": "Reply with sub-done.", "message": "Reply with sub-done.",
                      "description": "contract dispatch"}},
            {"text": "done"},
        ]
        proc, _ = self._run("Dispatch the contract subagent.")
        hits = [b for b in self.fake.bodies() if any(HIDDEN_MARKER in t for t in message_texts(b, "system"))]
        self.assertTrue(hits, "subagent %s was never dispatched; %s" % (name, self._tail(proc)))

    def test_missing_variant_reports_no_route(self):
        proc, _ = self._run("Answer ok.", effort="max")
        combined = proc.stdout + proc.stderr
        self.assertTrue("provider.no-route" in combined or "Variant unavailable" in combined, combined[-2000:])

    def test_rendered_agent_dispatchable_by_subagent(self):
        self._dispatch("contract-hidden")

    def test_probe_hidden_agent_dispatch(self):
        text = self._rendered(HIDDEN_AGENT_SRC)
        if "\nhidden: true\n" not in text:
            text = text.replace("\nmode: ", "\nhidden: true\nmode: ", 1)
        self._write_agent("contract-hidden-forced", text)
        self._dispatch("contract-hidden-forced")

    @unittest.expectedFailure  # v2 does not expand !`cmd` in commands; /glm-docs keeps its Turn-1 recon
    def test_probe_command_bang_expansion(self):
        self._write(os.path.join(self.config_dir, "commands", "contract-bang.md"), BANG_COMMAND)
        proc, _ = self._run("/contract-bang")
        texts = "\n".join(t for b in self.fake.bodies() for t in message_texts(b, "user"))
        self.assertIn("BANG-42", texts, "not expanded; user text: %s; %s" % (texts[-800:], self._tail(proc)))


@unittest.skipUnless(ENABLED, SKIP_MSG)
class V1ContractTest(ContractCases, unittest.TestCase):
    MAJOR = 1
    SHELL = "bash"
    WRITE_PATH_KEY = "filePath"
    TOOLS = V1_TOOLS

    def test_effort_suffix_rejected(self):
        brief = "Answer ok."
        cmd = oc_harness.build_run_cmd(self._lane(brief), 1, self.wrapper)
        i = cmd.index("-m") if "-m" in cmd else cmd.index("--model")
        cmd[i + 1] = cmd[i + 1] + "#high"
        proc, _ = self._exec(cmd, brief)
        self.assertNotEqual(proc.returncode, 0, self._tail(proc))


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


RACE_MSG = "Error: Standalone server exited before reporting readiness"
RACE_BIN = """#!/bin/sh
cat >/dev/null
echo x >> "$RACE_COUNT"
n=$(wc -l < "$RACE_COUNT" | tr -d ' ')
if [ "$n" -le "$RACE_FAILS" ]; then
  echo "$RACE_MSG" >&2
  exit 1
fi
echo '{"type":"text","part":{"type":"text","text":"ok"}}'
"""


class StandaloneRaceRetryTest(unittest.TestCase):
    """v2 `run --standalone` lanes started together on a fresh data dir race during init and some
    exit 1 with RACE_MSG (found by test_rate_limit_error_and_governor); run_lanes retries once."""

    def _run(self, fails, msg=RACE_MSG, major=2):
        tmp = tempfile.mkdtemp(prefix="oc-race-")
        self.addCleanup(shutil.rmtree, tmp, True)
        binary = os.path.join(tmp, "opencode")
        with open(binary, "w") as fh:
            fh.write(RACE_BIN)
        os.chmod(binary, 0o755)
        count = os.path.join(tmp, "count")
        lane = {"id": "race", "agent": "a", "model": "fake/fake-model", "dir": tmp, "brief": "hi",
                "env": {"RACE_COUNT": count, "RACE_FAILS": str(fails), "RACE_MSG": msg}}
        with mock.patch.object(oc_harness, "check_run_flags", return_value=[]):
            rows = oc_harness.run_lanes([lane], os.path.join(tmp, "out"), width=2, stall=60,
                                        binary=binary, major=major)
        with open(count) as fh:
            return rows[0], len(fh.read().splitlines())

    def test_race_retried_once_then_ok(self):
        row, attempts = self._run(1)
        self.assertEqual((row["status"], attempts), ("OK", 2), row)

    def test_race_retried_only_once(self):
        row, attempts = self._run(99)
        self.assertEqual((row["status"], attempts), ("FAIL", 2), row)

    def test_other_failure_not_retried(self):
        row, attempts = self._run(1, msg="Error: something else")
        self.assertEqual((row["status"], attempts), ("FAIL", 1), row)

    def test_v1_not_retried(self):
        row, attempts = self._run(1, major=1)
        self.assertEqual((row["status"], attempts), ("FAIL", 1), row)


if __name__ == "__main__":
    unittest.main()
