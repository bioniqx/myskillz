---
name: voice-waveform-live
summary: A recording capsule shows 64 live bars that surge with speech, shrink to a dotted line in pauses, and collapse on submit.
use: Feature shots for voice input / AI assistants signaling "listening to you"; segments lacking UI content to showcase but requiring continuous vitality to sustain the screen
duration: 172f (~5.7s: entrance 14f + speech 1.4s + pause 0.8s + speech 1.4s + submit collapse / tuck into bubble 0.8s + hold 0.7s)
energy: Medium (functional vitality, not visual flexing)
---

## Intention
This card provides a **functional** waveform: a live receipt of "listening to you." The linchpin lies in causality: the waveform pulses with "user speech" as a core product capability, rather than decorative packaging dancing to BGM. Waveform surges when speaking, collapses into dotted lines during pauses, and historical waves stream leftward—viewers perceive "it is truly listening" from the wave undulations, sustaining 6s+ of screen time purely through vitality without needing other content. Division of labor with gauge-readout-moves: gauges represent mechanical rituals of "reporting a value," whereas this card represents the vital signs of "continuous monitoring," devoid of terminal values.

## Motion Core
- **Frame-deterministic pseudorandomness is essential**: mulberry32 integer sampling + smoothstep adjacent interpolation (value noise), zero Math.random—rendering is reproducible with seamless frame continuity.
- Scrolling sensation: Bar i sampling instant = f - (N-1-i)*1.6, where the rightmost bar is "now" and history flows leftward; bars do not translate, but rather sample signals at different points in time.
- Bar height = speech envelope (trapezoidal seg speech/pause states + syllable noise 0.55+0.45*noise) * central spatial weight sin^0.8 * per-bar jitter (0.35+0.65*noise); silence clamped to 6px dotted line.
- Submit: button compresses scale 1->0.82->1 rebound over 3f, waveform collapses to 0.06 over 12f ease-in, microphone breath ring expands with envelope.
- Demo adds real-time transcription (92px bold): each word rises from transparent to solid at its syllable start, spoken words highlight in accent color before settling to ink after several frames, and cursor blinks during pauses; on submit, entire transcription moves up, shrinks, and packs into accent message bubble—"pause" is legible in both text and waveform, culminating in a complete dialogue poster.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|---|---|---|
| Bar count / gap | 64 bars, gap 5px (1240px wide pill, waveform zone ~820px) | Fewer than 40 bars reads like an equalizer; denser than 90 bars loses individual bar motion |
| Scroll speed | 1.6 frames / sample point | Faster scrolls history too quickly like a glitch; slower loses scroll sensation into stationary jitter |
| Speech-pause envelope | Trapezoidal rise 5f / fall 7f; demo speech 15–57f, pause 80–124f | Pause segments must truly collapse to dotted lines—without pause contrast, speech cannot register |
| Syllable noise | 0.55+0.45*noiseAt(t/4.5) | Removing syllable layer renders waveform as smooth hills, losing cadence of spoken phrases |
| Central weighting | sin^0.8 spatial envelope | Without weighting, uniform height reads like equalizer; exponent >1.5 creates isolated spike in center |
| Silence clamp | max 6px dotted line (neutral muted color for dots, accent gradient for active bars) | Clamping to 0 causes waveform to vanish, reading like disconnected line; dotted line means "listening, but you aren't speaking" |
| Submit collapse | 12f ease-in to 0.06 + button compression rebound 3f | Collapse signals "this passage was ingested"; fade out fails to convey submission semantics |
| Transcription pace | Word appears at syllable onset (within envelope rise), 8f fade-in | Word preceding waveform reads like subtitles ahead of voice; lagging by >10f reads as transcription latency |
| Pack into bubble | 22f EASE.swift upward shift + scale to 0.72, bubble background / white text follow over 10f | Fading transcription alone fails to convey "sent" |

## Known Pitfalls
- Demo calibrated on warm, light stage for video-shotcraft voice dictation storyboard ("Shotcraft is listening")—parameters are a tuning starting point, not final production lock; re-verify against real assets in initial production.
- **Waveform must synchronize with vocal track when audio exists**: if video includes real voiceover/narration, envelope speech-pause segments must align with audio track pauses—a 1s offset immediately breaks illusion; purely synthetic envelopes apply only to music-only videos.
- Demo uses a light warm-white solid pill (top 1.5px inner highlight + dual drop shadows); for dark videos, swap for 1.5px gradient-border glass pill while keeping waveform parameters unchanged.
- Microphone is an SVG line icon (replacing early emoji + grayscale placeholder); swap according to brand icon library in production.
- Audio: visuals represent the "shape of sound," pairing most naturally with voiceover; submit button pairs with light pop + collapse pairs with short descending whoosh.

## Reference Implementation
demos/interaction/voice-waveform-live/
(VoiceWaveformLive.tsx)
Source: raycast-teams 19.5–26.0s
