// Calls: python3 guard.py oc
// Spawns guard.py only for tools that can write files or run commands. The spawn is
// asynchronous so read-only tools pay nothing and the event loop never blocks. A failing guard
// fails open (integrate re-checks the footprint) and warns loudly once per lane process.
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

export const DevteamGuard = async ({ directory }) => {
  return {
    "tool.execute.before": async (input, output) => {
      const role = process.env.DEVTEAM_ROLE;
      if (!role) return;
      if (!GUARDED_TOOLS.has(input.tool)) return;
      let decision = null;
      try {
        const payload = JSON.stringify({
          tool: input.tool,
          args: output.args,
          cwd: directory,
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
    },
  };
};
