import { existsSync, mkdirSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";

// @proj = external project source (connected via workbench/proj symlink, not committed; managed by scripts/open.mjs).
// Falls back to proj-stub when unlinked: builds and runs with a hint in Media tab.
// @demos = repo demos/ (relative symlink demosrc, committed) — 158 demo cards served directly as motion library.
// preserveSymlinks resolves virtual paths so 'react'/'remotion' bare imports resolve to local node_modules;
// src/proj.d.ts prevents tsc from typechecking external source.
const root = fileURLToPath(new URL(".", import.meta.url));
// Fall back to stub when project is linked without src/workbench.ts manifest (workbench imports @proj/workbench exclusively)
const proj = existsSync(path.join(root, "proj", "workbench.ts")) ? "proj" : "proj-stub";

/** Export video: launches Remotion CLI render within dev server.
 *  Frontend submits project JSON via POST /api/export, polling GET /api/export/:id for progress. */
type ExportJob = {
  status: "running" | "done" | "error";
  progress: number; // 0..1
  output: string; // output path relative to workbench
  lastLine: string;
  logTail: string[];
};

const renderExportPlugin = (): Plugin => {
  const jobs = new Map<string, ExportJob>();
  const stripAnsi = (s: string) => s.replace(/\x1b\[[0-9;]*[A-Za-z]/g, "");

  return {
    name: "wb-render-export",
    configureServer(server) {
      // Clean up temporary props files upon task completion (success/fail/sync error) and clear leftovers on startup
      const exportsDir = path.join(root, "exports");
      if (existsSync(exportsDir)) {
        for (const f of readdirSync(exportsDir)) {
          if (/^\.props-[a-z0-9]+\.json$/.test(f)) rmSync(path.join(exportsDir, f), { force: true });
        }
      }
      server.middlewares.use("/api/export", (req, res) => {
        const send = (code: number, body: unknown) => {
          res.statusCode = code;
          res.setHeader("Content-Type", "application/json");
          res.end(JSON.stringify(body));
        };
        const sub = (req.url ?? "/").split("?")[0];

        // POST /api/export — Submit render
        if (req.method === "POST" && (sub === "/" || sub === "")) {
          if ([...jobs.values()].some((j) => j.status === "running")) {
            send(409, { error: "A render is already in progress" });
            return;
          }
          let raw = "";
          req.on("data", (c) => (raw += c));
          req.on("end", () => {
            let project: { name?: string };
            try {
              project = JSON.parse(raw).project;
              if (!project) throw new Error("no project");
            } catch {
              send(400, { error: "Missing project JSON" });
              return;
            }
            const id = Date.now().toString(36);
            const outDir = path.join(root, "exports");
            mkdirSync(outDir, { recursive: true });
            const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
            const safeName =
              (project.name ?? "project").replace(/[^\w·-]+/g, "_").slice(0, 40) || "project";
            const output = `exports/${safeName}-${stamp}.mp4`;
            const propsFile = path.join(outDir, `.props-${id}.json`);
            writeFileSync(propsFile, JSON.stringify({ project, renderExact: true }));
            const dropProps = () => rmSync(propsFile, { force: true });

            const job: ExportJob = {
              status: "running",
              progress: 0,
              output,
              lastLine: "Syncing assets…",
              logTail: [],
            };
            jobs.set(id, job);

            const onChunk = (buf: Buffer) => {
              const lines = stripAnsi(buf.toString()).split(/[\r\n]+/).filter((l) => l.trim());
              for (const line of lines) {
                job.lastLine = line.trim();
                job.logTail = [...job.logTail, line.trim()].slice(-40);
                // Remotion CLI progress format: "Rendered 123/5544", take last a/b
                const m = [...line.matchAll(/(\d+)\/(\d+)/g)].pop();
                if (m && Number(m[2]) > 0) job.progress = Number(m[1]) / Number(m[2]);
              }
            };

            // Remotion static server restricts symlinks (returns 404 for symlinked paths).
            // Dereference and sync public/ to a real folder before rendering, pointing via --public-dir.
            const renderPublic = path.join(root, ".render-public");
            const rsync = spawn(
              "rsync",
              ["-aL", "--delete", "--exclude=cardpreviews", "public/", `${renderPublic}/`],
              { cwd: root },
            );
            rsync.stderr.on("data", onChunk);
            rsync.on("close", (rc) => {
              if (rc !== 0) {
                dropProps();
                job.status = "error";
                job.lastLine = `Asset sync failed (rsync exit code ${rc}): ${job.lastLine}`;
                return;
              }
              const bin = path.join(root, "node_modules", ".bin", "remotion");
              const child = spawn(
                bin,
                [
                  "render",
                  "src/remotion/index.ts",
                  "Main",
                  output,
                  `--props=${propsFile}`,
                  `--public-dir=${renderPublic}`,
                ],
                { cwd: root },
              );
              child.stdout.on("data", onChunk);
              child.stderr.on("data", onChunk);
              child.on("close", (code) => {
                dropProps(); // Props read at launch, safe to drop
                job.status = code === 0 ? "done" : "error";
                if (code === 0) job.progress = 1;
                else {
                  // Surface most informative error line to UI
                  const err = job.logTail.find((l) => l.includes("Error"));
                  if (err) job.lastLine = err;
                }
              });
            });
            send(200, { id });
          });
          return;
        }

        // GET /api/export/:id — Poll progress
        const m = sub.match(/^\/([a-z0-9]+)(\/reveal)?$/);
        const job = m ? jobs.get(m[1]) : undefined;
        if (!job) {
          send(404, { error: "Task not found" });
          return;
        }
        // POST /api/export/:id/reveal — Reveal in Finder
        if (req.method === "POST" && m![2]) {
          if (process.platform === "darwin") spawn("open", ["-R", path.join(root, job.output)]);
          send(200, { ok: true });
          return;
        }
        send(200, job);
      });
    },
  };
};

export default defineConfig({
  plugins: [react(), renderExportPlugin()],
  // Port 5198: decoupled from video-talkcraft (5199), allowing concurrent runs
  server: { port: 5198, strictPort: true },
  resolve: {
    preserveSymlinks: true,
    alias: { "@proj": path.join(root, proj), "@demos": path.join(root, "demosrc") },
  },
  // Ensure pre-bundle includes bare imports from symlinked external project / demos
  optimizeDeps: { include: ["react", "react-dom", "remotion", "@remotion/motion-blur"] },
});
