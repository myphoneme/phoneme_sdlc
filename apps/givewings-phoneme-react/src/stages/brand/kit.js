// Brand Studio helpers (2026-10-13): colour maths shared by the editor and
// the live preview. The dark theme is derived exactly like the server does
// (app/brand.py dark_of) so the preview never waits for a save.
export const isHex = (v) => /^#[0-9a-fA-F]{6}$/.test(v || "");
const rgb = (h) => [0, 2, 4].map((i) => parseInt(h.replace("#", "").slice(i, i + 2), 16));
const hex = (c) => "#" + c.map((v) => Math.max(0, Math.min(255, Math.round(v))).toString(16).padStart(2, "0")).join("").toUpperCase();
export const mix = (a, b, t) => { const x = rgb(a), y = rgb(b); return hex(x.map((v, i) => v * (1 - t) + y[i] * t)); };
function lum(h) {
  return rgb(h).map((v) => v / 255).map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4))
    .reduce((s, v, i) => s + v * [0.2126, 0.7152, 0.0722][i], 0);
}
export function contrast(a, b) {
  if (!isHex(a) || !isHex(b)) return 1;
  const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p);
  return (x + 0.05) / (y + 0.05);
}
function readableOn(c, bg, target = 4.5) {
  let out = c;
  for (let i = 1; i <= 10 && contrast(out, bg) < target; i += 1) out = mix(c, "#FFFFFF", i * 0.09);
  return out;
}
export function darkOf(p) {
  const surf = isHex(p.dark_surface) ? p.dark_surface : mix("#121214", p.primary, 0.07);
  return {
    primary: isHex(p.dark_primary) ? p.dark_primary : readableOn(p.primary, surf),
    ink: isHex(p.dark_ink) ? p.dark_ink : mix("#F1F1F3", p.primary, 0.04),
    surface: surf,
    accent: isHex(p.dark_accent) ? p.dark_accent : readableOn(p.accent, surf, 3),
  };
}
export const onColour = (bg) => (contrast("#FFFFFF", bg) >= contrast("#111111", bg) ? "#FFFFFF" : "#111111");

export const RADIUS = { sharp: { card: 6, btn: 4 }, rounded: { card: 12, btn: 8 }, soft: { card: 18, btn: 999 } };

// CSS custom properties for one mode of the brand.
export function themeVars(p, mode, tokens) {
  const t = tokens || {};
  const r = RADIUS[t.radius] || RADIUS.rounded;
  const c = mode === "dark" ? darkOf(p) : { primary: p.primary, ink: p.ink, surface: p.surface, accent: p.accent };
  const bg = mode === "dark" ? c.surface : "#FFFFFF";
  const tint = mode === "dark" ? mix(c.surface, "#FFFFFF", 0.06) : c.surface;
  return {
    "--b-p": c.primary, "--b-on-p": onColour(c.primary), "--b-ink": c.ink, "--b-bg": bg, "--b-tint": tint, "--b-acc": c.accent,
    "--b-line": mode === "dark" ? "rgba(255,255,255,.12)" : mix(c.surface, c.ink, 0.12),
    "--b-mut": mode === "dark" ? mix(c.ink, c.surface, 0.35) : mix(c.ink, "#FFFFFF", 0.4),
    "--b-fh": `"${t.heading_font || "Manrope"}", system-ui, sans-serif`, "--b-fb": `"${t.body_font || "DM Sans"}", system-ui, sans-serif`,
    "--b-rc": `${r.card}px`, "--b-rb": `${r.btn}px`, "--b-gap": t.density === "compact" ? "8px" : "14px", "--b-pad": t.density === "compact" ? "10px" : "16px",
  };
}

// Load the chosen Google fonts once so the preview shows the real type.
const loaded = new Set();
export function useFonts(fonts) {
  fonts.filter(Boolean).forEach((f) => {
    if (loaded.has(f) || typeof document === "undefined") return;
    loaded.add(f);
    const l = document.createElement("link");
    l.rel = "stylesheet";
    l.href = `https://fonts.googleapis.com/css2?family=${f.replace(/ /g, "+")}:wght@400;600;700;800&display=swap`;
    document.head.appendChild(l);
  });
}
// Older stored logos can carry xmlns twice (invalid XML, so the image breaks): keep one.
const oneXmlns = (svg) => { let n = 0; return (svg || "").replace(/\sxmlns="[^"]*"/g, (m) => (n++ ? "" : m)); };
export const svgSrc = (svg) => `data:image/svg+xml;utf8,${encodeURIComponent(oneXmlns(svg))}`;
