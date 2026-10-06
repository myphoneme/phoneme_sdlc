import { useEffect, useMemo, useState } from "react";
import { ArrowDown, ArrowRight, ArrowUp, ExternalLink, Globe, Lock, LockOpen, RefreshCw, Save, Smartphone, Sparkles } from "lucide-react";
import { api } from "../api.js";

// Experience Blueprint (2026-10-07): the portal's structure and look are
// chosen here, at Identity, previewed as a clickable branded skeleton and
// frozen with the brand -- so the UI/UX stage only fills module screens in.

const SECTION_LABEL = {
  hero: "Hero (headline + call to action)", promise: "Promise strip", features: "How it works",
  download: "Download the app (QR code)", pricing: "Plans & pricing", faq: "FAQ", cta: "Closing call to action",
};
const PLATFORM = { web: "Web portal", mobile: "Mobile app", both: "Both" };
const HOME = { dashboard: "Dashboard", feed: "Feed", inbox: "Inbox / queue" };

function Seg({ value, options, onChange, disabled }) {
  return (
    <span className="seg" role="radiogroup">
      {Object.entries(options).map(([k, label]) => (
        <button key={k} type="button" role="radio" aria-checked={value === k} className={value === k ? "on" : ""} disabled={disabled} onClick={() => onChange(k)}>{label}</button>
      ))}
    </span>
  );
}

const list = (v) => v.split(",").map((x) => x.trim()).filter(Boolean);

export function BlueprintSummary({ session }) {
  const bp = session.brand?.blueprint;
  if (!bp) return null;
  return (
    <div className="bp-summary">
      <div className="bp-summary-head">
        <strong>Experience Blueprint</strong>
        {bp.frozen ? <span className="chip good"><Lock size={11} /> Frozen v{bp.version}</span> : <span className="chip warn">Draft{bp.version ? ` (after v${bp.version})` : ""}</span>}
      </div>
      <dl>
        <div><dt>Platforms</dt><dd>{PLATFORM[bp.platforms]}{bp.platforms === "both" ? ` · ${bp.primary} first` : ""}</dd></div>
        <div><dt>Public site</dt><dd>{bp.public_pages.join(" · ")}</dd></div>
        <div><dt>Landing</dt><dd>{bp.landing_sections.join(" → ")}</dd></div>
        <div><dt>Sign-in</dt><dd>{bp.auth.methods.join(", ").replaceAll("_", " ")}</dd></div>
        {bp.platforms !== "mobile" && <div><dt>Web app</dt><dd>{bp.web.nav} menu · {HOME[bp.web.home]} home</dd></div>}
        {bp.platforms !== "web" && <div><dt>Phone app</dt><dd>{bp.mobile.tabs.join(" · ")}{bp.mobile.share_target ? " · in the Share menu" : ""}</dd></div>}
        <div><dt>Look</dt><dd>{bp.tokens.heading_font} / {bp.tokens.body_font} · {bp.tokens.radius} corners · {bp.tokens.density}</dd></div>
      </dl>
    </div>
  );
}

export default function ExperienceStep({ session, setSession, next, compact = false }) {
  const sid = session.session_id;
  const saved = session.brand?.blueprint || null;
  const [cat, setCat] = useState(null);
  const [suggested, setSuggested] = useState("");
  const [bp, setBp] = useState(saved);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState(null);
  const [rev, setRev] = useState(0);
  const frozen = !!saved?.frozen;
  const dirty = useMemo(() => JSON.stringify(bp) !== JSON.stringify(saved), [bp, saved]);

  useEffect(() => {
    api.blueprintCatalogue().then(setCat).catch((e) => setError(e.message));
    api.blueprintSuggest(sid).then((r) => setSuggested(r.template_key)).catch(() => {});
  }, [sid]);
  useEffect(() => { setBp(saved); setRev((r) => r + 1); }, [saved]); // eslint-disable-line react-hooks/exhaustive-deps

  async function run(label, fn, after) {
    setBusy(label); setError(null);
    try { const s = await fn(); if (s) setSession(s); if (after) after(); }
    catch (e) { setError(e.message); }
    finally { setBusy(""); }
  }
  const set = (path, value) => setBp((x) => {
    const y = structuredClone(x);
    const keys = path.split(".");
    let o = y;
    keys.slice(0, -1).forEach((k) => { o = o[k]; });
    o[keys.at(-1)] = value;
    return y;
  });
  const toggle = (path, arr, item) => set(path, arr.includes(item) ? arr.filter((x) => x !== item) : [...arr, item]);
  const move = (i, d) => {
    const a = [...bp.landing_sections];
    const j = i + d;
    if (j < 0 || j >= a.length) return;
    [a[i], a[j]] = [a[j], a[i]];
    set("landing_sections", a);
  };
  const save = () => run("Saving blueprint…", () => api.saveBlueprint(sid, bp));
  const freeze = () => run("Freezing blueprint…", async () => {
    if (dirty) await api.saveBlueprint(sid, bp);
    return api.freezeBlueprint(sid);
  }, next);

  const templates = cat?.templates || [];
  const sections = cat?.sections || [];
  const methods = cat?.auth_methods || {};
  const fonts = cat?.fonts || [];

  return (
    <div className={"id-step bp-step" + (compact ? " compact" : "")}>
      <p className="muted">Decide how {session.selected_name || "the product"} is organised and how it looks, once, here. Pick a starting point, adjust it, click through the preview, then freeze it. The UI/UX stage designs each module's screens inside this frame.</p>

      <h4 className="mini-head">1. Starting point</h4>
      <div className="bp-templates">
        {templates.map((t) => (
          <button key={t.key} type="button" disabled={frozen || !!busy} className={"bp-template" + (bp?.template_key === t.key ? " selected" : "")}
            onClick={() => run("Applying template…", () => api.blueprintTemplate(sid, t.key))}>
            <span className="bp-template-top">
              <strong>{t.name}</strong>
              {t.key === suggested && <span className="chip accent"><Sparkles size={11} /> Fits your concept</span>}
            </span>
            <small>{t.summary}</small>
            <span className="bp-template-meta">{t.platforms === "web" ? <Globe size={13} /> : <Smartphone size={13} />} {PLATFORM[t.platforms]}{t.platforms === "both" ? ` · ${t.primary} first` : ""} · {t.fits}</span>
          </button>
        ))}
        <div className="bp-template soon" aria-disabled="true">
          <span className="bp-template-top"><strong>Reference site or your own designs</strong><span className="chip">Next release</span></span>
          <small>Paste a live site or demo URL, or upload screenshots / PDF, and GiveWings proposes the structure from it.</small>
        </div>
      </div>

      {busy && <div className="working" role="status"><span className="spinner" aria-hidden="true" /><div><strong>{busy}</strong></div></div>}
      {error && <div className="error-banner" role="alert">{error}</div>}

      {bp && (
        <div className="bp-work">
          <div className="bp-editor">
            {frozen && <p className="notice-inline"><Lock size={14} /> Frozen as v{saved.version}. Unfreeze to change it — the next freeze becomes a new version.</p>}
            <fieldset disabled={frozen || !!busy}>
              <h4 className="mini-head">2. Platforms</h4>
              <div className="bp-row"><Seg value={bp.platforms} options={PLATFORM} onChange={(v) => set("platforms", v)} />
                {bp.platforms === "both" && <Seg value={bp.primary} options={{ mobile: "Phone first", web: "Web first" }} onChange={(v) => set("primary", v)} />}</div>

              <h4 className="mini-head">3. Public website</h4>
              <div className="bp-checks">
                {(cat?.pages || []).filter((p) => p !== "Landing" && (bp.platforms !== "web" || p !== "Download app")).map((p) => (
                  <label key={p}><input type="checkbox" checked={bp.public_pages.includes(p)} onChange={() => toggle("public_pages", bp.public_pages, p)} /> {p}</label>
                ))}
              </div>
              <div className="bp-sections">
                {bp.landing_sections.map((k, i) => (
                  <div key={k} className="bp-sec">
                    <span>{i + 1}. {SECTION_LABEL[k] || k}</span>
                    <span className="bp-sec-act">
                      <button type="button" className="icon-btn" aria-label="Move up" onClick={() => move(i, -1)} disabled={i === 0}><ArrowUp size={14} /></button>
                      <button type="button" className="icon-btn" aria-label="Move down" onClick={() => move(i, 1)} disabled={i === bp.landing_sections.length - 1}><ArrowDown size={14} /></button>
                      {k !== "hero" && <button type="button" className="link-btn" onClick={() => toggle("landing_sections", bp.landing_sections, k)}>Remove</button>}
                    </span>
                  </div>
                ))}
                <div className="bp-checks">
                  {sections.filter((k) => !bp.landing_sections.includes(k) && (bp.platforms !== "web" || k !== "download")).map((k) => (
                    <button key={k} type="button" className="opt-chip sm" onClick={() => set("landing_sections", [...bp.landing_sections, k])}>+ {SECTION_LABEL[k]}</button>
                  ))}
                </div>
              </div>
              <label className="bp-field">Visitors can use without signing in
                <input value={bp.public_features} onChange={(e) => set("public_features", e.target.value)} placeholder="e.g. a free trial of one feature, a calculator, a contest" /></label>

              <h4 className="mini-head">4. Sign-in</h4>
              <div className="bp-checks">
                {Object.entries(methods).map(([k, label]) => (
                  <label key={k}><input type="checkbox" checked={bp.auth.methods.includes(k)} onChange={() => toggle("auth.methods", bp.auth.methods, k)} /> {label}</label>
                ))}
              </div>
              <label className="bp-field">Fields to create an account (comma separated)
                <input value={bp.auth.register_fields.join(", ")} onChange={(e) => set("auth.register_fields", list(e.target.value))} /></label>
              <label className="bp-field">First-run steps after sign-up (comma separated, optional)
                <input value={bp.auth.onboarding.join(", ")} onChange={(e) => set("auth.onboarding", list(e.target.value))} /></label>

              {bp.platforms !== "mobile" && <>
                <h4 className="mini-head">5. Web app</h4>
                <div className="bp-row"><Seg value={bp.web.nav} options={{ sidebar: "Sidebar menu", top: "Top menu" }} onChange={(v) => set("web.nav", v)} />
                  <Seg value={bp.web.home} options={HOME} onChange={(v) => set("web.home", v)} /></div>
              </>}
              {bp.platforms !== "web" && <>
                <h4 className="mini-head">{bp.platforms === "mobile" ? "5" : "6"}. Phone app</h4>
                <label className="bp-field">Bottom tabs (comma separated, up to 5)
                  <input value={bp.mobile.tabs.join(", ")} onChange={(e) => set("mobile.tabs", list(e.target.value))} /></label>
                <div className="bp-checks">
                  <label><input type="checkbox" checked={bp.mobile.share_target} onChange={(e) => set("mobile.share_target", e.target.checked)} /> Appears in the phone's Share menu</label>
                  <label><input type="checkbox" checked={bp.mobile.push} onChange={(e) => set("mobile.push", e.target.checked)} /> Push notifications</label>
                  <label><input type="checkbox" checked={bp.mobile.offline} onChange={(e) => set("mobile.offline", e.target.checked)} /> Works offline, syncs later</label>
                </div>
              </>}

              <h4 className="mini-head">Look</h4>
              <div className="bp-row">
                <label className="bp-field inline">Headings <select value={bp.tokens.heading_font} onChange={(e) => set("tokens.heading_font", e.target.value)}>{fonts.map((f) => <option key={f}>{f}</option>)}</select></label>
                <label className="bp-field inline">Text <select value={bp.tokens.body_font} onChange={(e) => set("tokens.body_font", e.target.value)}>{fonts.map((f) => <option key={f}>{f}</option>)}</select></label>
              </div>
              <div className="bp-row">
                <Seg value={bp.tokens.radius} options={{ sharp: "Sharp", rounded: "Rounded", soft: "Soft" }} onChange={(v) => set("tokens.radius", v)} />
                <Seg value={bp.tokens.density} options={{ comfortable: "Comfortable", compact: "Compact" }} onChange={(v) => set("tokens.density", v)} />
              </div>
              <label className="bp-field">Notes for designers (optional)
                <textarea rows={2} value={bp.notes} onChange={(e) => set("notes", e.target.value)} /></label>
            </fieldset>
          </div>

          <div className="bp-preview">
            <div className="bp-preview-head">
              <strong>Clickable preview</strong>
              <span>{dirty ? "Unsaved changes — save to refresh" : "Click buttons, menus and tabs to walk through"}</span>
              <a className="btn-secondary sm" href={api.blueprintPreviewUrl(sid)} target="_blank" rel="noreferrer"><ExternalLink size={14} /> Full screen</a>
            </div>
            <div className="bp-scaler"><iframe key={rev} title="Experience blueprint preview" src={`${api.blueprintPreviewUrl(sid)}?v=${rev}`} /></div>
          </div>
        </div>
      )}

      <div className="sticky-actions">
        {!bp && <span className="muted">Pick a starting point to see your product's structure in your brand.</span>}
        {bp && !frozen && <>
          <button className="btn-secondary" disabled={!!busy || !dirty} onClick={save}><Save size={15} /> Save &amp; refresh preview</button>
          <button className="btn-primary" disabled={!!busy} onClick={freeze}><Lock size={15} /> Freeze blueprint{next ? " & continue" : ""} <ArrowRight size={16} /></button>
        </>}
        {bp && frozen && <>
          <button className="btn-secondary" disabled={!!busy} onClick={() => run("Unfreezing…", () => api.unfreezeBlueprint(sid))}><LockOpen size={15} /> Unfreeze to change</button>
          {next && <button className="btn-primary" onClick={next}>Continue <ArrowRight size={16} /></button>}
        </>}
        {bp && !frozen && dirty && <button className="link-btn" onClick={() => setBp(saved)}><RefreshCw size={13} /> Discard edits</button>}
      </div>
    </div>
  );
}
