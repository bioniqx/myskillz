# Shot Redesign · Round 2 Execution Brief (Required reading for all participating agents)

## 0. Objective for this round

Round 1 (`shot-polish/after-v1/`) focused on "conservative polish": keeping original geometry, palette, and pacing while adding shadows, grain, and easings. The result was clean but plain—light gray background, identical indigo, small fonts, sparse composition, and unchanged pacing. User feedback:

> I want **substantial** improvements across **pacing, motion curves, visual rendering, palette, design, and typography**;
> **You do not need to strictly adhere to the original video, only follow the approximate shot design of the original video**.

Therefore, this round is a **complete redesign**, not mere polish. Standard: treat each shot as one destined for a top-tier product launch film (Apple Keynote, Linear / Stripe / Vercel / Arc launch films) or an elite motion designer's reel.
Paused on any frame, it should look like a designed poster; in playback, pacing must breathe with weight and intentionality.
**When placed side by side with before and after-v1, the upgrade must be immediately obvious and substantial.** Changes that merely add shadows or grain are unacceptable.

## 1. What to keep, what to open up

**Keep only the "approximate shot design"**—namely the motion technique itself described in the card's "summary / intention":
crash zoom remains a crash zoom, clock wipe remains a radial clock wipe transition, split text stagger remains staggered character entry, and counter confetti remains confetti on counter completion. The signature recognizability of the technique must be enhanced, never transformed into a different technique.

**Everything else can be reworked**:
- Palette (change look), background, lighting, materials;
- Typography and composition (hero scale, position, grid, negative space);
- Content and copy (product names, numbers, headlines, UI content—craft better copy; use only fictional brands, never real company/product names);
- Type design (font size, weight, tracking, hierarchy, bilingual/English typographic polish);
- Rhythm and duration (the value of `*_DURATION` can change, constant name remains); motion curves, staggering, springs, camera paths;
- You may dispense with generic `_fixtures/Fixtures.tsx` (FakeDashboard / Card / TitleBlock) in favor of custom-built scenes tailored for the shot (generic small-text dashboards are hard to read and visually unexciting in motion);
- Copy language: English if originally English, Chinese if originally Chinese; debug/placeholder text (like shot name capitalized in corners) must be deleted or replaced with actual content.

## 2. Six Look Visual Systems (`demos/_fixtures/Look.tsx`)

Choose an explicit visual tone per shot; never default to washed-out gray:
- `paper`: warm off-white paper, crisp ink, serif headlines, vermilion or amber accents (editorial / publication style).
- `terminal`: deep obsidian/slate dark theme, monospace fonts, lime/cyan data glows (developer tools / infrastructure).
- `swiss`: bold primary poster colors (cobalt, vermilion, lemon), heavy grotesque typography, stark negative space (design tools / graphic craft).
- `glass`: frosted blur, soft gradient refraction, refined micro-borders (modern OS / luxury consumer web).
- `porcelain`: clean clinical white/silver, electric blue accents, pristine surfaces (enterprise SaaS / data platforms).
- `monochrome`: stark high-contrast black and white, zero chromatic distraction, pure typographic geometry.

## 3. Review Bar
- Side-by-side comparison with before and after-v1 must show clear superiority.
- Clean execution, zero layout clipping or type overlap.
- Timing must feel physically grounded with clear easing and rest pauses.
