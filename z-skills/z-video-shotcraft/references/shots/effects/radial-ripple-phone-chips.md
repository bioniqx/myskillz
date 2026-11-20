---
name: radial-ripple-phone-chips
summary: Four concentric grey circles breathe out of phase like water ripples while a centered phone mockup auto-scrolls its feed and two white feature chips spring in and hover.
use: The "here it is" hero freeze-frame for mobile products; feature breakdown sections flanking both sides; opening or closing product overviews
duration: ~5.6s (168f @ 30fps)
energy: Low (serene, breathing feel, sustained by the continuous ripple motion to keep the shot alive)
---

## Intention
Anchor a mobile phone at screen center with minimal motion while keeping it undeniably "alive": concentric circles provide atmospheric breathing, in-screen auto-scrolling proves "live content is running inside," and flanking chips highlight feature names. All three motion layers run at deliberate, slow paces, combining so the composition never feels frozen—the gold standard for product hero beauty shots.

## Motion Core
- Demo framing (look = sand, phone displays video-shotcraft shot library feed): 1080p native layout coordinates (bypassing DesignStage scaling), phone 430x900 occupying 83% canvas height; engraved mark + video-shotcraft wordmark rise in the bottom-left after both chips settle, concluding on a product poster.
- 4 concentric circles (2240/1760/1280/840px, #dccbb4->#f2eadf from dark to light, outer two layers spilling beyond canvas) each scale 1 ± 0.06 over 1.5 sine cycles, with a 1.7 rad phase offset between adjacent layers—phase offset is crucial for "ripples" rather than "monolithic scaling"; each layer features illuminated upper rims + white hairline outer edges, with warm white soft light cradling the phone at center.
- Phone: warm titanium metal frame 12px + 9px bezel, 70px corner radius, dynamic island / side buttons / diagonal glass specular reflection, two-tier contact shadows; rises snappy 90px from below over 0–26f, shadows tightening upon landing.
- Custom feed designed for the shot: large title + featured hero card + 8 episode cards (geometric illustration covers / titles / duration & show / progress), fixed mini player bar at bottom (constant progress bar advance, deterministic waveform pulses), status bar and player bar underlaid with canvas color gradients.
- Feed translateY 0->-560px across window t 0.08->0.98 **constant linear velocity with zero easing**.
- Chip pop: springAt(t0, damping: 13, stiffness: 190) drives scale 0.8->1 (single visible overshoot), simultaneously shifting outward 28px snappy from phone edge, opacity jumping to full in 5f; left chip starts at 37f, right chip at 67f.
- Following pop, chips engage sine hover ±8px (2 cycles across shot), phasing in smoothly over 24f starting 18f post-pop—floating does not start abruptly upon landing.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| Concentric circle layers / sizes | 4 layers: 2240/1760/1280/840px (1080p) | 3 layers fail to fill the frame; outer layer must bleed off-canvas, or it looks like a round color swatch |
| Breathing amplitude | scale 1 ± 0.06, 1.5 cycles across shot | 0.06 is the ceiling; 0.1 reads as a "pulsing animation" rather than water ripples |
| Phase offset | 1.7 rad between adjacent layers | Identical phase = uniform scale pulse; 1.7 offset creates the illusion of outward radiating waves |
| Phone shadows | Crisp contact shadow 0 4px 10px + ambient shadow 0 40px 80px -20px + environment shadow 0 90px 140px -40px (sand.shadow tinted) | Shadows provide the sole anchor for the phone "floating above ripples"; removing them flattens depth |
| Auto-scroll | translateY 0->-560px, t 0.08->0.98 linear | Adding easing immediately reads as "someone swiping"; linear speed conveys automated playback |
| Chip pop | spring damping 13 / stiffness 190, scale 0.8->1, 28px outward shift | Overshoot delivers the entire tactile pop sensation; damping >20 feels flat |
| Chip timing | Left 37f / Right 67f (1s stagger) | Simultaneous arrival reads like two labels; staggering creates an unhurried "one by one" narrative cadence |
| Chip hover | ±8px, 2 cycles, smoothly fading in over 24f starting 18f post-pop | Amplitudes over ~12px compete with the concentric ripples |
| Chip font size | 36px / 600 weight + 60px accent icon circle | Under 1080p, chips must be readable words, not tiny 12–20px sticker tags |

## Known Pitfalls
- Chips anchor against the phone's outer edge via `right: 1920 − PX + CHIP_GAP` / `left: PX + PW + CHIP_GAP`; modifying phone width PW updates chip positions automatically, but verify that longer text chips stay inside the 96px safety margins.
- In-screen feed contains mock placeholder items; when substituting real product screenshots, total content height must exceed `560px + screen_height`, otherwise scrolling exposes blank voids.
- Mobile display width is only ~390px: constrain episode card titles to ~18 characters with `nowrap + ellipsis` on metadata, preventing text wrap from breaking card heights.
- Concentric circles are stacked solid surfaces (not stroke rings); layers must be appended in order from largest to smallest, otherwise the largest layer conceals smaller ones.
- ACCENT (default sand terracotta `#c4552d`) governs in-screen covers, progress bars, play buttons, and chip icons; reskinning requires modifying only this single variable.

## Reference Implementation
demos/effects/radial-ripple-phone-chips/
(RadialRipplePhoneChips.tsx)
