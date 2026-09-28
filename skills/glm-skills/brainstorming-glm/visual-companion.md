# Visual Companion Guide

Browser-based companion for mockups, diagrams, and side-by-side visual
options. Read this only after the user accepts the offer.

## When to use (per question, not per session)

Test: **would the user understand this better by seeing it?**

Browser: UI mockups/wireframes/layouts, architecture and flow diagrams,
side-by-side visual comparisons, look-and-feel/spacing/hierarchy,
state machines and entity relationships drawn as diagrams.

Terminal: requirements and scope, conceptual A/B/C choices described in
words, trade-off lists, API/data-model decisions, anything whose answer
is words. "What kind of wizard?" is terminal; "which of these wizard
layouts?" is browser.

## Speed rules

The loop is human-gated; hide machine latency inside the human wait.

- **One turn, one bundle.** Liveness check + `events` read + new screen
  write + any read-only exploration or web lanes for upcoming questions
  are batched tool calls in a single message. Never spread across messages.
- **Pre-draft the next screen** while the user looks at the current
  one, but do NOT write it to `screen_dir` early — the server serves the
  newest file, so writing early replaces what they are looking at.
  Write it the instant the current step validates.
- **Iterate cheaply.** Small revisions → copy the file and edit only
  the changed fragment into `layout-v2.html`; don't regenerate.
- **Bundle visual questions.** If two visual questions are independent,
  put both on one screen (two sections, two option groups) and let one
  reply resolve both.
- **Write screens at `reasoning_effort: low`.** Producing HTML is
  mechanical; deep reasoning here only adds latency at ~63 tok/s.
- **Delegate screen writing to a Flash lane** when the screen is long
  (a full mockup set) and you have other work in the same turn. Give the
  lane the exact fragment contract below and a word cap; Flash is
  verbose unless bounded.

## How it works

The server watches `screen_dir` and serves the newest `.html` to the
browser; clicks are appended as JSON lines to `state_dir/events`, which
you read next turn. If your file starts with `<!DOCTYPE` or `<html` it
is served as-is (helper script injected); otherwise it is wrapped in the
frame template (header, theme CSS, connection status, interactivity).
**Write fragments by default.**

## Starting

```bash
# Only after the user accepts. <skill_dir> is printed in SKILL.md's Live
# context. --open opens their browser on the first screen; --project-dir
# persists mockups and enables same-port restart.
<skill_dir>/scripts/start-server.sh --project-dir /path/to/project --open
# → {"type":"server-started","port":52341,"url":"http://localhost:52341/?key=…",
#    "screen_dir":".../.superpowers/brainstorm/<id>/content",
#    "state_dir":".../.superpowers/brainstorm/<id>/state"}
```

Save `screen_dir` and `state_dir`. The URL carries a session key
(`?key=…`); always share the **complete** URL as a fallback for
headless/remote setups, never a bare host:port. If you didn't capture
stdout, read `$STATE_DIR/server-info`. Remind the user to gitignore
`.superpowers/` if it isn't already.

Reading screenshots back: GLM-5.3-Flash is natively multimodal, so a
Flash lane can look at a screenshot of the rendered page if you need a
visual check. GLM-5.3 is text-only — do not send it images.

Platform notes: Claude Code — run as above (script backgrounds itself;
on Windows it auto-foregrounds, so pass `run_in_background: true` and
read `server-info` next turn). Codex — auto-foregrounds via `CODEX_CI`,
run normally. Gemini CLI — add `--foreground` and set
`is_background: true`. Copilot CLI — `bash scripts/start-server.sh …
--foreground` via its background shell mechanism. Any harness that
reaps detached processes → `--foreground` + its background mechanism.
Unreachable URL in containers → `--host 0.0.0.0 --url-host localhost`.

## The loop

1. **Same message:** confirm alive (`$STATE_DIR/server-info` exists and
   `server-stopped` does not; if stopped, restart with the same
   `--project-dir` — it reuses the port and the open tab reconnects),
   read `$STATE_DIR/events` if present, write the new screen with your
   file-creation tool (never cat/heredoc) under a fresh semantic name
   (`layout.html`, `layout-v2.html` — never reuse a filename).
2. **End the turn** with: the URL, a one-line summary of what's on
   screen, and "Take a look — click an option if you like, then reply
   here."
3. **Next turn:** merge `events` (JSONL of clicks; last `choice` is
   usually the final pick, the click path shows hesitation) with the
   terminal reply. Terminal text wins. No `events` file = no browser
   interaction.
4. Iterate (`-v2`) or advance. When the next step is terminal-only,
   push a waiting screen so a resolved choice isn't left on display:
   ```html
   <div style="display:flex;align-items:center;justify-content:center;min-height:60vh">
     <p class="subtitle">Continuing in terminal...</p>
   </div>
   ```

Server auto-exits after 4h idle (`--idle-timeout-minutes`). Stop with
`<skill_dir>/scripts/stop-server.sh $SESSION_DIR`; `--project-dir` sessions keep
their mockups, `/tmp` sessions are deleted.

## Writing fragments

```html
<h2>Which layout works better?</h2>
<p class="subtitle">Consider readability and visual hierarchy</p>
<div class="options">
  <div class="option" data-choice="a" onclick="toggleSelect(this)">
    <div class="letter">A</div>
    <div class="content"><h3>Single Column</h3><p>Clean, focused reading</p></div>
  </div>
  <div class="option" data-choice="b" onclick="toggleSelect(this)">
    <div class="letter">B</div>
    <div class="content"><h3>Two Column</h3><p>Sidebar navigation</p></div>
  </div>
</div>
```

No `<html>`, CSS, or `<script>` needed.

## CSS classes provided by the frame

- **Options:** `.options > .option[data-choice][onclick="toggleSelect(this)"] > .letter + .content(h3,p)`.
  Add `data-multiselect` on `.options` for multi-select toggling.
- **Cards:** `.cards > .card[data-choice][onclick="toggleSelect(this)"] > .card-image + .card-body(h3,p)`.
- **Mockup:** `.mockup > .mockup-header + .mockup-body`.
- **Split view:** `.split > .mockup + .mockup`.
- **Pros/cons:** `.pros-cons > .pros(h4,ul) + .cons(h4,ul)`.
- **Wireframe blocks:** `.mock-nav`, `.mock-sidebar`, `.mock-content`,
  `.mock-button`, `.mock-input`, `.placeholder`.
- **Typography:** `h2` page title, `h3` section heading, `.subtitle`,
  `.section`, `.label` (small uppercase).

Full CSS: `scripts/frame-template.html`. Client helper: `scripts/helper.js`.

## Events format

```jsonl
{"type":"click","choice":"a","text":"Option A - Simple Layout","timestamp":1706000101}
{"type":"click","choice":"c","text":"Option C - Complex Grid","timestamp":1706000108}
```

The file is cleared automatically when a new screen is pushed.

## Design tips

Scale fidelity to the question (wireframes for layout, polish for
polish). State the question on every screen. 2-4 options per group.
Use real content when it matters (real images for a photo portfolio).
Keep mockups structural, not pixel-perfect.
