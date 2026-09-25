// Shape: Plugin.define({ id: "devteam-guard", setup })
import { Plugin } from "@opencode/plugin";
import { spawnSync } from "node:child_process";
import path from "node:path";

export default Plugin.define({
  id: "devteam-guard",
  setup: (ctx) => ({
    "tool.execute.before": async (input, output) => {
      if (!process.env.DEVTEAM_ROLE) return;
      let decision = null;
      try {
        const payload = JSON.stringify({
          tool: input.tool,
          args: output.args,
          cwd: ctx.location.directory,
          role: process.env.DEVTEAM_ROLE,
        });
        const guardScript = path.join("{{SKILL_DIR}}", "scripts", "guard.py");
        const result = spawnSync("python3", [guardScript, "oc"], {
          input: payload,
          encoding: "utf8",
        });
        const stdout = (result.stdout || "").trim();
        if (stdout) decision = JSON.parse(stdout);
      } catch (err) {
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
  }),
});
