import { Box } from "@mantine/core";
import type { CSSProperties } from "react";

/** SPEX brand (Brand book v1.0): navy leads, the four beam colours identify. */
export const APP_NAME = "SPEX School Manager";
export const TAGLINE = "Secure. Intelligent. Powered.";
export const BRAND = {
  navy: "#0B1F3A",
  cloud: "#F4F6F9",
  graphite: "#16191F",
  steel: "#5B6B7F",
  blue: "#1E88E5",
  violet: "#7C4DFF",
  amber: "#F5A623",
  teal: "#12B5C9",
} as const;

/** Short 45° beams, tone-on-tone on navy. Background only, never behind small text. */
export const BEAM_TEXTURE = `url("data:image/svg+xml,${encodeURIComponent(
  '<svg xmlns="http://www.w3.org/2000/svg" width="44" height="44"><path d="M6 6l9 9M28 28l9 9" stroke="#16325a" stroke-width="5" stroke-linecap="butt"/></svg>',
)}")`;

/** The master logo artwork (taken from the brand kit, never retyped).
 *  "navy" goes on white or Cloud; "white" on navy or dark photos. */
export function SpexLogo({ height = 32, variant = "navy", style }: { height?: number; variant?: "navy" | "white"; style?: CSSProperties }) {
  return (
    <img
      src={`/brand/spex-logo-${variant}.png`}
      alt="SPEX"
      height={height}
      width={Math.round((height * 840) / 218)}
      style={{ display: "block", flexShrink: 0, ...style }}
    />
  );
}

/** The X symbol: four division beams meeting at the lens. On a navy tile for app icons
 *  and avatars; below 24 px the lens ring is dropped, as the brand book asks. */
export function SpexSymbol({ size = 32, tile = true }: { size?: number; tile?: boolean }) {
  const ring = size >= 24;
  const lens = tile ? ["#FFFFFF", BRAND.navy, "#FFFFFF"] : [BRAND.navy, "#FFFFFF", BRAND.navy];
  return (
    <svg width={size} height={size} viewBox={tile ? "0 0 64 64" : "12 12 40 40"} role="img" aria-label="SPEX" style={{ display: "block", flexShrink: 0 }}>
      {tile && <rect width="64" height="64" rx="10.5" fill={BRAND.navy} />}
      <g strokeWidth={7.5}>
        <line x1="32" y1="32" x2="15.25" y2="15.25" stroke={BRAND.blue} />
        <line x1="32" y1="32" x2="48.75" y2="15.25" stroke={BRAND.violet} />
        <line x1="32" y1="32" x2="15.25" y2="48.75" stroke={BRAND.amber} />
        <line x1="32" y1="32" x2="48.75" y2="48.75" stroke={BRAND.teal} />
      </g>
      {ring && (
        <>
          <circle cx="32" cy="32" r="7.1" fill={lens[0]} />
          <circle cx="32" cy="32" r="4.6" fill={lens[1]} />
          <circle cx="32" cy="32" r="1.7" fill={lens[2]} />
        </>
      )}
    </svg>
  );
}

/** The four-colour stripe that closes every page, card and banner, always in beam order. */
export function BrandStripe({ height = 4, style }: { height?: number; style?: CSSProperties }) {
  return (
    <Box
      aria-hidden
      style={{
        height,
        flexShrink: 0,
        background: `linear-gradient(90deg, ${BRAND.blue} 0 25%, ${BRAND.violet} 25% 50%, ${BRAND.amber} 50% 75%, ${BRAND.teal} 75% 100%)`,
        ...style,
      }}
    />
  );
}
