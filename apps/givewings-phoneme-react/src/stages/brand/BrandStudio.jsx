// Brand Studio (2026-10-13) — the Identity stage, rebuilt. Seven sections in
// one place, each editable on the fly with a live light/dark, web/phone
// preview. Rules: while Identity is open, sections change freely and can be
// frozen one by one (no version). "Freeze Identity" freezes all as v1.0.
// After that every change is a change request: pick the sections, see the
// impact, edit, then approve as the next version (UI/UX and UX flow must then
// be re-approved).
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle, ArrowRight, Check, CircleDashed, ExternalLink, GitPullRequest, Globe, ImageUp, LayoutTemplate, Lock, LockOpen,
  Moon, Palette as PaletteIcon, Shapes, ShieldCheck, Smartphone, Sun, Type, Undo2, X,
} from "lucide-react";
import { api, fileUrl } from "../../api.js";
import DesignImport from "../DesignImport.jsx";
import BrandPreview from "./BrandPreview.jsx";
import { ColoursSection, LandingSection, LogoSection, MobileSection, NameSection, PRESETS, ThemeSection, WebSection } from "./sections.jsx";
import "./brand.css";

const META = {
  name: { icon: Type, hint: "Brand name, domain and tagline." },
  colours: { icon: PaletteIcon, hint: "One palette, in a light and a dark theme." },
  logo: { icon: Shapes, hint: "Logo, favicon and app icon." },
  theme: { icon: LayoutTemplate, hint: "Type, corners, spacing — and what the standard modules inherit." },
  landing: { icon: Globe, hint: "The public marketing page visitors land on." },
  web: { icon: Globe, hint: "The web app frame and the page catalogue every module uses." },
  mobile: { icon: Smartphone, hint: "Phone tabs, page types and the share sheet." },
};
const BP_SECTIONS = { theme: 1, landing: 1, web: 1, mobile: 1 };

// A draft that is saved a moment after the owner stops editing.
function useAutosave(saved, save, onError, delay = 700) {
  const [draft, setDraft] = useState(saved);
  const dirty = useRef(false);
  const timer = useRef(null);
  const savedJson = JSON.stringify(saved);
  useEffect(() => { if (!dirty.current) setDraft(saved); }, [savedJson]); // eslint-disable-line react-hooks/exhaustive-deps
  const update = useCallback((next) => {
    dirty.current = true;
    setDraft(next);
    clearTimeout(timer.current);
    timer.current = setTimeout(async () => {
      try { await save(next); } catch (e) { onError(e); dirty.current = false; setDraft(saved); return; }
      dirty.current = false;
    }, delay);
  }, [save, onError, delay, saved]);
  useEffect(() => () => clearTimeout(timer.current), []);
  return [draft, update, () => dirty.current];
}

function ChangeDialog({ status, onClose, onOpen }) {
  const [keys, setKeys] = useState([]);
  const [reason, setReason] = useState("");
  const toggle = (k) => setKeys((s) => (s.includes(k) ? s.filter((x) => x !== k) : [...s, k]));
  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="cr-title">
      <div className="modal bs-modal">
        <button type="button" className="modal-close" onClick={onClose} aria-label="Close"><X size={15} /></button>
        <h2 id="cr-title">Request a change to Identity v{status.version}</h2>
        <p className="modal-lead">Choose what to change. Only these sections reopen; approving the change freezes Identity as v{nextVersion(status.version)}.</p>
        <div className="bs-cr-list">
          {status.sections.filter((s) => s.status !== "na").map((s) => (
            <label key={s.key}><input type="checkbox" checked={keys.includes(s.key)} onChange={() => toggle(s.key)} /> {s.label}</label>
          ))}
        </div>
        <label>Why (kept in the version history)<textarea rows={2} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. warmer colours for the launch" /></label>
        <div className="bs-impacts"><strong><AlertTriangle size={13} /> Impact</strong><ul>{status.impacts.map((x) => <li key={x}>{x}</li>)}</ul></div>
        <div className="modal-actions">
          <button type="button" className="btn-secondary" onClick={onClose}>Cancel</button>
          <button type="button" className="btn-primary" disabled={!keys.length} onClick={() => onOpen(keys, reason)}><GitPullRequest size={14} /> Open change request</button>
        </div>
      </div>
    </div>
  );
}
const nextVersion = (v) => { const [a, b] = (v || "1.0").split("."); return `${a}.${Number(b || 0) + 1}`; };

export default function BrandStudio({ session, setSession }) {
  const sid = session.session_id;
  const b = session.brand || {};
  const [active, setActive] = useState(() => (b.blueprint?.designs?.length ? "name" : "name"));
  const [status, setStatus] = useState(null);
  const [cat, setCat] = useState(null);
  const [suggested, setSuggested] = useState("");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState(null);
  const [mode, setMode] = useState("light");
  const [device, setDevice] = useState("web");
  const [askChange, setAskChange] = useState(false);
  const pvRef = useRef(null);
  useEffect(() => { if (pvRef.current) pvRef.current.scrollTop = 0; }, [active]);
  const [nameDraft, setNameDraft] = useState(null); // typed but not yet saved: shown live in the preview

  const sig = JSON.stringify([b.sections, b.change?.sections, b.version, b.completed, b.palette, b.logo?.id, b.tagline, session.selected_name,
    b.blueprint && JSON.stringify(b.blueprint).length, (session.baselines || []).length]);
  useEffect(() => { api.brandStatus(sid).then(setStatus).catch((e) => setError(e.message)); }, [sid, sig]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    api.blueprintCatalogue().then(setCat).catch(() => {});
    api.blueprintSuggest(sid).then((r) => setSuggested(r.template_key)).catch(() => {});
  }, [sid]);

  const run = useCallback(async (label, fn) => {
    setBusy(label); setError(null);
    try { const s = await fn(); if (s) setSession(s); } catch (e) { setError(e.message); } finally { setBusy(""); }
  }, [setSession]);
  const onError = useCallback((e) => setError(e.message), []);

  const savePal = useCallback(async (p) => setSession(await api.choosePalette(sid, p)), [sid, setSession]);
  const [pal, setPal] = useAutosave(b.palette || b.palette_options?.[0] || PRESETS[0], savePal, onError);
  const saveBp = useCallback(async (x) => setSession(await api.saveBlueprint(sid, x)), [sid, setSession]);
  const [bp, setBpDraft] = useAutosave(b.blueprint || null, saveBp, onError);
  const setBp = (path, value) => {
    const y = structuredClone(bp);
    const keys = path.split(".");
    let o = y;
    keys.slice(0, -1).forEach((k) => { o = o[k]; });
    o[keys.at(-1)] = value;
    setBpDraft(y);
  };

  const sections = status?.sections || [];
  const sec = sections.find((s) => s.key === active);
  const identityFrozen = !!status?.frozen;
  const change = b.change;
  const lockedReason = (key) => {
    if (!status) return "";
    const s = sections.find((x) => x.key === key);
    if (identityFrozen) return `Identity is frozen as v${status.version}. Request a change to edit this section.`;
    if (change && !change.sections.includes(key)) return "Not part of the open change request.";
    if (s?.status === "frozen") return "This section is frozen.";
    return "";
  };
  const locked = (key) => !!lockedReason(key);
  const favV = JSON.stringify([b.favicon_style, b.favicon_letter, b.palette?.primary, b.logo?.id, session.selected_name, bp?.tokens?.heading_font]);
  const favicon = api.faviconUrl(sid, favV);
  const ready = sections.filter((s) => s.status !== "na").every((s) => s.status === "ready" || s.status === "frozen");
  const done = sections.filter((s) => s.status === "frozen").length;
  const applicable = sections.filter((s) => s.status !== "na").length;
  const order = ["designs", ...sections.map((s) => s.key), "standard"];
  const nextKey = order[order.indexOf(active) + 1];

  const freezeSection = (key, action) => run(action === "freeze" ? "Freezing section…" : "Unfreezing…", async () => {
    if (key === "colours") await api.choosePalette(sid, pal);
    if (BP_SECTIONS[key] && bp) await api.saveBlueprint(sid, bp);
    return api.brandSection(sid, key, action);
  });
  const freezeIdentity = () => run(change ? "Approving the change…" : "Freezing Identity…", async () => {
    if (!locked("colours") && pal) await api.choosePalette(sid, pal);
    return api.completeIdentity(sid);
  });

  const editor = useMemo(() => {
    const common = { session, run, busy: !!busy };
    switch (active) {
      case "designs": return <DesignImport session={session} setSession={setSession} frozen={["landing", "web", "mobile"].some((k) => locked(k) && sections.find((s) => s.key === k)?.status !== "na")} />;
      case "name": return <NameSection {...common} locked={locked("name")} onDraft={setNameDraft} />;
      case "colours": return <ColoursSection {...common} locked={locked("colours")} pal={pal} setPal={setPal} />;
      case "logo": return <LogoSection {...common} locked={locked("logo")} favicon={favicon} />;
      case "theme": return <ThemeSection {...common} locked={locked("theme")} bp={bp} set={setBp} cat={cat} suggested={suggested} placementLocked={locked("theme")} />;
      case "landing": return <LandingSection {...common} locked={locked("landing")} bp={bp} set={setBp} cat={cat} />;
      case "web": return <WebSection {...common} locked={locked("web")} bp={bp} set={setBp} />;
      case "mobile": return <MobileSection {...common} locked={locked("mobile")} bp={bp} set={setBp} />;
      case "standard": return (
        <div className="bs-fields">
          <p>These modules ship with every product and are <b>never designed per product</b>. They inherit your colours (light and dark), type, corners and logo — nothing else to decide here.</p>
          <ul className="bs-std-list">{(status?.standard_pages || []).map((p) => <li key={p}><ShieldCheck size={13} /> {p}</li>)}</ul>
          <p className="muted small">Logo placement and sign-in methods are set in <button type="button" className="link-btn" onClick={() => setActive("theme")}>Brand theme</button>.</p>
        </div>
      );
      default: return null;
    }
  }, [active, session, busy, pal, bp, cat, suggested, status, favicon]); // eslint-disable-line react-hooks/exhaustive-deps

  const title = active === "designs" ? "Your own designs (optional)" : active === "standard" ? "Standard modules — inherited" : sec?.label;
  const hint = active === "designs" ? "Upload every web and phone design at once; GiveWings sorts them into the sections below." : active === "standard" ? "Same in every product; only the theme and logo placement carry over." : META[active]?.hint;
  const lr = META[active] ? lockedReason(active) : "";

  return (
    <div className="bs">
      <header className="bs-head">
        <div className="bs-id">
          <span className="bs-fav"><img src={favicon} alt="" width="34" height="34" /></span>
          <div>
            <strong>{session.selected_name || "New product"}</strong>
            <small>{b.tagline || "No tagline yet"}</small>
          </div>
        </div>
        <div className="bs-state">
          {change ? <span className="chip warn"><GitPullRequest size={12} /> Change request open · v{status?.version} → v{nextVersion(status?.version)}</span>
            : identityFrozen ? <span className="chip good"><Lock size={12} /> Identity frozen · v{status?.version}</span>
              : <span className="chip">Draft · {done} of {applicable} sections frozen</span>}
          {identityFrozen && <button type="button" className="btn-secondary sm" onClick={() => setAskChange(true)}><GitPullRequest size={14} /> Request a change</button>}
        </div>
      </header>

      {change && (
        <div className="bs-change">
          <div>
            <strong>Changing: {change.sections.map((k) => sections.find((s) => s.key === k)?.label || k).join(", ")}</strong>
            {change.reason && <span className="muted"> — {change.reason}</span>}
            <ul>{(change.impacts || []).map((x) => <li key={x}>{x}</li>)}</ul>
          </div>
          <div className="bs-change-act">
            <button type="button" className="btn-secondary sm" disabled={!!busy} onClick={() => run("Withdrawing…", () => api.cancelChange(sid))}><Undo2 size={13} /> Withdraw (restore v{status?.version})</button>
            <button type="button" className="btn-primary sm" disabled={!!busy || !ready} onClick={freezeIdentity}><Check size={13} /> Approve as v{nextVersion(status?.version)}</button>
          </div>
        </div>
      )}
      {busy && <div className="working" role="status"><span className="spinner" aria-hidden="true" /><div><strong>{busy}</strong></div></div>}
      {error && <div className="error-banner" role="alert"><AlertTriangle size={15} /> {error} <button type="button" className="link-btn" onClick={() => setError(null)}>Dismiss</button></div>}

      <div className="bs-grid">
        <nav className="bs-rail" aria-label="Identity sections">
          <button type="button" className={"bs-item extra" + (active === "designs" ? " on" : "")} onClick={() => setActive("designs")}>
            <ImageUp size={15} /><span>Your own designs<small>Optional · {(b.blueprint?.designs || []).length || "none"} uploaded</small></span>
          </button>
          {sections.map((s, i) => {
            const Icon = META[s.key].icon;
            return (
              <button key={s.key} type="button" className={`bs-item ${s.status}` + (active === s.key ? " on" : "") + (s.in_change ? " changing" : "")} onClick={() => setActive(s.key)}>
                <span className="bs-num">{s.status === "frozen" ? <Lock size={11} /> : i + 1}</span>
                <span>{s.label}<small>{s.status === "na" ? "Not needed" : s.status === "frozen" ? "Frozen" : s.status === "ready" ? "Ready to freeze" : s.missing}</small></span>
                <Icon size={14} className="bs-ico" />
              </button>
            );
          })}
          <button type="button" className={"bs-item extra" + (active === "standard" ? " on" : "")} onClick={() => setActive("standard")}>
            <ShieldCheck size={15} /><span>Standard modules<small>Inherited · no design needed</small></span>
          </button>
          <div className="bs-rail-foot">
            {!identityFrozen && !change && <button type="button" className="btn-primary" disabled={!!busy || !ready} onClick={freezeIdentity}><Lock size={14} /> Freeze Identity v1.0</button>}
            {!identityFrozen && !change && !ready && <small className="muted">Every section needs a choice first.</small>}
            {identityFrozen && session.stage === "identity" && <button type="button" className="btn-primary" onClick={() => run("", () => api.getSession(sid))}>Continue <ArrowRight size={14} /></button>}
            {(status?.history || []).length > 0 && <details className="bs-hist"><summary>Version history</summary><ul>{status.history.slice().reverse().map((h) => <li key={h.version + h.at}><b>v{h.version}</b> {h.summary}<small>{h.at.slice(0, 10)}</small></li>)}</ul></details>}
          </div>
        </nav>

        <section className="bs-editor">
          <div className="bs-ed-head">
            <div><h3>{title}</h3><p className="muted small">{hint}</p></div>
            {META[active] && sec && sec.status !== "na" && !identityFrozen && (
              sec.status === "frozen"
                ? (!change || change.sections.includes(active)) && <button type="button" className="btn-secondary sm" disabled={!!busy} onClick={() => freezeSection(active, "unfreeze")}><LockOpen size={13} /> Unfreeze</button>
                : !lr && <button type="button" className="btn-secondary sm" disabled={!!busy || sec.status !== "ready"} title={sec.missing} onClick={() => freezeSection(active, "freeze")}><Lock size={13} /> Freeze section</button>
            )}
          </div>
          {lr && <p className="notice-inline"><Lock size={13} /> {lr}</p>}
          {editor}
          {nextKey && <div className="bs-next"><button type="button" className="link-btn" onClick={() => setActive(nextKey)}>Next: {nextKey === "standard" ? "Standard modules" : sections.find((s) => s.key === nextKey)?.label} <ArrowRight size={13} /></button></div>}
        </section>

        <aside className="bs-preview" aria-label="Live preview">
          <div className="bs-pv-head">
            <strong><CircleDashed size={13} /> Live preview</strong>
            <span className="seg sm" role="radiogroup" aria-label="Theme">
              <button type="button" role="radio" aria-checked={mode === "light"} className={mode === "light" ? "on" : ""} onClick={() => setMode("light")}><Sun size={13} /> Light</button>
              <button type="button" role="radio" aria-checked={mode === "dark"} className={mode === "dark" ? "on" : ""} onClick={() => setMode("dark")}><Moon size={13} /> Dark</button>
            </span>
            {["landing", "theme", "standard"].includes(active) && (
              <span className="seg sm" role="radiogroup" aria-label="Device">
                <button type="button" role="radio" aria-checked={device === "web"} className={device === "web" ? "on" : ""} onClick={() => setDevice("web")}><Globe size={13} /> Web</button>
                <button type="button" role="radio" aria-checked={device === "phone"} className={device === "phone" ? "on" : ""} onClick={() => setDevice("phone")}><Smartphone size={13} /> Phone</button>
              </span>
            )}
            {b.blueprint && ["landing", "web", "mobile"].includes(active) && <a className="link-btn" href={api.blueprintPreviewUrl(sid)} target="_blank" rel="noreferrer"><ExternalLink size={12} /> Clickable</a>}
          </div>
          <div className="bs-pv-body" ref={pvRef}>
            <p className="bs-pv-label">Previewing: <b>{title}</b></p>
            <BrandPreview asset={(id) => fileUrl(`/identity/${sid}/designs/file/${id}`)} section={active} session={nameDraft ? { ...session, selected_name: nameDraft.name || session.selected_name, brand: { ...b, tagline: nameDraft.tagline || b.tagline } } : session} palette={pal} bp={bp} mode={mode} device={device} favicon={favicon} />
          </div>
        </aside>
      </div>

      {askChange && status && (
        <ChangeDialog status={status} onClose={() => setAskChange(false)}
          onOpen={(keys, reason) => { setAskChange(false); setActive(keys[0]); run("Opening change request…", () => api.openChange(sid, keys, reason)); }} />
      )}
    </div>
  );
}
