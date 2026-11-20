// Remotion CLI (Studio / Render export) bundle config: consistent with vite.config.ts @proj/@demos strategy.
// Falls back to proj-stub when project is unlinked; symlinks:false resolves symlinks via
// virtual paths so bare imports resolve to local node_modules (preventing duplicate react/remotion instances).
import { existsSync } from "node:fs";
import path from "node:path";
import { Config } from "@remotion/cli/config";

const proj = path.resolve(
  process.cwd(),
  existsSync(path.resolve(process.cwd(), "proj", "workbench.ts")) ? "proj" : "proj-stub",
);

Config.overrideWebpackConfig((c) => ({
  ...c,
  resolve: {
    ...c.resolve,
    symlinks: false,
    alias: {
      ...(c.resolve?.alias ?? {}),
      "@proj": proj,
      "@demos": path.resolve(process.cwd(), "demosrc"),
    },
  },
}));

// Aligns with template/remotion.config.ts: JPEG frames, ANGLE GL (required by three/WebGL shots), concurrency 4
Config.setVideoImageFormat("jpeg");
Config.setOverwriteOutput(true);
Config.setChromiumOpenGlRenderer("angle");
Config.setConcurrency(4);
