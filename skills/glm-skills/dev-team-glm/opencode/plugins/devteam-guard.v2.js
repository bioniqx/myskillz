// OpenCode v2 plugin: default export {id, setup(api)}; api.tool.hook("execute.before", fn) fires
// before every tool call with an event carrying event.tool and event.input. Throwing inside the
// hook denies the call. setup() gets no per-call directory from the api, so we use process.cwd()
// (the lane's cwd) for the guard payload instead.
import { spawnSync } from "node:child_process";
import path from "node:path";

export default {
  id: "devteam-guard",
  setup: async (api) => {
    api.tool.hook("execute.before", async (event) => {
      if (!process.env.DEVTEAM_ROLE) return;
      let decision = null;
      try {
        const payload = JSON.stringify({
          tool: event.tool,
          args: event.input,
          cwd: process.cwd(),
          role: process.env.DEVTEAM_ROLE,
        });
        const guardScript = path.join("{{SKILL_DIR}}", "scripts", "guard.py");
        const result = spawnSync("python3", [guardScript, "oc"], {
          input: payload,
          encoding: "utf8",
          timeout: 30000,
        });
        if (result.error || result.status !== 0) {
          console.error("devteam-guard: guard.py oc " +
            (result.error ? result.error.message : "exited " + result.status) + " — failing open");
        } else {
          const stdout = (result.stdout || "").trim();
          if (stdout) decision = JSON.parse(stdout);
        }
      } catch (err) {
        console.error("devteam-guard: guard.py oc " + err.message + " — failing open");
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
