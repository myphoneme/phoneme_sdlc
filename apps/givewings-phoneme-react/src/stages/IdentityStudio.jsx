import { useEffect, useState } from "react";
import { ArrowRight, Check, CircleHelp, Globe, Palette as PaletteIcon, PenLine, RefreshCw, Shapes, Type } from "lucide-react";
import { api } from "../api.js";

const STEPS = [
  { key: "name", label: "Name & domain", icon: Globe },
  { key: "tagline", label: "Tagline", icon: Type },
  { key: "colors", label: "Colour theme", icon: PaletteIcon },
  { key: "logo", label: "Logo", icon: Shapes },
  { key: "review", label: "Review", icon: Check },
];

const PRESETS = [
  { name: "GiveWings Orange", mood: "Warm, energetic", primary: "#C2410C", ink: "#171717", surface: "#FFF7F0", accent: "#0F766E", rationale: "" },
  { name: "Slate", mood: "Calm, enterprise", primary: "#334155", ink: "#0F172A", surface: "#F1F5F9", accent: "#2563EB", rationale: "" },
  { name: "Teal", mood: "Fresh, trustworthy", primary: "#0F766E", ink: "#12302D", surface: "#ECF7F5", accent: "#C2410C", rationale: "" },
];

// WCAG relative-luminance contrast.
function lum(hex) {
  const n = (hex || "#000000").replace("#", "");
  const c = [0, 2, 4].map((i) => parseInt(n.slice(i, i + 2), 16) / 255).map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
}
export function contrast(a, b) {
  const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p);
  return (x + 0.05) / (y + 0.05);
}
const svgSrc = (svg) => `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
const isHex = (v) => /^#[0-9a-fA-F]{6}$/.test(v);

function firstOpenStep(s) {
  const b = s.brand || {};
  if (!s.selected_name || !b.domain_checked_name) return 0;
  if (!b.tagline) return 1;
  if (!b.palette) return 2;
  if (!b.logo) return 3;
  return 4;
}

function Busy({ text }) {
  return <div className="working" role="status"><span className="spinner" aria-hidden="true" /><div><strong>{text}</strong><p>GiveWings AI is working on it — usually 10–30 seconds.</p></div></div>;
}

/* ---------------- Step 1: name + domains ---------------- */
function NameStep({ session, setSession, run, busy, next }) {
  const b = session.brand || {};
  const [name, setName] = useState(session.selected_name || b.domain_checked_name || session.suggested_names?.[0] || "");
  const [domain, setDomain] = useState(b.chosen_domain || "");
  const checked = b.domain_checked_name && b.domain_checked_name.toLowerCase() === name.trim().toLowerCase();
  const domains = checked ? b.domains || [] : [];
  const exact = domains.slice(0, 6);
  const variants = domains.slice(6);
  const available = domains.filter((d) => d.status === "available");

  const check = () => run("Checking the registries…", () => api.checkDomains(session.session_id, name.trim()));
  const useName = () =>
    run("Saving…", async () => {
      let s = await api.chooseName(session.session_id, name.trim());
      s = await api.chooseDomain(session.session_id, domain);
      return s;
    }, next);

  const Row = ({ d }) => (
    <label className={`domain-row ${d.status}`}>
      <input type="radio" name="domain" disabled={d.status !== "available"} checked={domain === d.domain} onChange={() => setDomain(d.domain)} />
      <span className="domain-name">{d.domain}</span>
      <span className={`domain-badge ${d.status}`}>
        {d.status === "available" ? "Available" : d.status === "taken" ? "Taken" : "Couldn't verify"}
      </span>
    </label>
  );

  return (
    <div className="id-step">
      {session.suggested_names?.length > 0 && (
        <div className="choice-row">
          <span className="muted">From research:</span>
          {session.suggested_names.map((n) => (
            <button key={n} className={"opt-chip" + (n === name ? " on" : "")} onClick={() => setName(n)}>{n}</button>
          ))}
        </div>
      )}
      <div className="inline-field">
        <PenLine size={17} aria-hidden="true" />
        <input value={name} onChange={(e) => setName(e.target.value)} onKeyDown={(e) => e.key === "Enter" && name.trim() && check()} placeholder="Product name" aria-label="Product name" />
        <button className="btn-secondary" disabled={busy || !name.trim()} onClick={check}>Check name &amp; domains</button>
      </div>

      {checked && (
        <>
          {b.name_notes && <p className="ai-note"><span className="chip">AI opinion</span> {b.name_notes}</p>}
          <div className="domain-summary">
            <strong>{available.length}</strong> of {domains.length} domains available · live registry lookup
          </div>
          <div className="domain-grid">
            <div>
              <h4 className="mini-head">Exact name</h4>
              {exact.map((d) => <Row key={d.domain} d={d} />)}
            </div>
            <div>
              <h4 className="mini-head">Variations (.com)</h4>
              {variants.map((d) => <Row key={d.domain} d={d} />)}
            </div>
          </div>
          <p className="muted small">Registry status is live but not a reservation — register your chosen domain soon. "Couldn't verify" means the registry didn't answer; check it manually. Trademark checks are not included.</p>
        </>
      )}

      <div className="sticky-actions">
        <span className="muted">{!checked ? "Check the name to see domain availability." : domain ? <>Using <strong>{name}</strong> with <strong>{domain}</strong></> : "Pick an available domain, or continue without one."}</span>
        <button className="btn-primary" disabled={busy || !checked} onClick={useName}>Use this name <ArrowRight size={16} /></button>
      </div>
    </div>
  );
}

/* ---------------- Step 2: tagline ---------------- */
function TaglineStep({ session, run, busy, next }) {
  const b = session.brand || {};
  const [value, setValue] = useState(b.tagline || "");
  useEffect(() => {
    if (!b.tagline_options?.length && !busy) run("Writing tagline options…", () => api.genTaglines(session.session_id));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return (
    <div className="id-step">
      <div className="option-list">
        {(b.tagline_options || []).map((t) => (
          <label key={t} className={"option-card" + (value === t ? " selected" : "")}>
            <input type="radio" name="tagline" checked={value === t} onChange={() => setValue(t)} />
            <span className="tagline-text">{t}</span>
          </label>
        ))}
      </div>
      <div className="inline-field">
        <Type size={17} aria-hidden="true" />
        <input value={value} onChange={(e) => setValue(e.target.value)} placeholder="Or write / edit your own tagline" aria-label="Tagline" maxLength={80} />
        <button className="btn-secondary" disabled={busy} onClick={() => run("Writing new options…", () => api.genTaglines(session.session_id))}><RefreshCw size={15} /> New options</button>
      </div>
      <div className="sticky-actions">
        <span className="muted">{value ? <>“{value}”</> : "Pick or write a tagline."}</span>
        <button className="btn-primary" disabled={busy || !value.trim()} onClick={() => run("Saving…", () => api.chooseTagline(session.session_id, value.trim()), next)}>Use tagline <ArrowRight size={16} /></button>
      </div>
    </div>
  );
}

/* ---------------- Step 3: colour theme ---------------- */
function ThemePreview({ p, name, tagline }) {
  return (
    <div className="theme-live" style={{ background: p.surface, color: p.ink }}>
      <div className="theme-live-bar" style={{ background: p.ink }}>
        <span style={{ color: p.surface }}>{name}</span>
        <i style={{ background: p.primary }} />
      </div>
      <div className="theme-live-body">
        <strong style={{ color: p.ink }}>{tagline || "Your tagline here"}</strong>
        <p style={{ color: p.ink, opacity: 0.8 }}>This is how body text reads on your background.</p>
        <div className="theme-live-actions">
          <span className="theme-live-btn" style={{ background: p.primary, color: contrast("#FFFFFF", p.primary) >= contrast(p.ink, p.primary) ? "#FFFFFF" : p.ink }}>Primary button</span>
          <span className="theme-live-chip" style={{ borderColor: p.accent, color: p.accent }}>Accent</span>
        </div>
      </div>
    </div>
  );
}

function ColorsStep({ session, run, busy, next }) {
  const b = session.brand || {};
  const [p, setP] = useState(b.palette || b.palette_options?.[0] || PRESETS[0]);
  useEffect(() => {
    if (!b.palette_options?.length && !busy) run("Designing colour palettes…", () => api.genPalettes(session.session_id));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => {
    if (!b.palette && b.palette_options?.length) setP(b.palette_options[0]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [b.palette_options?.length]);

  const set = (k, v) => setP((x) => ({ ...x, [k]: v, name: x.name.endsWith(" (edited)") ? x.name : `${x.name} (edited)` }));
  const textC = contrast(p.ink, p.surface);
  const btnC = Math.max(contrast("#FFFFFF", p.primary), contrast(p.ink, p.primary));
  const valid = ["primary", "ink", "surface", "accent"].every((k) => isHex(p[k]));
  const options = [...(b.palette_options || []), ...PRESETS];

  return (
    <div className="id-step">
      <div className="palette-grid">
        {options.map((o, i) => (
          <button key={o.name + i} className={"palette-card" + (p.name === o.name ? " selected" : "")} onClick={() => setP(o)}>
            <span className="swatches" aria-hidden="true">{["primary", "ink", "surface", "accent"].map((k) => <i key={k} style={{ background: o[k] }} />)}</span>
            <strong>{o.name}</strong>
            <small>{o.mood || (i >= (b.palette_options || []).length ? "Preset" : "")}</small>
            {i < (b.palette_options || []).length && <span className="chip accent">AI</span>}
          </button>
        ))}
      </div>

      <div className="theme-builder">
        <div className="color-fields">
          {[["primary", "Primary (brand)"], ["ink", "Ink (text)"], ["surface", "Surface (background)"], ["accent", "Accent"]].map(([k, label]) => (
            <label key={k} className="color-field">
              <span>{label}</span>
              <span className="color-input">
                <input type="color" value={isHex(p[k]) ? p[k] : "#000000"} onChange={(e) => set(k, e.target.value.toUpperCase())} aria-label={`${label} colour picker`} />
                <input value={p[k]} onChange={(e) => set(k, e.target.value)} aria-label={`${label} hex`} maxLength={7} />
              </span>
            </label>
          ))}
          <div className="contrast-checks">
            <span className={textC >= 4.5 ? "ok" : "bad"}>Text on background {textC.toFixed(1)}:1 {textC >= 7 ? "· AAA" : textC >= 4.5 ? "· AA" : "· too low"}</span>
            <span className={btnC >= 4.5 ? "ok" : "bad"}>Button label {btnC.toFixed(1)}:1 {btnC >= 4.5 ? "· AA" : "· too low"}</span>
          </div>
          {p.rationale && <p className="ai-note small"><span className="chip">AI</span> {p.rationale}</p>}
        </div>
        <ThemePreview p={p} name={session.selected_name} tagline={b.tagline} />
      </div>

      <div className="sticky-actions">
        <button className="btn-secondary" disabled={busy} onClick={() => run("Designing new palettes…", () => api.genPalettes(session.session_id))}><RefreshCw size={15} /> New AI palettes</button>
        <button className="btn-primary" disabled={busy || !valid || textC < 4.5} onClick={() => run("Saving…", () => api.choosePalette(session.session_id, p), next)}>Use this theme <ArrowRight size={16} /></button>
      </div>
    </div>
  );
}

/* ---------------- Step 4: logo ---------------- */
function LogoStep({ session, run, busy, next }) {
  const b = session.brand || {};
  const [sel, setSel] = useState(b.logo?.id || "");
  useEffect(() => {
    if (!b.logo_options?.length && !busy) run("Drawing logo concepts…", () => api.genLogos(session.session_id));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const pal = b.palette || PRESETS[0];
  return (
    <div className="id-step">
      <div className="logo-grid">
        {(b.logo_options || []).map((l) => (
          <button key={l.id} className={"logo-card" + (sel === l.id ? " selected" : "")} onClick={() => setSel(l.id)}>
            <span className="logo-canvas" style={{ background: pal.surface }}><img src={svgSrc(l.svg)} alt={`Logo concept: ${l.concept || "untitled"}`} /></span>
            <small>{l.concept}</small>
            <span className="theme-check" aria-hidden="true"><Check size={14} strokeWidth={3} /></span>
          </button>
        ))}
      </div>
      <p className="muted small">Concepts are vector (SVG) starting points drawn by GiveWings AI in your theme — a designer can refine the chosen one.</p>
      <div className="sticky-actions">
        <button className="btn-secondary" disabled={busy} onClick={() => run("Drawing new concepts…", () => api.genLogos(session.session_id))}><RefreshCw size={15} /> New concepts</button>
        <button className="btn-primary" disabled={busy || !sel} onClick={() => run("Saving…", () => api.chooseLogo(session.session_id, sel), next)}>Use this logo <ArrowRight size={16} /></button>
      </div>
    </div>
  );
}

/* ---------------- Step 5: review ---------------- */
export function IdentitySummary({ session }) {
  const b = session.brand || {};
  const p = b.palette;
  return (
    <div className="identity-summary" style={p ? { background: p.surface, color: p.ink } : undefined}>
      {b.logo ? <img className="identity-logo" src={svgSrc(b.logo.svg)} alt={`${session.selected_name} logo`} /> : <span className="ws-mark">{(session.selected_name || "?").charAt(0)}</span>}
      <dl>
        <div><dt>Name</dt><dd>{session.selected_name || "—"}</dd></div>
        <div><dt>Tagline</dt><dd>{b.tagline || "—"}</dd></div>
        <div><dt>Domain</dt><dd>{b.chosen_domain || "Not chosen"}</dd></div>
        <div><dt>Colour theme</dt><dd>{p ? <span className="swatches inline">{["primary", "ink", "surface", "accent"].map((k) => <i key={k} title={`${k} ${p[k]}`} style={{ background: p[k] }} />)} {p.name}</span> : session.selected_theme || "—"}</dd></div>
      </dl>
    </div>
  );
}

function ReviewStep({ session, run, busy }) {
  return (
    <div className="id-step">
      <IdentitySummary session={session} />
      <div className="sticky-actions">
        <span className="muted">Next, GiveWings AI breaks {session.selected_name} into modules for you to review.</span>
        <button className="btn-primary" disabled={busy} onClick={() => run("Locking identity…", () => api.completeIdentity(session.session_id))}>Confirm identity &amp; continue <ArrowRight size={16} /></button>
      </div>
    </div>
  );
}

export default function IdentityStudio({ session, setSession }) {
  const [step, setStep] = useState(() => firstOpenStep(session));
  const [busy, setBusy] = useState("");
  const [error, setError] = useState(null);
  const reached = firstOpenStep(session);

  async function run(label, fn, after) {
    setBusy(label);
    setError(null);
    try {
      const s = await fn();
      if (s) setSession(s);
      if (after) after();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy("");
    }
  }
  const next = () => setStep((i) => Math.min(i + 1, STEPS.length - 1));
  const props = { session, setSession, run, busy: !!busy, next };

  return (
    <div className="identity-studio">
      <ol className="substeps" aria-label="Identity steps">
        {STEPS.map((s, i) => {
          const Icon = s.icon;
          const state = i < reached ? "done" : i === reached ? "current" : "todo";
          return (
            <li key={s.key}>
              <button type="button" className={`substep ${state}${i === step ? " active" : ""}`} disabled={i > reached} onClick={() => setStep(i)} aria-current={i === step ? "step" : undefined}>
                <span className="substep-icon">{state === "done" ? <Check size={13} strokeWidth={3} /> : <Icon size={14} />}</span>
                {s.label}
              </button>
            </li>
          );
        })}
      </ol>

      {busy && <Busy text={busy} />}
      {error && <div className="error-banner" role="alert"><CircleHelp size={15} /> {error}</div>}

      {step === 0 && <NameStep {...props} />}
      {step === 1 && <TaglineStep {...props} />}
      {step === 2 && <ColorsStep {...props} />}
      {step === 3 && <LogoStep {...props} />}
      {step === 4 && <ReviewStep {...props} />}
    </div>
  );
}
