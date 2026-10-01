import { useEffect, useRef, useState } from "react";
import { ArrowDown, ArrowRight, ArrowUp, Boxes, Check, ChevronDown, ChevronRight, Globe, Lock, Pencil, Plus, RotateCcw, Save, ShieldCheck, Sparkles, Trash2, Wand2, X } from "lucide-react";
import { api } from "../api.js";
import { ACCESS, STANDARD_HINTS, accessLabel } from "../standard.js";

// Each card carries a client-only _id so edits survive reorders.
let seq = 0;
const withId = (m) => ({ ...m, _id: m._id || `m${++seq}` });
const strip = ({ _id, ...m }) => m; // eslint-disable-line no-unused-vars
const rowsFor = (t) => Math.min(16, Math.max(4, Math.ceil((t || "").length / 100) + ((t || "").match(/\n/g) || []).length));

function MergedFrom({ list }) {
  if (!list?.length) return null;
  return <div className="merged-from"><span>Replaces</span>{list.map((x) => <span key={x} className="chip">{x}</span>)}</div>;
}

function ModuleView({ m, i, count, busy, onUp, onDown, onEdit, onDelete }) {
  const [confirming, setConfirming] = useState(false);
  return (
    <li className="module-edit">
      <span className="module-num">{i + 1}</span>
      <div className="module-fields">
        <div className="module-top">
          <span className="module-icon" aria-hidden="true"><Boxes size={16} /></span>
          <h3 className="module-view-name">{m.name}</h3>
          <span className={"chip access-chip " + (m.access || "signed_in")}>{m.access && m.access !== "signed_in" ? <Globe size={12} aria-hidden="true" /> : <Lock size={12} aria-hidden="true" />} {accessLabel(m.access)}</span>
        </div>
        {m.description
          ? <p className="module-view-desc">{m.description}</p>
          : <p className="muted small">No description yet — click Edit to describe what this module is responsible for.</p>}
        {m.access && m.access !== "signed_in" && m.access_note && <p className="access-note"><b>Without signing in:</b> {m.access_note}</p>}
        <MergedFrom list={m.merged_from} />
        {confirming && (
          <div className="inline-confirm" role="alert">
            <span>Delete “{m.name}”? This saves immediately.</span>
            <button type="button" className="btn-secondary sm" onClick={() => setConfirming(false)}>Keep</button>
            <button type="button" className="btn-primary danger-btn" disabled={busy} onClick={() => { setConfirming(false); onDelete(); }}><Trash2 size={13} /> Delete</button>
          </div>
        )}
      </div>
      <div className="module-tools">
        <button type="button" className="icon-btn" aria-label={`Move ${m.name} up`} title="Move up" disabled={busy || i === 0} onClick={onUp}><ArrowUp size={15} /></button>
        <button type="button" className="icon-btn" aria-label={`Move ${m.name} down`} title="Move down" disabled={busy || i === count - 1} onClick={onDown}><ArrowDown size={15} /></button>
        <button type="button" className="icon-btn" aria-label={`Edit ${m.name}`} title="Edit" disabled={busy} onClick={onEdit}><Pencil size={15} /></button>
        <button type="button" className="icon-btn danger" aria-label={`Delete ${m.name}`} title="Delete" disabled={busy} onClick={() => setConfirming(true)}><Trash2 size={15} /></button>
      </div>
    </li>
  );
}

function ModuleForm({ d, i, isNew, busy, error, onChange, onSave, onCancel }) {
  return (
    <li className="module-edit editing">
      <span className="module-num">{i + 1}</span>
      <div className="module-fields">
        <div className="module-top">
          <span className="module-icon" aria-hidden="true"><Boxes size={16} /></span>
          <input className="module-name-input" autoFocus={isNew} value={d.name} placeholder="Module name" aria-label={`Module ${i + 1} name`}
            onChange={(e) => onChange({ name: e.target.value })} onKeyDown={(e) => e.key === "Enter" && onSave()} />
        </div>
        <textarea rows={rowsFor(d.description)} value={d.description || ""} aria-label={`Module ${i + 1} description`}
          placeholder="What is this module responsible for? Describe it in your own words — this guides its flow and requirement document."
          onChange={(e) => onChange({ description: e.target.value })} />
        <MergedFrom list={d.merged_from} />
        <div className="module-foot">
          <span className="foot-label">Who can use it?</span>
          <div className="seg" role="radiogroup" aria-label={`Module ${i + 1} access`}>
            {ACCESS.map((a) => (
              <button key={a.value} type="button" role="radio" aria-checked={(d.access || "signed_in") === a.value} title={a.hint}
                className={(d.access || "signed_in") === a.value ? "on" : ""} onClick={() => onChange({ access: a.value })}>
                {a.value === "signed_in" ? <Lock size={13} /> : <Globe size={13} />} {a.label}
              </button>
            ))}
          </div>
        </div>
        {d.access && d.access !== "signed_in" && (
          <input className="access-note-input" value={d.access_note || ""} aria-label="What visitors can do without signing in"
            placeholder={d.access === "public" ? "What is public? e.g. landing page, monthly contest, free caption tool" : "What can visitors try without an account? e.g. repurpose one link for free"}
            onChange={(e) => onChange({ access_note: e.target.value })} />
        )}
        {error && <p className="field-error" role="alert">{error}</p>}
      </div>
      <div className="module-tools">
        <button type="button" className="btn-primary sm-primary" disabled={busy} onClick={onSave}><Save size={13} /> {busy ? "Saving…" : "Save"}</button>
        <button type="button" className="btn-secondary sm" disabled={busy} onClick={onCancel}><X size={13} /> Cancel</button>
      </div>
    </li>
  );
}

function StandardCard({ m, busy, onSave }) {
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(m.tailoring || "");
  useEffect(() => { if (!editing) setText(m.tailoring || ""); }, [m.tailoring, editing]);
  return (
    <li className={"std-card" + (editing ? " editing" : "")}>
      <div className="std-head">
        <span className="module-icon std" aria-hidden="true"><ShieldCheck size={16} /></span>
        <div className="std-title">
          <strong>{m.name}</strong>
          <span>{m.description}</span>
        </div>
        {!editing && (
          <button type="button" className="icon-btn" title="Tailor for this product" aria-label={`Tailor ${m.name}`} disabled={busy} onClick={() => setEditing(true)}><Pencil size={15} /></button>
        )}
      </div>
      {editing ? (
        <div className="std-edit">
          <label className="foot-label" htmlFor={`tailor-${m.standard_key}`}>Tailor for this product (optional)</label>
          <textarea id={`tailor-${m.standard_key}`} rows={3} value={text} placeholder={STANDARD_HINTS[m.standard_key]} onChange={(e) => setText(e.target.value)} />
          <div className="requirement-actions">
            <button type="button" className="btn-secondary sm" disabled={busy} onClick={() => { setText(m.tailoring || ""); setEditing(false); }}><X size={13} /> Cancel</button>
            <button type="button" className="btn-primary sm-primary" disabled={busy} onClick={async () => { if (await onSave(text.trim())) setEditing(false); }}><Save size={13} /> Save</button>
          </div>
        </div>
      ) : m.tailoring ? (
        <p className="std-tailoring"><b>Tailored:</b> {m.tailoring}</p>
      ) : (
        <button type="button" className="link-btn" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
          {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />} Uses the GiveWings standard as-is
        </button>
      )}
      {open && !editing && !m.tailoring && <p className="muted small std-more">Click the pencil to add product specifics — for example {STANDARD_HINTS[m.standard_key]?.replace(/^e\.g\. /, "")}.</p>}
    </li>
  );
}

export default function ScopeFreeze({ session, setSession }) {
  const sid = session.session_id;
  const DRAFT_KEY = `gw_scope_drafts_${sid}`;
  const isStd = (m) => m.kind === "standard";
  const standards = (session.module_specs || []).filter(isStd);
  const [mods, setMods] = useState(() => (session.module_specs || []).filter((m) => !isStd(m)).map(withId)); // saved product modules
  const [drafts, setDrafts] = useState({}); // _id -> draft for cards being edited
  const [newIds, setNewIds] = useState({}); // _id -> true for never-saved cards
  const [cardErr, setCardErr] = useState({});
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [savedAt, setSavedAt] = useState(null);
  const [restorable, setRestorable] = useState(null);
  const [instruction, setInstruction] = useState("");
  const [target, setTarget] = useState("");
  const [proposal, setProposal] = useState(null);
  const [thinking, setThinking] = useState(false);
  const modsRef = useRef(mods);
  modsRef.current = mods;

  const editing = Object.keys(drafts).length;
  const archivedCount = (session.requirement_archive || []).reduce((n, a) => n + a.requirements.length, 0);

  // First visit: ask the AI for a module breakdown.
  useEffect(() => {
    // Always ask the server: it drafts the breakdown on first visit and adds
    // the GiveWings standard modules to scopes created before they existed.
    if (!session.module_specs?.length) setLoading(true);
    api.freeze(sid)
      .then((s) => {
        setSession(s);
        if (!session.module_specs?.length || !(session.module_specs || []).some(isStd)) setMods((s.module_specs || []).filter((m) => !isStd(m)).map(withId));
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
    // Offer to restore unsaved card edits from an earlier visit.
    try {
      const raw = localStorage.getItem(DRAFT_KEY);
      if (raw) {
        const d = JSON.parse(raw);
        if (d.drafts?.length) setRestorable(d); else localStorage.removeItem(DRAFT_KEY);
      }
    } catch { /* storage unavailable */ }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sid]);

  // Keep open drafts on this device and warn before leaving with unsaved edits.
  useEffect(() => {
    try {
      if (editing) {
        const list = Object.entries(drafts).map(([id, d]) => ({ ...strip(d), _new: !!newIds[id], _orig: modsRef.current.find((m) => m._id === id)?.name || null }));
        localStorage.setItem(DRAFT_KEY, JSON.stringify({ drafts: list, at: new Date().toISOString() }));
      } else localStorage.removeItem(DRAFT_KEY);
    } catch { /* ignore */ }
    if (!editing) return undefined;
    const warn = (e) => { e.preventDefault(); e.returnValue = ""; };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [drafts]);

  async function persist(list) {
    setBusy(true);
    setError(null);
    try {
      const s = await api.saveModules(sid, [...standards, ...list.map(strip)]);
      setMods(list);
      setSession(s);
      setSavedAt(new Date());
      return true;
    } catch (e) {
      setError(`Couldn't save to the server: ${e.message}. Nothing was lost — try again.`);
      return false;
    } finally {
      setBusy(false);
    }
  }

  const closeDraft = (id) => {
    setDrafts(({ [id]: _, ...rest }) => rest); // eslint-disable-line no-unused-vars
    setNewIds(({ [id]: _, ...rest }) => rest); // eslint-disable-line no-unused-vars
    setCardErr(({ [id]: _, ...rest }) => rest); // eslint-disable-line no-unused-vars
  };

  async function saveCard(id) {
    const d = drafts[id];
    const name = (d.name || "").trim();
    if (!name) return setCardErr((e) => ({ ...e, [id]: "Give the module a name." }));
    if (mods.some((m) => m._id !== id && m.name.trim().toLowerCase() === name.toLowerCase()))
      return setCardErr((e) => ({ ...e, [id]: "Another module already has this name." }));
    const clean = { ...d, name, description: (d.description || "").trim() };
    const list = mods.map((m) => (m._id === id ? clean : m));
    if (await persist(list)) closeDraft(id);
  }

  const cancelCard = (id) => {
    if (newIds[id]) setMods((m) => m.filter((x) => x._id !== id));
    closeDraft(id);
  };

  const startEdit = (m) => setDrafts((d) => ({ ...d, [m._id]: { ...m } }));
  const change = (id, patch) => { setDrafts((d) => ({ ...d, [id]: { ...d[id], ...patch } })); setCardErr(({ [id]: _, ...rest }) => rest); }; // eslint-disable-line no-unused-vars

  // Saved list only (drafts that were never saved are excluded from the server copy).
  const savedOnly = (list) => list.filter((m) => !newIds[m._id]);

  async function saveTailoring(key, tailoring) {
    setBusy(true);
    setError(null);
    try {
      const std = standards.map((m) => (m.standard_key === key ? { ...m, tailoring } : m));
      setSession(await api.saveModules(sid, [...std, ...mods.filter((m) => !newIds[m._id]).map(strip)]));
      setSavedAt(new Date());
      return true;
    } catch (e) {
      setError(`Couldn't save to the server: ${e.message}`);
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function move(i, dir) {
    const j = i + dir;
    if (j < 0 || j >= mods.length) return;
    const n = [...mods];
    [n[i], n[j]] = [n[j], n[i]];
    setMods(n);
    if (!(await persist(n))) setMods(mods); // moves are disabled while any card is being edited
  }

  async function remove(id) {
    const n = mods.filter((m) => m._id !== id);
    await persist(n);
  }

  const add = () => {
    const m = withId({ name: "", description: "", access: "signed_in", access_note: "" });
    setMods((x) => [...x, m]);
    setNewIds((x) => ({ ...x, [m._id]: true }));
    setDrafts((d) => ({ ...d, [m._id]: { ...m } }));
  };

  async function simplify() {
    setThinking(true);
    setError(null);
    try {
      setProposal(await api.consolidateModules(sid, instruction.trim(), target ? Number(target) : null));
    } catch (e) {
      setError(e.message);
    } finally {
      setThinking(false);
    }
  }

  async function useProposal() {
    const list = proposal.modules.filter((m) => !isStd(m)).map(withId);
    if (await persist(list)) {
      setDrafts({}); setNewIds({}); setCardErr({});
      setProposal(null);
    }
  }

  function restore() {
    const d = {}; const nw = {}; let list = [...mods];
    for (const r of restorable.drafts) {
      const { _new, _orig, ...draft } = r;
      const match = _orig && list.find((m) => m.name === _orig);
      if (match && !_new) d[match._id] = { ...draft, _id: match._id };
      else {
        const m = withId({ name: "", description: "", access: "signed_in", access_note: "" });
        list = [...list, m];
        nw[m._id] = true;
        d[m._id] = { ...draft, _id: m._id };
      }
    }
    setMods(list); setNewIds((x) => ({ ...x, ...nw })); setDrafts((x) => ({ ...x, ...d }));
    setRestorable(null);
  }
  const dropRestore = () => { try { localStorage.removeItem(DRAFT_KEY); } catch { /* ignore */ } setRestorable(null); };

  async function freeze() {
    setBusy(true);
    setError(null);
    try {
      setSession(await api.confirmModules(sid));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  const product = savedOnly(mods);

  return (
    <div className="scope">
      {loading && (
        <div className="working" role="status">
          <span className="spinner" aria-hidden="true" />
          <div><strong>Breaking {session.selected_name} into modules…</strong><p>Using the confirmed concept and research findings.</p></div>
        </div>
      )}

      {session.scope_revision > 0 && (
        <div className="callout">
          <Wand2 size={20} aria-hidden="true" />
          <div>
            <strong>Redefining scope (revision {session.scope_revision})</strong>
            <p>{archivedCount ? `${archivedCount} earlier requirement document${archivedCount > 1 ? "s are" : " is"} archived. ` : ""}Merge or remove overlapping modules below — each module should own a distinct part of the journey.</p>
          </div>
        </div>
      )}

      {restorable && (
        <div className="callout">
          <RotateCcw size={20} aria-hidden="true" />
          <div style={{ flex: 1 }}>
            <strong>You have {restorable.drafts.length} unsaved module edit{restorable.drafts.length > 1 ? "s" : ""} from {new Date(restorable.at).toLocaleString()}</strong>
            <p>They were kept on this device but never saved. Restore them to reopen those cards in edit mode.</p>
          </div>
          <div className="composer-actions">
            <button className="btn-secondary sm" onClick={dropRestore}>Discard</button>
            <button className="btn-primary" onClick={restore}>Restore edits</button>
          </div>
        </div>
      )}

      {!loading && mods.length > 0 && (
        <section className="simplify">
          <div className="simplify-head"><Sparkles size={16} aria-hidden="true" /><strong>Restructure with GiveWings AI</strong><span className="muted small">Optional</span></div>
          <p className="muted small" style={{ margin: "0 0 10px" }}>Tell the AI how to restructure the modules (merge overlaps, split one, change the count). It proposes a new list and changes nothing until you choose <b>Use this proposal</b>.</p>
          <div className="simplify-row">
            <input value={instruction} onChange={(e) => setInstruction(e.target.value)} onKeyDown={(e) => e.key === "Enter" && !thinking && simplify()} placeholder="e.g. Small project — keep capture, research and publishing separate" aria-label="Instruction for restructuring modules" />
            <select value={target} onChange={(e) => setTarget(e.target.value)} aria-label="Target number of product modules">
              <option value="">Any number</option>
              {[2, 3, 4, 5, 6].map((n) => <option key={n} value={n}>{n} modules</option>)}
            </select>
            <button className="btn-primary" disabled={thinking || busy} onClick={simplify}><Wand2 size={15} /> {thinking ? "Thinking…" : "Propose modules"}</button>
          </div>
          {proposal && (
            <div className="proposal">
              {proposal.rationale && <p className="lead">{proposal.rationale}</p>}
              <ol className="proposal-list">
                {proposal.modules.filter((m) => !isStd(m)).map((m, i) => (
                  <li key={i}>
                    <strong>{m.name}</strong> <span className="chip">{accessLabel(m.access)}</span>
                    {m.description && <p>{m.description}</p>}
                    <MergedFrom list={m.merged_from} />
                  </li>
                ))}
              </ol>
              <div className="requirement-actions">
                <button className="btn-secondary" onClick={() => setProposal(null)}>Dismiss</button>
                <button className="btn-primary" disabled={busy} onClick={useProposal}>Use this proposal <ArrowRight size={15} /></button>
              </div>
              {editing > 0 && <p className="muted small">Using the proposal replaces the product modules (standard modules stay) and closes the {editing} card{editing > 1 ? "s" : ""} you're editing.</p>}
            </div>
          )}
        </section>
      )}

      {!loading && (
        <div className="review-summary">
          <span><strong>{product.length}</strong> product module{product.length === 1 ? "" : "s"} + <strong>{standards.length}</strong> standard = <strong>{product.length + standards.length}</strong> BRD/PRD documents</span>
          <span className="muted small">Product modules get their own flow design; standard modules use pre-approved GiveWings flows.</span>
        </div>
      )}

      <div className="section-head">
        <h3>Product modules</h3>
        <p className="muted small">What makes this product unique. Keep a small product to 3–4 modules, and say who can use each one.</p>
      </div>
      <ol className="module-editor">
        {mods.map((m, i) => (drafts[m._id]
          ? <ModuleForm key={m._id} d={drafts[m._id]} i={i} isNew={!!newIds[m._id]} busy={busy} error={cardErr[m._id]}
              onChange={(p) => change(m._id, p)} onSave={() => saveCard(m._id)} onCancel={() => cancelCard(m._id)} />
          : <ModuleView key={m._id} m={m} i={i} count={mods.length} busy={busy || editing > 0}
              onUp={() => move(i, -1)} onDown={() => move(i, 1)} onEdit={() => startEdit(m)} onDelete={() => remove(m._id)} />))}
      </ol>

      {!loading && (
        <button type="button" className="add-row" disabled={busy} onClick={add}><Plus size={16} /> Add a module</button>
      )}

      {standards.length > 0 && (
        <section className="std-section">
          <div className="section-head">
            <h3><ShieldCheck size={17} aria-hidden="true" /> Standard modules <span className="chip">GiveWings standard v1.0</span></h3>
            <p className="muted small">Included in every product and shipped in its own code, so it runs independently wherever it is hosted. Written from GiveWings templates — tailor them to this product if needed. The health agent reports to the GiveWings Health Dashboard once the owner connects it.</p>
          </div>
          <ul className="std-grid">
            {standards.map((m) => <StandardCard key={m.standard_key} m={m} busy={busy || loading} onSave={(t) => saveTailoring(m.standard_key, t)} />)}
          </ul>
        </section>
      )}

      {error && <div className="error-banner" role="alert">{error}</div>}

      <div className="sticky-actions">
        <span className="muted">
          {editing ? `${editing} module${editing > 1 ? "s" : ""} still being edited — save or cancel first.`
            : busy ? "Saving…"
            : product.length === 0 ? "Add at least one product module to continue."
            : savedAt ? <><Check size={14} /> All changes saved {savedAt.toLocaleTimeString()}. Freeze when you're happy.</>
            : "Every module is saved. Freeze when you're happy with the list."}
        </span>
        <div className="composer-actions">
          <button className="btn-primary" disabled={busy || loading || editing > 0 || product.length === 0} onClick={freeze}>
            Freeze scope & design flows <ArrowRight size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}
