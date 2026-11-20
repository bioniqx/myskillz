# video-shotcraft Brand Guidelines

## Core Concept

Mark name: **Frame Chisel**

The open black frame represents a shot in the process of being framed; the amber diagonal facet serves both as an editing cut point and the chisel edge that carves motion into a crafted shot. The mark avoids literal depictions of cameras, play buttons, or film reels, directly embodying the core craft of video-shotcraft: **frame the motion, craft the shot.**

## Brand Palette

| Token | Name | Hex | Usage |
|---|---|---|---|
| `--brand-amber` | Frame Amber | `#D3923C` | Primary accent, key interactions, active state, chisel facet |
| `--brand-ink` | Stage Ink | `#171714` | Primary dark background, headlines, mark structure |
| `--brand-paper` | Cut Paper | `#F5F3EE` | Light background, dark-mode primary text |
| `--brand-slate` | Slate Gray | `#B5B0A5` | Secondary text, captions, annotations |

Recommended proportions: Stage Ink 70% / Cut Paper 20% / Frame Amber 10%. In high-density interfaces, Frame Amber should be restrained to 3–5%, highlighting only true focus points or cut boundaries.

Light mode tokens:

```css
:root {
  --brand-amber: #D3923C;
  --brand-ink: #171714;
  --brand-paper: #F5F3EE;
  --brand-slate: #716D64;
  --brand-line: #D9D5CC;
}
```

Dark mode tokens:

```css
:root {
  --brand-amber: #D3923C;
  --brand-ink: #171714;
  --brand-paper: #F0EDE5;
  --brand-slate: #B5B0A5;
  --brand-line: #3E3B34;
}
```

## Usage Rules

- Minimum display size: 16px in digital UI; below 24px, prefer the isolated mark without wordmark.
- Clear space: maintain at least 1/4 mark width on all sides.
- On dark backgrounds use `logo-mark-reverse.svg`; on light backgrounds use `logo-mark.svg`.
- For single-color printing, laser etching, and masks, use `logo-mark-mono.svg`.
- Wordmark typography: Avenir Next / Avenir / Inter, strictly lowercase `video-shotcraft`; never render in all-caps.
- Do not rotate the chisel cut angle, do not add glows, gradients, strokes, or drop shadows, and do not swap the amber accent with other hues.

## Brand Voice

English Motto: **Frame motion. Craft the shot.**
