// Calls: python3 guard.py oc
import { spawnSync } from "node:child_process";
import path from "node:path";

export const DevteamGuard = async ({ directory }) => {
  return {
    "tool.execute.before": async (input, output) => {
      if (!process.env.DEVTEAM_ROLE) return;
      let decision = null;
      try {
        const payload = JSON.stringify({
          tool: input.tool,
          args: output.args,
          cwd: directory,
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
    },
  };
};
