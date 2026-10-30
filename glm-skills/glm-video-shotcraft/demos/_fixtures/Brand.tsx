// video-shotcraft brand assets — standardized logo / brand name / pitch for demos:
// Mark <ShotcraftMark> ("Frame Chisel": open frame + amber bevel cut, same paths as assets/brand/logo-mark.svg),
// Wordmark <ShotcraftWordmark>, BRAND palette, PITCH copy library. Spec in assets/brand/BRAND.md:
// Wordmark is all-lowercase; mark has no rotation, glow, gradient, stroke, or shadow. Amber is sole accent.
// Pure props functions depending only on react; bundle alongside demo copies.
import React from 'react';

export const BRAND = {
  name: 'video-shotcraft', // Official name: lowercase + hyphen
  short: 'Shotcraft', // Short name for inline or tight spaces
  repo: 'github.com/Vincentwei1021/video-shotcraft',
  amber: '#D3923C', // Bevel cut color = brand accent
  ink: '#171714', // Frame color on light background
  paper: '#F5F3EE', // Frame color on dark background (inverted) / light background
  slate: '#B5B0A5', // Secondary text (dark background)
  font: '"Avenir Next", Avenir, Inter, "Helvetica Neue", "PingFang SC", Arial, sans-serif', // Wordmark font family
} as const;

// Two paths of the mark (viewBox 0 0 128 128): frame = open frame, cut = bevel cut. Exported separately for animation staging
// (frame draws out first / cut slides in, independent sheen, etc.).
export const MARK_PATHS = {
  frame: 'M16 16h96v26H42v44h70v26H16V16Z',
  cut: 'M92 48h28L84 84H56l36-36Z',
} as const;

// Mark. tone="dark" for dark ground, "light" for light ground; frameColor / cutColor can override.
// cutProgress 0->1: bevel cut slides in along its axis (default 1); frameProgress clips stroke proportionally.
export const ShotcraftMark: React.FC<{
  size?: number; tone?: 'dark' | 'light'; frameColor?: string; cutColor?: string;
  frameProgress?: number; cutProgress?: number; style?: React.CSSProperties;
}> = ({ size = 96, tone = 'dark', frameColor, cutColor, frameProgress = 1, cutProgress = 1, style }) => {
  const id = React.useId().replace(/[^a-zA-Z0-9]/g, '');
  const fp = Math.max(0, Math.min(1, frameProgress));
  const cp = Math.max(0, Math.min(1, cutProgress));
  return (
    <svg width={size} height={size} viewBox="0 0 128 128" style={{ display: 'block', overflow: 'visible', ...style }}>
      <defs>
        {/* Frame: reveal left-to-right */}
        <clipPath id={`f${id}`}><rect x={16} y={0} width={96 * fp} height={128} /></clipPath>
        {/* Cut: slide along 45-deg angle bottom-left to top-right */}
        <clipPath id={`c${id}`}><polygon points={`56,84 ${56 + 36 * cp},${84 - 36 * cp} ${84 + 36 * cp},${84 - 36 * cp} 84,84`} /></clipPath>
      </defs>
      {fp > 0 && <path d={MARK_PATHS.frame} fill={frameColor ?? (tone === 'dark' ? BRAND.paper : BRAND.ink)} clipPath={fp < 1 ? `url(#f${id})` : undefined} />}
      {cp > 0 && <path d={MARK_PATHS.cut} fill={cutColor ?? BRAND.amber} clipPath={cp < 1 ? `url(#c${id})` : undefined} />}
    </svg>
  );
};

// Wordmark: mark + video-shotcraft horizontal lockup (mark height ~= 2.1x font size, 700 weight, +0.03em letter-spacing).
// size = font size (px); mark={false} renders wordmark only.
export const ShotcraftWordmark: React.FC<{
  size?: number; tone?: 'dark' | 'light'; color?: string; mark?: boolean;
  markScale?: number; gap?: number; weight?: number; fontFamily?: string; style?: React.CSSProperties;
}> = ({ size = 48, tone = 'dark', color, mark = true, markScale = 2.1, gap, weight, fontFamily, style }) => (
  <div style={{ display: 'inline-flex', alignItems: 'center', gap: gap ?? size * 0.5, ...style }}>
    {mark && <ShotcraftMark size={size * markScale} tone={tone} />}
    <span style={{
      fontFamily: fontFamily ?? BRAND.font,
      fontSize: size, fontWeight: weight ?? 700, lineHeight: 1, letterSpacing: '0.03em', whiteSpace: 'nowrap',
      color: color ?? (tone === 'dark' ? BRAND.paper : BRAND.ink),
    }}>{BRAND.name}</span>
  </div>
);

// Pitch copy library — slogans / titles / subtitles / testimonials; avoid unverified numbers
// (never hardcode volatile card counts, star counts, or user counts in video).
export const PITCH = {
  en: {
    motto: 'Frame motion. Craft the shot.', // Brand motto (BRAND.md)
    taglines: [
      'One prompt to a finished promo.',
      'Cinematic product videos, crafted by your agent.',
      'Every shot, tuned in one place.',
      'Shot recipes for cinematic product films.',
      'Storyboard. Animate. Sound-design. Deliver.',
      'Your product, in motion.',
      'From screenshot to showreel.',
      'Direct the film. Let the agent shoot it.',
    ],
    features: [
      'Shot recipe cards', 'Real page captures', '2.5D camera moves', 'Beat-synced cuts',
      'Film-grade SFX', 'Motion workbench', 'Remotion render', 'JianYing export',
    ],
    praise: [
      'Feels like a launch film from a real studio.',
      'The first agent skill that actually understands pacing.',
      'Our promo shipped the same afternoon.',
      'Camera moves I would have keyframed for a week.',
      'Motion design without the motion designer bill.',
    ],
    works: 'An agent skill for Claude Code & Codex · Built on Remotion',
  },
  zh: {
    motto: 'Frame motion. Craft the shot.', // Brand motto (BRAND.md)
    taglines: [
      'One prompt, one final film.',
      'Shot recipe cards: direct-to-render promos.',
      'Empower your agent to craft cinematic promo films.',
      'Every single shot tuned to perfection.',
      'Storyboarding, motion, sound design, delivery — end to end.',
      'Turn screenshots into cinematic films.',
    ],
    features: ['Shot recipe cards', 'Real page captures', '2.5D camera moves', 'Beat-synced cuts', 'Film-grade SFX', 'Motion workbench', 'Remotion render', 'JianYing export'],
    praise: [
      'Feels like a launch film from a real studio.',
      'The first agent skill that actually understands pacing.',
      'Our promo shipped the same afternoon.',
      'Camera moves I would have keyframed for a week.',
    ],
    works: 'An agent skill for Claude Code & Codex · Built on Remotion',
  },
} as const;
