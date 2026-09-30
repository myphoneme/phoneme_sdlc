import { useState } from "react";
import { AlertTriangle, ArrowRight, Plus, X } from "lucide-react";
import { api } from "../api.js";

const FIELDS = [
  ["target_users", "Target users", "Who is it for?"],
  ["core_workflow", "Core workflow", "The main loop, start to finish"],
  ["input_channels", "Input channels", "How content or data gets in"],
  ["privacy_mode", "Privacy & visibility", "What stays private, what can be shared or public"],
  ["market", "Launch market & language", "e.g. India — English and Hindi"],
  ["platforms", "Launch platforms", "e.g. Web + Android + WhatsApp"],
];

function ListEditor({ label, hint, items, onChange }) {
  const [draft, setDraft] = useState("");
  const add = () => {
    if (!draft.trim()) return;
    onChange([...items, draft.trim()]);
    setDraft("");
  };
  return (
    <div className="brief-field wide">
      <span className="brief-label">{label}</span>
      <ul className="brief-list">
        {items.map((it, i) => (
          <li key={i}>
            <input value={it} aria-label={`${label} ${i + 1}`} onChange={(e) => onChange(items.map((x, j) => (j === i ? e.target.value : x)))} />
            <button type="button" className="icon-btn" aria-label={`Remove ${it}`} onClick={() => onChange(items.filter((_, j) => j !== i))}><X size={15} /></button>
          </li>
        ))}
      </ul>
      <div className="inline-field">
        <input value={draft} onChange={(e) => setDraft(e.target.value)} onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), add())} placeholder={hint} aria-label={`Add to ${label}`} />
        <button type="button" className="btn-secondary" onClick={add} disabled={!draft.trim()}><Plus size={15} /> Add</button>
      </div>
    </div>
  );
}

export default function ConceptConfirm({ session, setSession }) {
  const initial = session.concept_brief || { summary: session.concept_summary || "", must_haves: [], out_of_scope: [], assumptions: [] };
  const [brief, setBrief] = useState({ must_haves: [], out_of_scope: [], assumptions: [], ...initial });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const set = (k, v) => setBrief((b) => ({ ...b, [k]: v }));

  const unstated = FIELDS.filter(([k]) => !brief[k] || /^not stated/i.test(brief[k].trim()));

  async function confirm() {
    setBusy(true);
    setError(null);
    try {
      setSession(await api.confirmBrief(session.session_id, brief));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="brief">
      <label className="brief-field wide">
        <span className="brief-label">Concept summary</span>
        <textarea rows={3} value={brief.summary} onChange={(e) => set("summary", e.target.value)} />
      </label>

      <div className="brief-grid">
        {FIELDS.map(([k, label, hint]) => {
          const missing = !brief[k] || /^not stated/i.test(brief[k].trim());
          return (
            <label key={k} className={"brief-field" + (missing ? " missing" : "")}>
              <span className="brief-label">{label}{missing && <span className="chip warn">Needs your answer</span>}</span>
              <textarea rows={2} value={missing && /^not stated/i.test(brief[k] || "") ? "" : brief[k] || ""} placeholder={hint} onChange={(e) => set(k, e.target.value)} />
            </label>
          );
        })}
      </div>

      <ListEditor label="Must-have capabilities" hint="Add a must-have…" items={brief.must_haves} onChange={(v) => set("must_haves", v)} />
      <ListEditor label="Out of scope (for now)" hint="Add something to leave out…" items={brief.out_of_scope} onChange={(v) => set("out_of_scope", v)} />

      {brief.assumptions.length > 0 && (
        <div className="callout">
          <AlertTriangle size={20} aria-hidden="true" />
          <div>
            <strong>GiveWings AI had to assume these — correct any that are wrong above</strong>
            <ul className="research-bullet-list" style={{ marginTop: 8 }}>
              {brief.assumptions.map((a, i) => <li key={i}>{a}</li>)}
            </ul>
          </div>
        </div>
      )}

      {error && <div className="error-banner" role="alert">{error}</div>}

      <div className="sticky-actions">
        <span className="muted">
          {unstated.length ? `${unstated.length} field${unstated.length > 1 ? "s" : ""} still empty — fill them for sharper research, or continue anyway.` : "Every decision captured. Research will use exactly this brief."}
        </span>
        <button className="btn-primary" onClick={confirm} disabled={busy || !brief.summary.trim()}>
          {busy ? "Saving…" : "Confirm & start research"} <ArrowRight size={16} />
        </button>
      </div>
    </div>
  );
}
