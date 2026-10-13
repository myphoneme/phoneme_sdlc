// Brand Studio section editors (2026-10-13). Each edits in place: palette and
// blueprint changes are drafts shown live in the preview and saved by the
// studio a moment after you stop typing.
import { useEffect, useState } from "react";
import { ArrowDown, ArrowUp, Check, Globe, PenLine, RefreshCw, Smartphone, Sparkles, Type, Wand2 } from "lucide-react";
import { api } from "../../api.js";
import { contrast, darkOf, isHex, svgSrc } from "./kit.js";

export const PRESETS = [
  { name: "GiveWings Orange", mood: "Warm, energetic", primary: "#C2410C", ink: "#171717", surface: "#FFF7F0", accent: "#0F766E", rationale: "" },
  { name: "Slate", mood: "Calm, enterprise", primary: "#334155", ink: "#0F172A", surface: "#F1F5F9", accent: "#2563EB", rationale: "" },
  { name: "Teal", mood: "Fresh, trustworthy", primary: "#0F766E", ink: "#12302D", surface: "#ECF7F5", accent: "#C2410C", rationale: "" },
];
const LANDING_LABEL = { hero: "Hero (headline + call to action)", promise: "Promise strip", features: "How it works", download: "Download the app (QR)", pricing: "Plans & pricing", faq: "FAQ", cta: "Closing call to action" };
const HOME = { dashboard: "Dashboard", feed: "Feed", inbox: "Inbox / queue" };
const list = (v) => v.split(",").map((x) => x.trim()).filter(Boolean);

// A comma-separated list that keeps what is typed (a trailing comma, a space)
// and hands the parsed list on.
function CommaInput({ value, onChange, max }) {
  const [raw, setRaw] = useState(value.join(", "));
  useEffect(() => { if (list(raw).join("|") !== value.join("|")) setRaw(value.join(", ")); }, [value.join("|")]); // eslint-disable-line react-hooks/exhaustive-deps
  return <input value={raw} onChange={(e) => { setRaw(e.target.value); onChange(list(e.target.value).slice(0, max || 99)); }} />;
}

export function Seg({ value, options, onChange, disabled }) {
  return (
    <span className="seg" role="radiogroup">
      {Object.entries(options).map(([k, label]) => (
        <button key={k} type="button" role="radio" aria-checked={value === k} className={value === k ? "on" : ""} disabled={disabled} onClick={() => onChange(k)}>{label}</button>
      ))}
    </span>
  );
}

/* ---------- 1. Name & brand ---------- */
export function NameSection({ session, run, busy, locked, onDraft }) {
  const b = session.brand || {};
  const sid = session.session_id;
  const [name, setName] = useState(session.selected_name || b.domain_checked_name || session.suggested_names?.[0] || "");
  const [tag, setTag] = useState(b.tagline || "");
  useEffect(() => { setTag(b.tagline || ""); }, [b.tagline]);
  useEffect(() => { onDraft?.({ name: name.trim(), tagline: tag.trim() }); }, [name, tag]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => () => onDraft?.(null), []); // eslint-disable-line react-hooks/exhaustive-deps
  const checked = b.domain_checked_name && b.domain_checked_name.toLowerCase() === name.trim().toLowerCase();
  const domains = checked ? b.domains || [] : [];
  const nameChanged = name.trim() && name.trim() !== session.selected_name;
  const saveTag = (v) => v.trim() && v.trim() !== b.tagline && run("Saving tagline…", () => api.chooseTagline(sid, v.trim()));
  return (
    <fieldset className="bs-fields" disabled={locked || busy}>
      <label className="bs-label">Brand name</label>
      {session.suggested_names?.length > 0 && (
        <div className="choice-row">{session.suggested_names.map((n) => <button key={n} type="button" className={"opt-chip sm" + (n === name ? " on" : "")} onClick={() => setName(n)}>{n}</button>)}</div>
      )}
      <div className="inline-field">
        <PenLine size={16} aria-hidden="true" />
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Product name" aria-label="Brand name" />
        <button type="button" className="btn-secondary sm" disabled={!name.trim()} onClick={() => run("Checking domains…", () => api.checkDomains(sid, name.trim()))}>Check domains</button>
        {nameChanged && <button type="button" className="btn-primary sm" onClick={() => run("Saving name…", () => api.chooseName(sid, name.trim()))}>Use name</button>}
      </div>
      {b.name_notes && checked && <p className="ai-note small"><span className="chip">AI opinion</span> {b.name_notes}</p>}
      {domains.length > 0 && (
        <div className="bs-domains">
          {domains.map((d) => (
            <label key={d.domain} className={`domain-row ${d.status}` + (b.chosen_domain === d.domain ? " chosen" : "")}>
              <input type="radio" name="domain" disabled={d.status !== "available"} checked={b.chosen_domain === d.domain}
                onChange={() => run("Saving domain…", async () => { if (nameChanged) await api.chooseName(sid, name.trim()); return api.chooseDomain(sid, d.domain); })} />
              <span className="domain-name">{d.domain}</span>
              <span className={`domain-badge ${d.status}`}>{d.status === "available" ? "Available" : d.status === "taken" ? "Taken" : "Unverified"}</span>
            </label>
          ))}
        </div>
      )}
      <p className="muted small">Domain: <b>{b.chosen_domain || "not chosen"}</b>. Registry status is live but not a reservation.</p>

      <label className="bs-label">Tagline</label>
      <div className="inline-field">
        <Type size={16} aria-hidden="true" />
        <input value={tag} maxLength={80} onChange={(e) => setTag(e.target.value)} onBlur={(e) => saveTag(e.target.value)} onKeyDown={(e) => e.key === "Enter" && saveTag(tag)} placeholder="Write or pick a tagline" aria-label="Tagline" />
        <button type="button" className="btn-secondary sm" disabled={!session.selected_name} onClick={() => run("Writing taglines…", () => api.genTaglines(sid))}><Sparkles size={13} /> Ideas</button>
      </div>
      {(b.tagline_options || []).length > 0 && (
        <div className="choice-row">{b.tagline_options.map((t) => <button key={t} type="button" className={"opt-chip sm" + (t === b.tagline ? " on" : "")} onClick={() => { setTag(t); saveTag(t); }}>{t}</button>)}</div>
      )}
    </fieldset>
  );
}

/* ---------- 2. Colours (light + dark) ---------- */
function ColourField({ label, value, onChange, placeholder }) {
  return (
    <label className="color-field">
      <span>{label}</span>
      <span className="color-input">
        <input type="color" value={isHex(value) ? value : (isHex(placeholder) ? placeholder : "#000000")} onChange={(e) => onChange(e.target.value.toUpperCase())} aria-label={`${label} picker`} />
        <input value={value} placeholder={placeholder} onChange={(e) => onChange(e.target.value)} aria-label={`${label} hex`} maxLength={7} />
      </span>
    </label>
  );
}

export function ColoursSection({ session, run, busy, locked, pal, setPal }) {
  const b = session.brand || {};
  const sid = session.session_id;
  useEffect(() => {
    if (!locked && !b.palette_options?.length && !busy) run("Designing colour palettes…", () => api.genPalettes(sid));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const p = pal || PRESETS[0];
  const d = darkOf(p);
  const set = (k, v) => setPal({ ...p, [k]: v, name: p.name.endsWith(" (edited)") ? p.name : `${p.name} (edited)` });
  const lightText = contrast(p.ink, p.surface), darkText = contrast(d.ink, d.surface);
  const lightBtn = Math.max(contrast("#FFFFFF", p.primary), contrast("#111111", p.primary));
  const darkBtn = Math.max(contrast("#FFFFFF", d.primary), contrast("#111111", d.primary));
  const chk = (v, min) => <span className={v >= min ? "ok" : "bad"}>{v.toFixed(1)}:1</span>;
  const options = [...(b.palette_options || []), ...PRESETS];
  return (
    <fieldset className="bs-fields" disabled={locked || busy}>
      <div className="bs-palettes">
        {options.map((o, i) => (
          <button key={o.name + i} type="button" className={"palette-card sm" + (p.name === o.name ? " selected" : "")} onClick={() => setPal(o)}>
            <span className="swatches" aria-hidden="true">{["primary", "ink", "surface", "accent"].map((k) => <i key={k} style={{ background: o[k] }} />)}</span>
            <span className="swatches dark" aria-hidden="true">{["primary", "ink", "surface", "accent"].map((k) => <i key={k} style={{ background: darkOf(o)[k] }} />)}</span>
            <strong>{o.name}</strong>{i < (b.palette_options || []).length && <span className="chip accent">AI</span>}
          </button>
        ))}
      </div>
      <button type="button" className="link-btn" onClick={() => run("Designing new palettes…", () => api.genPalettes(sid))}><RefreshCw size={12} /> New AI palettes</button>
      <div className="bs-modes">
        <div>
          <h5>Light theme</h5>
          <ColourField label="Primary" value={p.primary} onChange={(v) => set("primary", v)} />
          <ColourField label="Text" value={p.ink} onChange={(v) => set("ink", v)} />
          <ColourField label="Background tint" value={p.surface} onChange={(v) => set("surface", v)} />
          <ColourField label="Accent" value={p.accent} onChange={(v) => set("accent", v)} />
          <p className="contrast-checks">Text {chk(lightText, 4.5)} · Button {chk(lightBtn, 4.5)}</p>
        </div>
        <div>
          <h5>Dark theme <small className="muted">(empty = derived)</small></h5>
          <ColourField label="Primary" value={p.dark_primary || ""} placeholder={d.primary} onChange={(v) => set("dark_primary", v)} />
          <ColourField label="Text" value={p.dark_ink || ""} placeholder={d.ink} onChange={(v) => set("dark_ink", v)} />
          <ColourField label="Background" value={p.dark_surface || ""} placeholder={d.surface} onChange={(v) => set("dark_surface", v)} />
          <ColourField label="Accent" value={p.dark_accent || ""} placeholder={d.accent} onChange={(v) => set("dark_accent", v)} />
          <p className="contrast-checks">Text {chk(darkText, 4.5)} · Button {chk(darkBtn, 4.5)}</p>
          <button type="button" className="link-btn" onClick={() => setPal({ ...p, dark_primary: "", dark_ink: "", dark_surface: "", dark_accent: "" })}><Wand2 size={12} /> Derive dark from light</button>
        </div>
      </div>
      {p.rationale && <p className="ai-note small"><span className="chip">AI</span> {p.rationale}</p>}
    </fieldset>
  );
}

/* ---------- 3. Logo & favicon ---------- */
export function LogoSection({ session, run, busy, locked, favicon }) {
  const b = session.brand || {};
  const sid = session.session_id;
  const pal = b.palette || PRESETS[0];
  const [letter, setLetter] = useState(b.favicon_letter || "");
  return (
    <fieldset className="bs-fields" disabled={locked || busy}>
      <label className="bs-label">Logo</label>
      <div className="logo-grid sm">
        {(b.logo_options || []).map((l) => (
          <button key={l.id} type="button" className={"logo-card" + (b.logo?.id === l.id ? " selected" : "")} onClick={() => run("Saving logo…", () => api.chooseLogo(sid, l.id))}>
            <span className="logo-canvas" style={{ background: pal.surface }}><img src={svgSrc(l.svg)} alt={`Logo concept: ${l.concept || "untitled"}`} /></span>
            <small>{l.concept}</small>
            <span className="theme-check" aria-hidden="true"><Check size={14} strokeWidth={3} /></span>
          </button>
        ))}
        {b.logo && !(b.logo_options || []).some((l) => l.id === b.logo.id) && (
          <div className="logo-card selected"><span className="logo-canvas" style={{ background: pal.surface }}><img src={svgSrc(b.logo.svg)} alt="Current logo" /></span><small>Current logo</small></div>
        )}
      </div>
      <button type="button" className="btn-secondary sm" disabled={!session.selected_name || !b.palette} onClick={() => run("Drawing logo concepts…", () => api.genLogos(sid))}><RefreshCw size={13} /> {b.logo_options?.length ? "New concepts in the current colours" : "Draw logo concepts"}</button>

      <label className="bs-label">Favicon & app icon</label>
      <div className="bs-fav">
        <img src={favicon} alt="Favicon" width="56" height="56" />
        <div>
          <Seg value={b.favicon_style || "monogram"} options={{ monogram: "Monogram", logo: "From the logo" }} disabled={locked}
            onChange={(v) => run("Saving favicon…", () => api.brandOptions(sid, { favicon_style: v }))} />
          {(b.favicon_style || "monogram") === "monogram" && (
            <label className="bp-field inline">Letters <input value={letter} maxLength={2} placeholder={(session.selected_name || "?").charAt(0)} onChange={(e) => setLetter(e.target.value)}
              onBlur={() => letter !== (b.favicon_letter || "") && run("Saving favicon…", () => api.brandOptions(sid, { favicon_letter: letter }))} /></label>
          )}
          <p className="muted small">Used in browser tabs, bookmarks and as the phone app icon.</p>
        </div>
      </div>
    </fieldset>
  );
}

/* ---------- 4. Brand theme + standard modules ---------- */
export function ThemeSection({ session, run, busy, locked, bp, set, cat, suggested, placementLocked }) {
  const sid = session.session_id;
  const fonts = cat?.fonts || [];
  const methods = cat?.auth_methods || {};
  const toggle = (path, arr, item) => set(path, arr.includes(item) ? arr.filter((x) => x !== item) : [...arr, item]);
  return (
    <fieldset className="bs-fields" disabled={locked || busy}>
      <label className="bs-label">Starting point</label>
      <div className="bs-templates">
        {(cat?.templates || []).map((t) => (
          <button key={t.key} type="button" className={"bp-template sm" + (bp?.template_key === t.key ? " selected" : "")}
            onClick={() => run("Applying starting point…", () => api.blueprintTemplate(sid, t.key))}>
            <span className="bp-template-top"><strong>{t.name}</strong>{t.key === suggested && <span className="chip accent"><Sparkles size={11} /> Fits</span>}</span>
            <small>{t.summary}</small>
          </button>
        ))}
      </div>
      {bp && <>
        <label className="bs-label">Where it runs</label>
        <div className="bp-row"><Seg value={bp.platforms} options={{ web: "Web", mobile: "Phone app", both: "Both" }} onChange={(v) => set("platforms", v)} />
          {bp.platforms === "both" && <Seg value={bp.primary} options={{ mobile: "Phone first", web: "Web first" }} onChange={(v) => set("primary", v)} />}</div>
        <label className="bs-label">Type, corners and spacing</label>
        <div className="bp-row">
          <label className="bp-field inline">Headings <select value={bp.tokens.heading_font} onChange={(e) => set("tokens.heading_font", e.target.value)}>{fonts.map((f) => <option key={f}>{f}</option>)}</select></label>
          <label className="bp-field inline">Text <select value={bp.tokens.body_font} onChange={(e) => set("tokens.body_font", e.target.value)}>{fonts.map((f) => <option key={f}>{f}</option>)}</select></label>
        </div>
        <div className="bp-row">
          <Seg value={bp.tokens.radius} options={{ sharp: "Sharp", rounded: "Rounded", soft: "Soft" }} onChange={(v) => set("tokens.radius", v)} />
          <Seg value={bp.tokens.density} options={{ comfortable: "Comfortable", compact: "Compact" }} onChange={(v) => set("tokens.density", v)} />
        </div>

        <div className="bs-standard">
          <strong>Standard modules — inherited, never designed</strong>
          <p className="muted small">Sign in, create account, forgot / change password, profile & settings and admin are the same in every product. They take your colours, type and logo; only these choices are yours.</p>
          <label className="bs-label">Logo placement on these pages</label>
          <Seg value={session.brand?.logo_placement || "left"} options={{ left: "Left", center: "Centred" }} disabled={placementLocked}
            onChange={(v) => run("Saving…", () => api.brandOptions(sid, { logo_placement: v }))} />
          <label className="bs-label">Sign-in methods</label>
          <div className="bp-checks">{Object.entries(methods).map(([k, label]) => <label key={k}><input type="checkbox" checked={bp.auth.methods.includes(k)} onChange={() => toggle("auth.methods", bp.auth.methods, k)} /> {label}</label>)}</div>
          <label className="bp-field">Fields to create an account <CommaInput value={bp.auth.register_fields} onChange={(v) => set("auth.register_fields", v)} /></label>
          <label className="bp-field">First-run steps after sign-up (optional) <CommaInput value={bp.auth.onboarding} onChange={(v) => set("auth.onboarding", v)} /></label>
        </div>
      </>}
    </fieldset>
  );
}

/* ---------- 5. Marketing landing page ---------- */
export function LandingSection({ busy, locked, bp, set, cat }) {
  if (!bp) return <p className="muted">Choose a starting point in Brand theme first.</p>;
  const sections = cat?.sections || [];
  const toggle = (path, arr, item) => set(path, arr.includes(item) ? arr.filter((x) => x !== item) : [...arr, item]);
  const move = (i, dd) => { const a = [...bp.landing_sections]; const j = i + dd; if (j < 0 || j >= a.length) return; [a[i], a[j]] = [a[j], a[i]]; set("landing_sections", a); };
  return (
    <fieldset className="bs-fields" disabled={locked || busy}>
      <label className="bs-label">Sections, top to bottom</label>
      <div className="bp-sections">
        {bp.landing_sections.map((k, i) => (
          <div key={k} className="bp-sec">
            <span>{i + 1}. {LANDING_LABEL[k] || k}</span>
            <span className="bp-sec-act">
              <button type="button" className="icon-btn" aria-label="Move up" onClick={() => move(i, -1)} disabled={i === 0}><ArrowUp size={14} /></button>
              <button type="button" className="icon-btn" aria-label="Move down" onClick={() => move(i, 1)} disabled={i === bp.landing_sections.length - 1}><ArrowDown size={14} /></button>
              {k !== "hero" && <button type="button" className="link-btn" onClick={() => toggle("landing_sections", bp.landing_sections, k)}>Remove</button>}
            </span>
          </div>
        ))}
        <div className="bp-checks">{sections.filter((k) => !bp.landing_sections.includes(k) && (bp.platforms !== "web" || k !== "download")).map((k) => (
          <button key={k} type="button" className="opt-chip sm" onClick={() => set("landing_sections", [...bp.landing_sections, k])}>+ {LANDING_LABEL[k]}</button>))}</div>
      </div>
      <label className="bs-label">Other public pages</label>
      <div className="bp-checks">{(cat?.pages || []).filter((p) => p !== "Landing" && (bp.platforms !== "web" || p !== "Download app")).map((p) => (
        <label key={p}><input type="checkbox" checked={bp.public_pages.includes(p)} onChange={() => toggle("public_pages", bp.public_pages, p)} /> {p}</label>))}</div>
      <label className="bp-field">Visitors can use without signing in <input value={bp.public_features} onChange={(e) => set("public_features", e.target.value)} placeholder="e.g. a free trial of one feature, a calculator" /></label>
    </fieldset>
  );
}

/* ---------- 6. Web pages theme ---------- */
export function WebSection({ busy, locked, bp, set }) {
  if (!bp) return <p className="muted">Choose a starting point in Brand theme first.</p>;
  if (bp.platforms === "mobile") return <p className="muted"><Globe size={14} /> This product is phone-only. Switch “Where it runs” in Brand theme to add a web app.</p>;
  return (
    <fieldset className="bs-fields" disabled={locked || busy}>
      <label className="bs-label">Menu</label>
      <Seg value={bp.web.nav} options={{ sidebar: "Sidebar", top: "Top bar" }} onChange={(v) => set("web.nav", v)} />
      <label className="bs-label">Home page</label>
      <Seg value={bp.web.home} options={HOME} onChange={(v) => set("web.home", v)} />
      <p className="muted small">The catalogue on the right — list, detail, form, empty state, settings — is how every module page is drawn at UI/UX. Module screens are designed into these, not from scratch.</p>
      <label className="bp-field">Notes for designers (optional) <textarea rows={2} value={bp.notes} onChange={(e) => set("notes", e.target.value)} /></label>
    </fieldset>
  );
}

/* ---------- 7. Mobile pages theme ---------- */
export function MobileSection({ busy, locked, bp, set }) {
  if (!bp) return <p className="muted">Choose a starting point in Brand theme first.</p>;
  if (bp.platforms === "web") return <p className="muted"><Smartphone size={14} /> This product is web-only. Switch “Where it runs” in Brand theme to add a phone app.</p>;
  return (
    <fieldset className="bs-fields" disabled={locked || busy}>
      <label className="bp-field">Bottom tabs (comma separated, up to 5) <CommaInput value={bp.mobile.tabs} max={5} onChange={(v) => set("mobile.tabs", v)} /></label>
      <div className="bp-checks">
        <label><input type="checkbox" checked={bp.mobile.share_target} onChange={(e) => set("mobile.share_target", e.target.checked)} /> Appears in the phone's Share menu</label>
        <label><input type="checkbox" checked={bp.mobile.push} onChange={(e) => set("mobile.push", e.target.checked)} /> Push notifications</label>
        <label><input type="checkbox" checked={bp.mobile.offline} onChange={(e) => set("mobile.offline", e.target.checked)} /> Works offline, syncs later</label>
      </div>
    </fieldset>
  );
}
