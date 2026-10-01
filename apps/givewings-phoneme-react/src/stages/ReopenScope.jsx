import { useState } from "react";
import { AlertTriangle, RotateCcw } from "lucide-react";
import { api } from "../api.js";

// Inline (not window.confirm) so the consequences are spelled out before
// scope is reopened.
export default function ReopenScope({ session, setSession, requirements = [], compact = false }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const frozen = requirements.filter((r) => r.status === "Frozen").length;
  const productModules = (session.modules || []).filter((m) => !m.toLowerCase().startsWith("platform-core")).length;

  async function reopen() {
    setBusy(true);
    setError(null);
    try {
      setSession(await api.reopenScope(session.session_id, reason.trim()));
    } catch (e) {
      setError(e.message);
      setBusy(false);
    }
  }

  if (!open) {
    return (
      <button type="button" className={compact ? "btn-secondary sm" : "btn-secondary"} onClick={() => setOpen(true)}>
        <RotateCcw size={15} /> Redefine modules
      </button>
    );
  }
  return (
    <div className="reopen-box" role="group" aria-label="Redefine modules">
      <div className="reopen-head"><AlertTriangle size={18} aria-hidden="true" /><strong>Go back to Freeze Scope and redefine the modules?</strong></div>
      <ul className="research-bullet-list">
        <li>You'll be able to merge, rename, add or remove modules — or ask GiveWings AI to simplify the current {productModules}.</li>
        {requirements.length > 0 && <li>The current {requirements.length} requirement document{requirements.length > 1 ? "s" : ""}{frozen ? ` (${frozen} frozen)` : ""} will be archived — still viewable, but replaced by new drafts.</li>}
        <li>Flows for modules you keep are kept but must be re-approved; new or merged modules get new flows.</li>
      </ul>
      <input className="reopen-reason" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Reason (optional) — e.g. small project, too many overlapping modules" aria-label="Reason for redefining scope" />
      {error && <div className="error-banner" role="alert">{error}</div>}
      <div className="requirement-actions">
        <button className="btn-secondary" disabled={busy} onClick={() => setOpen(false)}>Cancel</button>
        <button className="btn-primary" disabled={busy} onClick={reopen}><RotateCcw size={15} /> {busy ? "Reopening…" : "Reopen scope"}</button>
      </div>
    </div>
  );
}
