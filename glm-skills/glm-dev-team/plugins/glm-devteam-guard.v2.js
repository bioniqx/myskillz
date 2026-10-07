// OpenCode v2 plugin: default export {id, setup(api)}; api.tool.hook("execute.before", fn) fires
// before every tool call with an event {tool, sessionID, agent, messageID, id, input}. Throwing
// inside the hook denies the call. setup() gets no per-call directory from the api, so we use
// process.cwd() (the lane's cwd) for the guard payload instead. The role comes from DEVTEAM_ROLE;
// when that is unset (agents started by the subagent tool) event.agent is used if it names a
// glm-dev-team role. guard.py is spawned asynchronously and only for tools that can write files or
// run commands. A failing guard fails open (integrate re-checks the footprint) and warns loudly
// once per lane process.
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
const DEVTEAM_ROLES = new Set([
  "glm-programmer",
  "glm-programmer-lite",
  "glm-code-reviewer",
  "glm-spot-reviewer",
  "glm-investigator",
  "glm-team-leader",
]);
const GUARD_TIMEOUT_MS = 30000;

let warnedFailOpen = false;

function failOpen(reason) {
  if (warnedFailOpen) return;
  warnedFailOpen = true;
  console.error(
    "glm-devteam-guard: WARNING guard.py oc " + reason +
      " — failing open for the rest of this lane; integrate re-checks the footprint"
  );
}

function resolveRole(event) {
  const envRole = process.env.DEVTEAM_ROLE;
  if (envRole) return envRole;
  if (event && typeof event.agent === "string" && DEVTEAM_ROLES.has(event.agent)) {
    return event.agent;
  }
  return null;
}

function runGuard(payload) {
  return new Promise((resolve) => {
    const guardScript = path.join("{{SKILL_DIR}}", "scripts", "guard.py");
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
  id: "glm-devteam-guard",
  setup: async (api) => {
    await api.tool.hook("execute.before", async (event) => {
      const role = resolveRole(event);
      if (!role) return;
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
