---
name: type-rhythm-sync
summary: Two voice-and-beat synchronizations: font weight pulsing on percussion and spoken words filling like karaoke.
use: Sections where headlines / slogans bind tightly to audio tracks; Variant A binds to musical tempo (drum hits), Variant B binds to voiceover (spoken word tracking)
duration: A FontWeightPump 165f / B KaraokeFillSync 150f; A 128 BPM 14f per beat with 9–13f decay window; B 18–33f per word based on speech cadence
energy: A High (dance-floor pulse) / B Medium (guided reading flow)
tags: rhythm
---

## Intention
Previous typography cards in the library focused entirely on "how text enters the frame," offering nothing for "how text already on screen lives and breathes with the audio." These two variants provide the answer: Variant A turns headlines into rhythmic organs — letter strokes swell into heavy weights on bass hits and snap back, dancing to the beat as a visual subwoofer for high-energy segments; Variant B turns slogans into guided subtitles — words fill with color from left to right as the voiceover speaks them, pulling the viewer's gaze along during spoken emphasis segments. Their common principle: **text remains stationary while properties animate** — zero displacement, zero entrance/exit, purely font-weight and color breathing in lockstep with the sound track.

## Variant Selection
| Variant | Technique | Use Case |
|---|---|---|
| A font-weight-pump weight pulse | Fine-weight text snaps instantly to black weight on hit frames (continuous variable-weight interpolation), decaying back over 9–13f; accent beats expand 6% wider; bar 2 spawns stroke echo rows above/below, with drop beat settling into bold gradient poster | Music-driven high-energy sequences; titles acting as visual subwoofers |
| B karaoke-fill-sync voice tracking | Light-background two-line slogan (demo: "FRAME MOTION / CRAFT SHOTS"), each word filling left-to-right with soft edge matching speech speed; active word highlights in accent color, receding to primary ink after spoken; active word carries tracking underline | Voiceover / spoken pitch sequences; visual focus guidance across multi-word slogans |

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|---|---|---|
| Variant A pulse envelope | `env = (1 - t/D)^0.8` (t = frames since hit; demo staggers rebound from center 9f to edges 13f, exactly 0 when t≥D); fontWeight `250 + 650·env` continuous interpolation (SF Pro variable font); each glyph anchored in slots sized for **900 weight** — fine glyphs leave air at rest, closing gaps as strokes swell on impact without reflowing line; fallback when variable font unavailable: env>0.15 snaps 300↔900 with `-webkit-text-stroke` decay | Sizing slots for maximum font weight is vital: sizing for standard weight causes letters to collide and overlap at peak swell |
| Variant A tempo | 128 BPM at 14f per beat (16/30/…/114) + 9th beat drop (128f); beat 1 of each bar accentuates `scaleX = 1 + 0.06·env` and tints pink; drop hits 900 without receding, settling over ~16f at 780 weight + purple→pink gradient + horizontal light streak | Beat interval must exceed longest decay window (14>13); overlapping beats read as erratic spasm |
| Variant A echo rows | Starting bar 2, identical text with 2px stroke spawns above/below, pulsing 2f after main hit, pushed 26px outward per beat (pushed 60px on drop before snapping home) | Progression relies on "layering," not cranking amplitude; introducing echoes in bar 1 leaves nothing for subsequent escalation |
| Variant A beat reference | 8+1 step sequencer below screen (two bars + DROP cell); active cell lights up and scales 12%, past cells retain muted glow | In silent preview environments, this sequencer is required to communicate rhythm; animate only cells and text, never pumping the full screen |
| Variant B word schedule | Per-word [start, end] frame intervals with linear intra-word fill; 4–10f pause between words (breathing) | Production timestamps come from voiceover cue sheets; equal distribution sounds like synthetic machine speech |
| Variant B demo schedule | FRAME 20–38, MOTION 42–75 (long word spoken slowly), CRAFT 85–103, SHOTS 107–130; 0–19f prep, 130–149f static rest | Longer words get wider reading windows, reflecting natural human cadence |
| Variant B fill technique | Dual-layer identical text: bottom layer light grey (13% transparent ink) + top layer unmasked by progress: `mask-image: linear-gradient(90deg, #000 e-4%, transparent e+4%)`, e = p·108 - 4 (±4% soft leading edge; hard cut uses `clipPath: inset(0 (1-p)·100% 0 0)`); active word fills accent color, fading to primary ink over 10f once read | Dual layers per word avoid calculating full-row text width ratios; single-row masks require exact coordinate tables and drift easily |
| Variant B tracking bar | 8px rounded underline below active word (demo uses accent color), width = p·100%; retracts left-to-right over 6f once read | 4px light grey is invisible in 1080p thumbnails (lesson learned); remove underline once word is finished |
| Variant B voice reference | 48 vertical waveform bars below slogan: surging with speech, dipping during breath pauses, completed portions tinted accent | Silent preview environments require this waveform to signal that text is tracking speech |
| Resolution | True static rest ≥20f after Variant A final decay / Variant B final word fill | Rule R1: Breathing room requirement |

## Known Pitfalls
- The demo was tuned on placeholder copy — parameters serve as a tuning baseline, not a final production lock; verify with real assets during initial production.
- Both variants have **strict audio dependencies**: Variant A hit frames must match drum hits exactly; Variant B fill intervals must match voiceover word boundaries (anchor cues relative to audio start via sound-design §4.5) — without audio, Variant A looks like a glitch and Variant B looks like arbitrary color cycling; never use in silent segments.
- Variant A relies on system variable fonts (macOS SF Pro) for continuous wght interpolation; switching fonts or rendering on servers lacking variable font support degrades motion into stepped jumps — verify font loader and renderer support upfront, or fall back to stroke + stepped weights.
- Variant A is restricted to ≤1 segment per video (P4) — headlines dancing to the beat heavily dominate attention; running two segments creates conflicting visual noise.
- Variant B should contain ≤6 words per screen: larger word counts outpace comfortable reading speeds; break into multiple lines or shots.

## Reference Implementation
demos/typography/type-rhythm-sync/
(FontWeightPump.tsx / KaraokeFillSync.tsx)
