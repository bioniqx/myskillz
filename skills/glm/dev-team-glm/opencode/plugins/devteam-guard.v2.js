// Shape: async (ctx) => ({ "tool.execute.before": async (input, output) => {...} })
// The installed opencode v2.0.16 binary triggers this hook from one internal
// call site (Tool service, tool.execute.before): the tool name and call
// arguments travel together as `{tool, sessionID, agent, messageID, id,
// input}` (`input` holding the raw args). Depending on how that event is
// adapted for the external plugin's two-argument (input, output) hook
// signature, the args may land as output.args, input.args or input.input;
// the tool name is always at input.tool.
import { spawnSync } from "node:child_process";
import path from "node:path";

export default async (ctx) => {
  return {
    "tool.execute.before": async (input, output) => {
      if (!process.env.DEVTEAM_ROLE) return;
      let decision = null;
      try {
        const args = output?.args ?? input?.args ?? input?.input;
        const payload = JSON.stringify({
          tool: input.tool,
          args,
          cwd: ctx.directory,
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
  };
};
