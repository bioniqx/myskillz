---
name: document-typewriter-reveal
summary: A fully typeset document writes itself behind one accent-color caret, opens both side columns, and drops history entries into the rail.
use: Feature shots for document/report/note products; the single beat with the highest information density
duration: 150f (~5s, including history-list-stack tail and slogan hold)
energy: Low-medium (highest information density, paced steadily so viewers can read text)
tags: ui-entrance
---

## Intention
The audience will read every word on screen — this shot's persuasive power rests entirely on the conviction that "the document is real." Typewriter-style composition turns a static page into an "actively authored document," while history entries dropping into the sidebar add temporal depth representing continuous output.

## Motion Core
- Content blocks are written in pairs to the beat: background color masks anchored right contract from left to right, with an accent-colored caret riding the leading edge of reveal.
- Person @-mentions sprout an accent background color after the wipe completes.
- Dual sidebars enter via background patches retracting top-to-bottom, with an inner-edge accent hairline drawing along the reveal and fading out.
- Tail segment (history-list-stack): 6 history items drop into the sidebar track from above one by one, each accompanied by a distinct pop sound.
- Camera pulls back from an oblique headline close-up to the full window (both sidebars must remain in frame), then tilts down slightly and moves up to yield bottom space for a slogan, executing an ultra-slow push-in; the page is an application window floating in a dark field (rounded corners, bright border, backlight, long shadow) rather than filling the entire screen.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|---|---|---|
| Typing cadence | 20 blocks in pairs, pair g cues at = 8 + g·4.4, each block wipes in 9f, final pair finishes at ~57f (before full window settles at 64f) | Typing block-by-block sequentially blows the frame budget — "block count × cadence must match budget upfront" is the core arithmetic of this card; calculate before coding |
| Reveal technique | Background mask width 100%→0, bezier(0.4,0,0.6,1); mask color sampled from real textured paper, over-covering on the right (120px on headings — measured block width is shorter than actual bold text width, risking tail leakage); 3px accent caret (deeper aurora purple + matching soft glow) tracks only the active block, riding only within actual text width, fading out 2f after writing finishes; caret blinks on standby at headline start 8f before first block starts typing | Multiple simultaneous carets instantly break immersion; maintain strictly one "pen tip" |
| List bullets (li) | Mask extends 28px extra to the left (::marker sits ~22px left of text) | Failing to over-cover bullets leaks them prematurely — inspect every typographic detail baked into screenshot textures |
| @-mentions | 4f after wipe completes, 8f to grow accent background (aurora purple 0.4), `mix-blend-mode: multiply` (background overlays above textured text; normal blend washes out names); skip non-person headings | Highlighting arriving after writing reads as "emphasis being applied"; same-frame appearance looks like a flat texture |
| Dual sidebar entrance | Left column cue 54 / Right column cue 62, background patch retracts top-to-bottom in 10f + 2px inner-edge accent line grows with reveal and fades over 24f | Sidebars stagger cadence against body text; simultaneous entrances fight for visual attention |
| History items drop | 6 items, cue = 66 + i·5 (placed after sidebar wipe settles at 64f), each drops in 9f; starts at -48px, bezier(0.2,1.15,0.3,1) light bounce, airborne shadow `0 12·air px 24·air px` | Item geometry sits flush beneath existing items baked into texture, matching line-height — DOM-redrawn items must align strictly with active items in texture |
| Stage | Aurora dark field: accent backlight halo behind window (translateZ -40 in page space, following window perspective), 0 0 0 1.5px bright rim + 70px long shadow, top-edge highlight; ending slogan 84px in two segments (second segment in accent color) left-aligned to window left edge | Warm white paper placed in a cool dark field acts like a lantern — stage and window must share lighting direction; backlight must never overpower paper surface |
| Camera | Custom 3D window camera (layout-level CSS zoom, Q2), monotonic cubic Hermite spline unrolled per frame: f0 zoom 1.42 / rotY -18° / rotX 8° (window top-left corner and stage light enter frame simultaneously) → f26 1.24 → f64 full window 0.86 → f104 0.74 + rotX 9° + move up 78px (yielding bottom to slogan) → f150 0.746 | Opening too close (>1.6x) covers the entire screen in paper, hiding dark field and window borders, reading as a flat original page; full-window view must frame both sidebars (Q10) |

## Audio
Typing segment locks keyboard.mp3 trimmed to ~50f (8→57f) covering the writing sequence (Foley strictly matches action duration, S4); history items feature 6 consecutive pops every 5f, with volume stepping down 0.40→0.25 for distance falloff (S2).

## Known Pitfalls
- Mock content must be publication-grade: native product layout, full text density, and sidebars fully framed (Q10) — perfunctory "texture + slogan" mockups will require a full reshoot.
- Data compliance: Never use real customer or team member names in mock content (Q1).
- When source pages are live data sources (collaborative docs), full recaptures wipe finalized textures — use incremental scripts to refresh only single pages or single keys.
- Accent color examples (caret / @-mentions / inner hairline) use amber in the reference template video; update uniformly to the target brand accent color for new projects.

## Reference Implementation
demos/ui-entrance/document-typewriter-reveal/DocumentTypewriterReveal.tsx (originally template/src/aifl/live/SceneWbr.tsx; typing sound effects in template/src/aifl/Main.tsx SFX table; in the template video, this shot represents a weekly report document scene)
