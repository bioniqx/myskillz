#!/usr/bin/env node
// Imported result vs original video frame-by-frame comparison: proves decomposing and recomposing does not alter visuals.
//
//   node scripts/parity.mjs [--frames 150,240,470,1000] [--tolerance 2]
//
// Renders ProjImported (unmodified workbench project just imported from manifest) and ProjOriginal (project's own Main)
// at the same frame to PNG in .parity/, using PIL for pixel-by-pixel comparison (percentage of pixels with per-channel diff > tolerance).
// Prerequisite: already linked via `node scripts/open.mjs <project>`, manifest provides `original`, python3 + Pillow installed.
// Bundles once, renders multiple frames (remotion still re-bundles each time, 8 frames would run 8 bundles).
// Exit codes: 0 all identical; 1 differences found; 2 inconclusive (missing prerequisite / comparison failed) — never false green.
import { bundle } from "@remotion/bundler";
import { renderStill, selectComposition } from "@remotion/renderer";
import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const wb = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const args = process.argv.slice(2);
const opt = (k, d) => { const i = args.indexOf(`--${k}`); return i >= 0 ? args[i + 1] : d; };
const FRAMES = opt("frames", "150,240,470,1000").split(",").map(Number);
const TOL = Number(opt("tolerance", "2"));

if (!existsSync(join(wb, "proj", "workbench.ts"))) {
  console.error("No project linked with manifest: run node scripts/open.mjs <project dir> first");
  process.exit(2);
}
// Check comparison dependencies first before rendering frames
{
  const r = spawnSync("python3", ["-c", "import PIL"], { encoding: "utf8" });
  if (r.status !== 0) {
    console.error("parity requires python3 + Pillow for pixel comparison: pip install pillow (or python3 -m pip install pillow)");
    process.exit(2);
  }
}

// Remotion static server rejects symlinks: dereference sync to .render-public, matching export pipeline
const out = join(wb, ".parity");
mkdirSync(out, { recursive: true });
const renderPublic = join(wb, ".render-public");
const rs = spawnSync("rsync", ["-aL", "--delete", "--exclude=cardpreviews", "public/", `${renderPublic}/`], { cwd: wb, stdio: "inherit" });
if (rs.status !== 0) process.exit(2);

console.log("bundling…");
const serveUrl = await bundle({
  entryPoint: join(wb, "src/remotion/index.ts"),
  publicDir: renderPublic,
  // Same aliases as remotion.config.ts (programmatic API does not read remotion.config.ts)
  webpackOverride: (c) => ({
    ...c,
    resolve: {
      ...c.resolve,
      symlinks: false,
      alias: { ...(c.resolve?.alias ?? {}), "@proj": join(wb, "proj"), "@demos": join(wb, "demosrc") },
    },
  }),
});

const render = async (id, frame) => {
  const composition = await selectComposition({ serveUrl, id, inputProps: {} });
  const output = join(out, `${id}-f${frame}.png`);
  await renderStill({ composition, serveUrl, output, frame, imageFormat: "png", chromiumOptions: { gl: "angle" } });
  return output;
};

const PY_DIFF = `
import sys
from PIL import Image, ImageChops
a = Image.open(sys.argv[1]).convert("RGB"); b = Image.open(sys.argv[2]).convert("RGB")
if a.size != b.size:
    print("SIZE", a.size, b.size); sys.exit(3)
d = ImageChops.difference(a, b)
px = d.getdata(); tol = int(sys.argv[3])
bad = sum(1 for p in px if max(p) > tol)
print(bad, a.size[0] * a.size[1], max(max(p) for p in px))
`;

const results = []; // { f, verdict: "same" | "diff" | "inconclusive", detail }
for (const f of FRAMES) {
  const [a, b] = await Promise.all([render("ProjImported", f), render("ProjOriginal", f)]);
  const py = spawnSync("python3", ["-c", PY_DIFF, a, b, String(TOL)], { encoding: "utf8" });
  if (py.status !== 0) {
    const detail = (py.stdout + py.stderr).trim().split("\n").pop() ?? "";
    results.push({ f, verdict: "inconclusive", detail });
    console.log(`f${f}: ? Comparison incomplete (${detail || `python exit code ${py.status}`})`);
    continue;
  }
  const [bad, total, maxd] = py.stdout.trim().split(/\s+/).map(Number);
  if (![bad, total, maxd].every(Number.isFinite) || total <= 0) {
    results.push({ f, verdict: "inconclusive", detail: `Unparseable diff output: ${py.stdout.trim()}` });
    console.log(`f${f}: ? Unparseable diff output`);
    continue;
  }
  const ratio = bad / total;
  const same = ratio < 0.001; // Less than 0.1% pixel difference considered identical (antialiasing / font raster noise)
  results.push({ f, verdict: same ? "same" : "diff", detail: `${bad}/${total}` });
  console.log(`f${f}: ${same ? "✓ Match" : "✗ Diff"}  Different pixels ${bad}/${total} (${(ratio * 100).toFixed(3)}%), max channel diff ${maxd}`);
}

const diff = results.filter((r) => r.verdict === "diff");
const inconclusive = results.filter((r) => r.verdict === "inconclusive");
if (inconclusive.length) {
  console.log(`\n${inconclusive.length}/${results.length} frames could not be compared, inconclusive. PNGs at ${out}`);
  process.exit(2);
}
if (diff.length) {
  console.log(`\n${diff.length}/${results.length} frames have differences, PNGs at ${out}`);
  process.exit(1);
}
console.log(`\n${results.length} frames all match, PNGs at ${out}`);
