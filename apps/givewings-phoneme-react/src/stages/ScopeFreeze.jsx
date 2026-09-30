import { useEffect, useState } from "react";
import { ArrowDown, ArrowRight, ArrowUp, Boxes, Link2, Plus, Trash2 } from "lucide-react";
import { api } from "../api.js";

export default function ScopeFreeze({ session, setSession }) {
  const [mods, setMods] = useState(session.module_specs || []);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!session.module_specs?.length) {
      setLoading(true);
      api
        .freeze(session.session_id)
        .then((s) => { setSession(s); setMods(s.module_specs || []); })
        .catch((e) => setError(e.message))
        .finally(() => setLoading(false));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session.session_id]);

  const edit = (i, patch) => { setMods((m) => m.map((x, j) => (j === i ? { ...x, ...patch } : x))); setDirty(true); };
  const move = (i, d) => {
    setMods((m) => {
      const n = [...m];
      const j = i + d;
      if (j < 0 || j >= n.length) return m;
      [n[i], n[j]] = [n[j], n[i]];
      return n;
    });
    setDirty(true);
  };
  const remove = (i) => { setMods((m) => m.filter((_, j) => j !== i)); setDirty(true); };
  const add = () => { setMods((m) => [...m, { name: "", description: "", platform_core: false }]); setDirty(true); };

  const product = mods.filter((m) => !m.platform_core);
  const core = mods.filter((m) => m.platform_core);
  const names = mods.map((m) => m.name.trim().toLowerCase()).filter(Boolean);
  const dupes = names.length !== new Set(names).size;
  const blank = mods.some((m) => !m.name.trim());

  async function save(confirm) {
    setSaving(true);
    setError(null);
    try {
      let s = await api.saveModules(session.session_id, mods);
      setDirty(false);
      if (confirm) s = await api.confirmModules(session.session_id);
      setSession(s);
      setMods(s.module_specs || mods);
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="scope">
      {loading && (
        <div className="working" role="status">
          <span className="spinner" aria-hidden="true" />
          <div><strong>Breaking {session.selected_name} into modules…</strong><p>Using the confirmed concept and research findings.</p></div>
        </div>
      )}

      {mods.length > 0 && (
        <div className="review-summary">
          <span><strong>{product.length}</strong> product module{product.length === 1 ? "" : "s"} · <strong>{core.length}</strong> Platform-Core (shared, not rebuilt)</span>
          <span className="muted small">Each product module gets its own flow and requirement document.</span>
        </div>
      )}

      <ol className="module-editor">
        {mods.map((m, i) => (
          <li key={i} className={"module-edit" + (m.platform_core ? " core" : "")}>
            <span className="module-num">{i + 1}</span>
            <div className="module-fields">
              <div className="module-top">
                <span className="module-icon" aria-hidden="true">{m.platform_core ? <Link2 size={16} /> : <Boxes size={16} />}</span>
                <input className="module-name-input" value={m.name} placeholder="Module name" aria-label={`Module ${i + 1} name`} onChange={(e) => edit(i, { name: e.target.value })} />
              </div>
              <textarea rows={2} value={m.description} placeholder="What is this module responsible for?" aria-label={`Module ${i + 1} description`} onChange={(e) => edit(i, { description: e.target.value })} />
              <label className="toggle">
                <input type="checkbox" checked={m.platform_core} onChange={(e) => edit(i, { platform_core: e.target.checked })} />
                <span>Platform-Core (auth, security, gateway — provided by the platform, not drafted here)</span>
              </label>
            </div>
            <div className="module-tools">
              <button type="button" className="icon-btn" aria-label="Move up" disabled={i === 0} onClick={() => move(i, -1)}><ArrowUp size={15} /></button>
              <button type="button" className="icon-btn" aria-label="Move down" disabled={i === mods.length - 1} onClick={() => move(i, 1)}><ArrowDown size={15} /></button>
              <button type="button" className="icon-btn danger" aria-label={`Remove ${m.name || "module"}`} onClick={() => remove(i)}><Trash2 size={15} /></button>
            </div>
          </li>
        ))}
      </ol>

      {!loading && (
        <button type="button" className="add-row" onClick={add}><Plus size={16} /> Add a module</button>
      )}

      {error && <div className="error-banner" role="alert">{error}</div>}

      <div className="sticky-actions">
        <span className="muted">
          {dupes ? "Two modules have the same name." : blank ? "Every module needs a name." : product.length === 0 ? "Add at least one product module." : dirty ? "Unsaved changes." : "Happy with this list? Freezing it opens Flow Design."}
        </span>
        <div className="composer-actions">
          <button className="btn-secondary" disabled={saving || !dirty || dupes || blank} onClick={() => save(false)}>Save draft</button>
          <button className="btn-primary" disabled={saving || loading || dupes || blank || product.length === 0} onClick={() => save(true)}>
            {saving ? "Saving…" : "Freeze scope & design flows"} <ArrowRight size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}
