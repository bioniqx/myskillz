// Single card quick render check: bundles only the specified demo (without loading the entire workbench index), renders to mp4 + contact sheet.
//
//   node scripts/check-demo.mjs <relative path under demos/.tsx> [...more] [--out <dir>]
//        [--frames 12,40,88] [--sheet 8] [--scale 1] [--concurrency 3] [--no-video]
//
// Example: node scripts/check-demo.mjs camera/crash-zoom-punch/CrashZoomReal.tsx --frames 10,20
// Outputs (default ../shot-polish/after/):
//   <Stem>.mp4           Full segment render (1920×1080 h264)
//   <Stem>.sheet.jpg     Evenly sampled --sheet frames (default 8) contact sheet (4 columns, chronological, frame numbers in stdout)
//   <Stem>.f<N>.jpg      Full-size single frame for specified --frames
// Duration: exported *_DURATION / *_DUR takes precedence, otherwise inferred by gen-index in demo-index.ts.
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { bundle } from "@remotion/bundler";
import { renderMedia, renderStill, selectComposition } from "@remotion/renderer";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const args = process.argv.slice(2);
const opt = (k, d) => {
  const i = args.indexOf(`--${k}`);
  return i < 0 ? d : args[i + 1];
};
const flag = (k) => args.includes(`--${k}`);
const valued = new Set(["out", "frames", "sheet", "scale", "concurrency"]);
const files = args.filter((a, i) => !a.startsWith("--") && !(i > 0 && valued.has(args[i - 1].slice(2))));
if (!files.length) {
  console.error("usage: node scripts/check-demo.mjs <category/card/Stem.tsx> [...]");
  process.exit(2);
}
const out = path.resolve(opt("out", path.join(ROOT, "..", "shot-polish", "after")));
const stills = opt("frames", "")
  .split(",")
  .map((s) => s.trim())
  .filter(Boolean)
  .map(Number);
const sheetN = Number(opt("sheet", "8"));
const scale = Number(opt("scale", "1"));
const concurrency = Number(opt("concurrency", "3"));
mkdirSync(out, { recursive: true });

const indexSrc = existsSync(path.join(ROOT, "src/cards/demo-index.ts"))
  ? readFileSync(path.join(ROOT, "src/cards/demo-index.ts"), "utf8")
  : "";
const demos = files.map((f) => {
  const rel = f.replace(/^.*?demos\//, "").replace(/\.tsx$/, "");
  const stem = path.basename(rel);
  if (!existsSync(path.join(ROOT, "..", "demos", `${rel}.tsx`))) throw new Error(`not found: demos/${rel}.tsx`);
  const m = indexSrc.match(new RegExp(`stem: "${stem}"[^\\n]*?duration: (\\d+)`));
  return { rel, stem, fallback: m ? Number(m[1]) : 150 };
});

const tag = demos.map((d) => d.stem).join("_").slice(0, 60) + "_" + process.pid;
const dir = path.join(ROOT, ".check", tag);
mkdirSync(dir, { recursive: true });
writeFileSync(
  path.join(dir, "index.tsx"),
  `import React from "react";
import { Composition, registerRoot } from "remotion";
${demos.map((d, i) => `import * as M${i} from "@demos/${d.rel}";`).join("\n")}
const dur = (m: Record<string, unknown>, fb: number) => {
  const k = Object.keys(m).find((k) => /_(DURATION|DUR)$/.test(k) && typeof m[k] === "number");
  return Math.max(2, Math.round(k ? (m[k] as number) : fb));
};
const Root: React.FC = () => (
  <>
${demos
  .map(
    (d, i) =>
      `    <Composition id="${d.stem}" component={(M${i} as Record<string, unknown>)["${d.stem}"] as React.FC} durationInFrames={dur(M${i} as Record<string, unknown>, ${d.fallback})} fps={30} width={1920} height={1080} />`,
  )
  .join("\n")}
  </>
);
registerRoot(Root);
`,
);

let serveUrl = "";
try {
  serveUrl = await bundle({
    entryPoint: path.join(dir, "index.tsx"),
    publicDir: path.join(ROOT, "public"),
    // Distinct entry paths mean webpack persistent cache never hits, piling up in node_modules/.cache (~19GB)
    enableCaching: false,
    webpackOverride: (c) => ({
      ...c,
      resolve: {
        ...c.resolve,
        symlinks: false,
        alias: { ...(c.resolve?.alias ?? {}), "@demos": path.join(ROOT, "demosrc") },
      },
    }),
  });
  const chromiumOptions = { gl: "angle" };
  for (const d of demos) {
    // Clear previous iteration stills for this stem to avoid mixing old and new frames
    for (const f of readdirSync(out)) if (f.startsWith(`${d.stem}.f`) && f.endsWith(".jpg")) rmSync(path.join(out, f));
    const composition = await selectComposition({ serveUrl, id: d.stem, chromiumOptions });
    const n = composition.durationInFrames;
    for (const f of stills) {
      await renderStill({
        serveUrl,
        composition,
        frame: Math.min(n - 1, f),
        output: path.join(out, `${d.stem}.f${f}.jpg`),
        imageFormat: "jpeg",
        jpegQuality: 92,
        chromiumOptions,
      });
    }
    if (!flag("no-video")) {
      const mp4 = path.join(out, `${d.stem}.mp4`);
      const t0 = Date.now();
      await renderMedia({
        serveUrl,
        composition,
        codec: "h264",
        crf: 20,
        imageFormat: "jpeg",
        jpegQuality: 90,
        scale,
        concurrency,
        chromiumOptions,
        outputLocation: mp4,
        muted: true,
        timeoutInMilliseconds: 120000,
      });
      // Contact sheet: evenly sample sheetN frames across 4 columns
      const picks = Array.from({ length: sheetN }, (_, k) => Math.round(((k + 0.5) * n) / sheetN));
      const sel = picks.map((p) => `eq(n\\,${p})`).join("+");
      execFileSync("ffmpeg", [
        "-v", "error", "-y", "-i", mp4,
        "-vf", `select='${sel}',scale=480:-1,tile=4x${Math.ceil(sheetN / 4)}`,
        "-frames:v", "1", "-vsync", "0", path.join(out, `${d.stem}.sheet.jpg`),
      ]);
      console.log(`${d.stem}: ${n}f → ${mp4} (${((Date.now() - t0) / 1000).toFixed(1)}s), sheet frames ${picks.join(",")}`);
    }
  }
} finally {
  rmSync(dir, { recursive: true, force: true });
  // Bundled artifacts land in system temp dir, ~20MB each; clean up to avoid filling disk
  if (serveUrl) rmSync(serveUrl, { recursive: true, force: true });
}
