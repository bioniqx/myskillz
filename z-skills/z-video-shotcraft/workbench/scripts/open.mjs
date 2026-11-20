#!/usr/bin/env node
// One-click workbench launcher after delivery: links project → generates index → starts dev server → opens browser and auto-imports.
//
//   node scripts/open.mjs <project dir> [--port 5198] [--no-open] [--no-import]
//   node scripts/open.mjs               # without dir: reuses previously linked project
//
// Project dir = layer containing package.json / remotion.config.ts, source in <dir>/src (or <dir>/remotion/src).
// Project must provide src/workbench.ts manifest (structure in references/workbench.md) to decompose and import;
// can still open without manifest, but media tab won't show "Import project" button.
// Links are machine-local symlinks (workbench/proj, workbench/public/*), not checked into git.
//
// Dev server management: server started by this script records pid to .dev.pid. @proj alias is frozen
// when vite config loads, so passing a project dir (= relink) requires restarting server — only restarts
// verified own process; errors out if port is occupied by another server (e.g. manual npm run dev).
import { spawn, spawnSync } from "node:child_process";
import {
  existsSync, lstatSync, mkdirSync, openSync, readFileSync, readdirSync, readlinkSync, rmdirSync, symlinkSync, unlinkSync, writeFileSync,
} from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const wb = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const args = process.argv.slice(2);
const flag = (k) => args.includes(`--${k}`);
const opt = (k, d) => { const i = args.indexOf(`--${k}`); return i >= 0 ? args[i + 1] : d; };
const PORT = Number(opt("port", "5198"));
const positional = args.filter((a, i) => !a.startsWith("--") && !(i > 0 && args[i - 1] === "--port"));

const isLink = (p) => { try { return lstatSync(p).isSymbolicLink(); } catch { return false; } };
const rmLink = (p) => { if (isLink(p)) unlinkSync(p); };
const log = (s) => console.log(`[workbench] ${s}`);
const die = (s, code = 1) => { console.error(`[workbench] ${s}`); process.exit(code); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// —— 1. Locate project ——
const relink = !!positional[0];
let projectDir = relink ? resolve(positional[0]) : null;
const projLink = join(wb, "proj");
if (!relink) {
  if (!isLink(projLink)) die("Usage: node scripts/open.mjs <project dir> (directory required for first run)", 2);
  projectDir = dirname(resolve(wb, readlinkSync(projLink)));
  if (existsSync(join(projectDir, "..", "package.json")) && !existsSync(join(projectDir, "package.json"))) projectDir = dirname(projectDir);
  log(`Reusing previously linked project: ${projectDir}`);
} else {
  if (!existsSync(projectDir)) die(`Project directory does not exist: ${projectDir}`, 2);
  const candidates = [join(projectDir, "src"), join(projectDir, "remotion", "src")];
  const srcDir = candidates.find((d) => existsSync(d) && readdirSync(d).some((f) => /^(Root|index|entry|workbench)\.tsx?$/.test(f)));
  if (!srcDir) die(`Could not find Remotion source directory under ${projectDir} (src/ or remotion/src/ must contain Root.tsx / index.ts)`, 2);
  const projRoot = dirname(srcDir); // package.json / public layer
  const publicSrc = join(projRoot, "public");

  // —— 2. Link src → proj, public/* → public/* ——
  rmLink(projLink);
  symlinkSync(srcDir, projLink);
  const pub = join(wb, "public");
  mkdirSync(pub, { recursive: true });
  // Clean up links left by previous project (only remove symlinks and created textures/ fallback dir, never touch real files)
  for (const e of readdirSync(pub)) {
    const p = join(pub, e);
    if (isLink(p)) unlinkSync(p);
    else if (e === "textures" && !isLink(p)) {
      const inner = readdirSync(p);
      if (inner.every((f) => isLink(join(p, f)))) { for (const f of inner) unlinkSync(join(p, f)); rmdirSync(p); }
    }
  }
  let n = 0;
  if (existsSync(publicSrc)) {
    for (const e of readdirSync(publicSrc)) {
      if (e.startsWith(".")) continue;
      symlinkSync(join(publicSrc, e), join(pub, e));
      n++;
    }
  }
  log(`Linked ${srcDir} → proj, public/ ${n} items`);
  const manifest = ["workbench.ts", "workbench.tsx"].some((f) => existsSync(join(srcDir, f)));
  if (!manifest) log("⚠ Project missing src/workbench.ts manifest: workbench will open, but cannot decompose/import (see references/workbench.md)");
}

// —— 3. Dependencies and index ——
if (!existsSync(join(wb, "node_modules"))) {
  log("First-time setup, installing dependencies…");
  const r = spawnSync("npm", ["install", "--ignore-scripts"], { cwd: wb, stdio: "inherit" });
  if (r.status !== 0) process.exit(r.status ?? 1);
}
{
  const r = spawnSync(process.execPath, [join(wb, "scripts", "gen-index.mjs")], { cwd: wb, stdio: "inherit" });
  if (r.status !== 0) process.exit(r.status ?? 1);
}

// —— 4. Dev server ——
const url = `http://localhost:${PORT}/`;
const alive = async () => { try { const r = await fetch(url, { signal: AbortSignal.timeout(1500) }); return r.ok; } catch { return false; } };
const viteBin = join(wb, "node_modules", "vite", "bin", "vite.js");
const pidFile = join(wb, ".dev.pid");
const readPid = () => { try { const n = Number(readFileSync(pidFile, "utf8").trim()); return Number.isInteger(n) && n > 1 ? n : null; } catch { return null; } };
const pidAlive = (pid) => { try { process.kill(pid, 0); return true; } catch { return false; } };
/** Process verification: command line must be workbench vite on same port — pid may be reused by OS */
const isOurVite = (pid) => {
  if (process.platform === "win32") return false;
  const r = spawnSync("ps", ["-o", "command=", "-p", String(pid)], { encoding: "utf8" });
  if (r.status !== 0) return false;
  const cmd = r.stdout.trim();
  return cmd.includes(viteBin) && cmd.includes(`--port ${PORT}`);
};

let managed = null; // Verified own server pid
{
  const pid = readPid();
  if (pid !== null) {
    if (!pidAlive(pid)) { unlinkSync(pidFile); log(`.dev.pid process ${pid} no longer running, cleaning up`); }
    else if (!isOurVite(pid)) { unlinkSync(pidFile); log(`.dev.pid process ${pid} is not workbench vite (pid reused), cleaning up`); }
    else managed = pid;
  }
}

if (relink) {
  // Relink: @proj alias is frozen when vite config loads, restart own server only
  if (managed) {
    try { process.kill(managed); log(`Restarting dev server (old pid ${managed})`); } catch { /* exited */ }
    unlinkSync(pidFile);
    const t0 = Date.now();
    while ((await alive()) && Date.now() - t0 < 10_000) await sleep(300);
  }
  if (await alive()) {
    die(
      `Port ${PORT} is in use by another server not started by this script (e.g. manual npm run dev). ` +
        `The @proj alias is fixed at startup; reloading won't load the new project. Please stop it or specify --port <other port>.`,
    );
  }
}

if (await alive()) {
  log(`Dev server already running at ${url} (index regenerated, refresh browser)`);
} else {
  const logFile = join(wb, ".dev.log");
  const fd = openSync(logFile, "a");
  const child = spawn(process.execPath, [viteBin, "--port", String(PORT), "--strictPort"], {
    cwd: wb, detached: true, stdio: ["ignore", fd, fd],
  });
  child.unref();
  writeFileSync(pidFile, String(child.pid));
  log(`Starting dev server (pid ${child.pid}, log ${logFile})…`);
  const t0 = Date.now();
  while (!(await alive())) {
    if (Date.now() - t0 > 90_000) die(`Dev server did not start within 90s, check ${logFile}`);
    if (!pidAlive(child.pid)) die(`Dev server exited immediately (port ${PORT} in use?), check ${logFile}`);
    await sleep(500);
  }
  log(`Dev server ready: ${url}`);
}

// —— 5. Open browser (?import=project: auto-import manifest if current project doesn't match) ——
const openUrl = url + (flag("no-import") ? "" : "?import=project");
if (!flag("no-open")) {
  const cmd = process.platform === "darwin" ? "open" : process.platform === "win32" ? "start" : "xdg-open";
  spawn(cmd, [openUrl], { stdio: "ignore", detached: true, shell: process.platform === "win32" }).unref();
}
console.log(`\nWorkbench: ${openUrl}\nStop dev server: kill $(cat ${pidFile})\n`);
