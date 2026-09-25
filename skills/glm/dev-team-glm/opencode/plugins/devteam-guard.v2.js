// Real opencode v2.0.16 plugin shape, verified against the installed binary
// (/opt/homebrew/Cellar/opencode-v2/2.0.16/bin/opencode, read-only strings/grep):
// PluginModule.load decodes every plugin's default export against
// SB = r({default: P([r({id, effect}), r({id, setup})])}) and otherwise throws
// "Plugin must export a default definition with an id and an effect or setup
// function." A setup plugin receives an api object; api.tool.hook(name, fn)
// forwards to the Tool service (o.tool.hook), which fires
// e.trigger("tool", "execute.before", {tool, sessionID, agent, messageID, id,
// input}) from its one internal call site before every tool call — the tool
// name is always at event.tool and the raw call arguments at event.input. An
// error thrown by the hook function propagates and blocks the call. The
// dotted event name "tool" + "." + "execute.before" never appears together
// as a single string in the binary, and the plugin api object built for
// setup() has no "directory" field — v2 gives the plugin no per-call
// directory context; lanes run --standalone with cwd set to the lane dir, so
// process.cwd() is the lane's directory.
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
    });
  },
};
