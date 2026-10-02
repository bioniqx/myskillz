// OpenCode v2 plugin: default export {id, setup(api)}; api.tool.hook("execute.before", fn) fires
// before every tool call with an event {tool, sessionID, agent, messageID, id, input}. Throwing
// inside the hook denies the call. The role is event.agent when it names an oc-<role> dev-team agent; the
// session itself and any other agent are not checked. oc_guard.py finds a programmer's slice from the
// tool input (an edit path or a shell workdir under <state>/wt/<id>/); setup() gets no per-call
// directory, so process.cwd() is sent as cwd. oc_guard.py is spawned asynchronously and only for tools
// that can write files or run commands. A failing guard fails open (integrate re-checks the
// footprint) and warns loudly once per OpenCode process.
import { spawn } from "node:child_process";
import path from "node:path";

const GUARDED_TOOLS = new Set([
  "write",
  "edit",
  "patch",
  "apply_patch",
  "multiedit",
  "shell",
  "bash",
  "execute",
  "batch",
]);
const DISPATCH_TOOLS = new Set(["subagent", "task"]);
const GUARDED_ROLES = new Set([
  "programmer",
  "code-reviewer",
  "spot-reviewer",
  "investigator",
  "team-leader",
]);
const AGENT_PREFIX = "oc-";
const GUARD_TIMEOUT_MS = 30000;

let warnedFailOpen = false;

function failOpen(reason) {
  if (warnedFailOpen) return;
  warnedFailOpen = true;
  console.error(
    "oc-devteam-guard: WARNING oc_guard.py oc " + reason +
      " — failing open for the rest of this OpenCode process; integrate re-checks the footprint"
  );
}

function resolveRole(event) {
  if (event && typeof event.agent === "string" && event.agent.startsWith(AGENT_PREFIX)) {
    const role = event.agent.slice(AGENT_PREFIX.length);
    if (GUARDED_ROLES.has(role)) return role;
  }
  return null;
}

function runGuard(payload) {
  return new Promise((resolve) => {
    const guardScript = path.join("{{SKILL_DIR}}", "scripts", "oc_guard.py");
    let settled = false;
    let timer = null;
    const finish = (value) => {
      if (settled) return;
      settled = true;
      if (timer) clearTimeout(timer);
      resolve(value);
    };
    let child;
    try {
      child = spawn("python3", [guardScript, "oc"], { stdio: ["pipe", "pipe", "ignore"] });
    } catch (err) {
      failOpen(err.message);
      finish(null);
      return;
    }
    let stdout = "";
    timer = setTimeout(() => {
      failOpen("timed out after " + GUARD_TIMEOUT_MS + " ms");
      child.kill("SIGKILL");
      finish(null);
    }, GUARD_TIMEOUT_MS);
    child.stdout.setEncoding("utf8");
    child.stdout.on("data", (chunk) => {
      stdout += chunk;
    });
    child.on("error", (err) => {
      failOpen(err.message);
      finish(null);
    });
    child.on("close", (code) => {
      if (settled) return;
      if (code !== 0) {
        failOpen("exited " + code);
        finish(null);
        return;
      }
      const text = stdout.trim();
      if (!text) {
        finish(null);
        return;
      }
      try {
        finish(JSON.parse(text));
      } catch (err) {
        failOpen(err.message);
        finish(null);
      }
    });
    child.stdin.on("error", () => {});
    child.stdin.end(payload);
  });
}

export default {
  id: "oc-devteam-guard",
  setup: async (api) => {
    await api.tool.hook("execute.before", async (event) => {
      const role = resolveRole(event);
      if (!role) return;
      if (DISPATCH_TOOLS.has(event.tool)) {
        throw new Error("dev-team roles may not dispatch nested subagents (" + role + ")");
      }
      if (!GUARDED_TOOLS.has(event.tool)) return;
      let decision = null;
      try {
        const payload = JSON.stringify({
          tool: event.tool,
          args: event.input,
          cwd: process.cwd(),
          role: role,
        });
        decision = await runGuard(payload);
      } catch (err) {
        failOpen(err.message);
        decision = null;
      }
      if (
        decision &&
        decision.hookSpecificOutput &&
        decision.hookSpecificOutput.permissionDecision === "deny"
      ) {
        throw new Error(
          decision.hookSpecificOutput.permissionDecisionReason || "denied by devteam guard"
        );
      }
    });
  },
};
