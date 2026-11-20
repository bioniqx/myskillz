// clipcard-looping — ClipCard crossfade looping regression card
// Covers three edge-case scenarios identified in maintainer review:
//   1) Unmuted (muted=false) crossfade loop — complementary fade-in/out volume without overlapping two full audio tracks in the transition zone;

//   2) startFrom>0 combined with loop — effective loop step = loopDurationInFrames - startFrom,
//      otherwise layers start playing from startFrom but step by full length, freezing at clip tail;
//   3) Short Sequence nested inside long Composition — layer count calculated from shot duration (durationInFrames prop)
//      rather than Composition total duration, avoiding rendering layers that are never visible.
//
// Asset: ClipCard src is a real mp4 under public/. Before rendering this demo, place a short video clip
// at public/clips/clipcard-demo.mp4 (recommended 30fps, square aspect ratio).
// All three scenarios share the same footage driven by different parameters for comparison.
import React from 'react';
import { AbsoluteFill, Sequence } from 'remotion';
import { ClipCard } from '../../../assets/lib/ClipCard';

export const CLIPCARD_LOOPING_DURATION = 120; // 4s @30fps
const CLIP = 'clips/clipcard-demo.mp4';

export const ClipCardLooping: React.FC = () => {
  return (
    <AbsoluteFill
      style={{
        background: '#0b0b0f',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        alignItems: 'center',
        gap: 36,
      }}
    >
      {/* Scenario 1: muted=false + loop — complementary audio fade-in, no doubled audio tracks */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
        <ClipCard
          src={CLIP}
          muted={false}
          loopDurationInFrames={60}
          loopCrossfadeInFrames={10}
          durationInFrames={120}
          size={200}
          caption="muted=false · loop"
          captionSize={11}
        />
        {/* Scenario 2: startFrom=12 + loop — effective step 60-12=48 */}
        <ClipCard
          src={CLIP}
          muted
          startFrom={12}
          loopDurationInFrames={60}
          loopCrossfadeInFrames={10}
          durationInFrames={120}
          size={200}
          caption="startFrom=12 · loop"
          captionSize={11}
        />
      </div>

      {/* Scenario 3: Short Sequence (120f) nested inside long Composition (if durationInFrames omitted,
          layer count calculated from useVideoConfig composition duration -> pass durationInFrames explicitly;
          wrapped in Sequence here to simulate short-shot-in-long-project structure) */}
      <Sequence name="short-shot" from={0} durationInFrames={120} layout="none">
        <div style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
          <ClipCard
            src={CLIP}
            muted
            loopDurationInFrames={45}
            loopCrossfadeInFrames={8}
            durationInFrames={120}
            size={200}
            caption="45f clip · 120f shot"
            captionSize={11}
          />
        </div>
      </Sequence>
    </AbsoluteFill>
  );
};
