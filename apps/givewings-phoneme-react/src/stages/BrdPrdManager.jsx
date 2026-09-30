import { useState } from "react";
import { ChevronDown, ChevronRight, Lock, Sparkles, Wand2 } from "lucide-react";
import { api } from "../api.js";
import RequirementDoc, { FlowStrip, LegacyBody } from "./RequirementDoc.jsx";

function statusClass(status) {
  if (status === "Approved" || status === "Frozen") return "chip good";
  if (status.startsWith("Revised")) return "chip warn";
  return "chip";
}

function RequirementCard({ sessionId, req, onChange, open, onToggle }) {
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState(null);
  const pending = !!(req.revised_doc || req.revised_body);

  async function act(label, fn) {
    setBusy(label);
    setError(null);
    try {
      onChange(await fn());
      return true;
    } catch (e) {
      setError(e.message);
      return false;
    } finally {
      setBusy("");
    }
  }

  const submitComment = async () => {
    if (!comment.trim()) return;
    if (await act("Reworking…", () => api.comment(sessionId, req.req_id, comment.trim()))) setComment("");
  };

  const counts = req.doc
    ? `${req.doc.journey?.length || 0} steps · ${req.doc.acceptance_criteria?.length || 0} acceptance criteria`
    : "Old prose format";

  return (
    <article className={"requirement-card doc-card" + (req.status === "Frozen" ? " frozen" : "") + (open ? " open" : "")}>
      <button type="button" className="doc-head" onClick={onToggle} aria-expanded={open}>
        {open ? <ChevronDown size={18} aria-hidden="true" /> : <ChevronRight size={18} aria-hidden="true" />}
        <span className="req-id">{req.req_id}</span>
        <span className="doc-title">
          <strong>{req.title}</strong>
          <small>{req.module} · {counts}</small>
        </span>
        {req.status === "Frozen" && <Lock size={14} aria-hidden="true" className="frozen-lock" />}
        <span className={statusClass(req.status)}>{req.status}</span>
      </button>

      {!open && req.doc && <div className="doc-peek"><FlowStrip journey={req.doc.journey} /></div>}

      {open && (
        <div className="doc-body">
          {req.doc ? <RequirementDoc doc={req.doc} /> : (
            <>
              <div className="callout">
                <Wand2 size={20} aria-hidden="true" />
                <div>
                  <strong>This requirement is in the old prose format</strong>
                  <p>Convert it into readable sections — summary, step-by-step flow, business rules and acceptance criteria — with technical detail moved out to Technical Design. You'll review the result before it replaces this text.</p>
                </div>
              </div>
              <LegacyBody text={req.body} />
            </>
          )}

          {pending && (
            <div className="diff-block">
              <div className="diff-label"><Sparkles size={13} aria-hidden="true" /> Proposed revision{req.revised_title && req.revised_title !== req.title ? ` — “${req.revised_title}”` : ""}</div>
              {req.revised_doc ? <RequirementDoc doc={req.revised_doc} compact /> : <LegacyBody text={req.revised_body} />}
              <div className="requirement-actions">
                <button className="btn-secondary" disabled={!!busy} onClick={() => act("Discarding…", () => api.discard(sessionId, req.req_id))}>Discard</button>
                <button className="btn-primary" disabled={!!busy} onClick={() => act("Accepting…", () => api.accept(sessionId, req.req_id))}>Accept revision</button>
              </div>
            </div>
          )}

          {!pending && req.status !== "Frozen" && (
            <div className="comment-row">
              <textarea
                className="chat-textarea"
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    if (!busy && comment.trim()) submitComment();
                  }
                }}
                placeholder="Ask for a change in plain words — e.g. 'add a rule that users can delete an item permanently'… (Shift+Enter for a new line)"
                disabled={!!busy}
                rows={2}
              />
              <div className="requirement-actions">
                {!req.doc && <button className="btn-secondary" disabled={!!busy} onClick={() => act("Restructuring…", () => api.restructure(sessionId, req.req_id))}><Wand2 size={15} /> Restructure</button>}
                <button className="btn-secondary" disabled={!!busy || !comment.trim()} onClick={submitComment}>Rework with AI</button>
                {req.status === "Draft" && <button className="btn-primary" disabled={!!busy} onClick={() => act("Approving…", () => api.accept(sessionId, req.req_id))}>Approve</button>}
                {req.status === "Approved" && <button className="btn-primary" disabled={!!busy} onClick={() => act("Freezing…", () => api.freezeRequirement(sessionId, req.req_id))}><Lock size={14} /> Freeze</button>}
              </div>
            </div>
          )}

          {busy && <div className="working" role="status"><span className="spinner" aria-hidden="true" /><div><strong>{busy}</strong><p>GiveWings AI is rewriting this requirement in business language.</p></div></div>}
          {error && <div className="error-banner" role="alert">{error}</div>}
        </div>
      )}
    </article>
  );
}

export default function BrdPrdManager({ session, requirements, setRequirements }) {
  const [openIds, setOpenIds] = useState(() => new Set());
  const [bulk, setBulk] = useState(null); // {done, total}
  const [bulkError, setBulkError] = useState(null);
  if (!session) return null;

  function handleChange(updated) {
    setRequirements((reqs) => reqs.map((r) => (r.req_id === updated.req_id ? updated : r)));
    if (updated.revised_doc || updated.revised_body) setOpenIds((s) => new Set(s).add(updated.req_id));
  }
  const toggle = (id) => setOpenIds((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });

  const sorted = [...requirements].sort((a, b) => a.req_id.localeCompare(b.req_id));
  const count = (st) => requirements.filter((r) => r.status === st).length;
  const frozen = count("Frozen");
  const approved = count("Approved");
  const inReview = requirements.filter((r) => r.status.startsWith("Revised")).length;
  const drafts = count("Draft");
  const total = requirements.length;
  const legacy = sorted.filter((r) => !r.doc && !r.revised_doc && r.status !== "Frozen");
  const allOpen = sorted.length > 0 && sorted.every((r) => openIds.has(r.req_id));

  async function restructureAll() {
    setBulk({ done: 0, total: legacy.length });
    setBulkError(null);
    for (let i = 0; i < legacy.length; i++) {
      try {
        handleChange(await api.restructure(session.session_id, legacy[i].req_id));
      } catch (e) {
        setBulkError(`${legacy[i].req_id}: ${e.message}`);
      }
      setBulk({ done: i + 1, total: legacy.length });
    }
    setBulk(null);
  }

  return (
    <div className="review">
      {total > 0 ? (
        <div className="gen-board">
          <div className="gen-stats">
            <div className="gen-stat"><span>Documents</span><strong>{total}</strong></div>
            <div className="gen-stat"><span>Draft</span><strong>{drafts}</strong></div>
            <div className="gen-stat warn"><span>Revision to review</span><strong>{inReview}</strong></div>
            <div className="gen-stat"><span>Approved</span><strong>{approved}</strong></div>
            <div className="gen-stat good"><span>Frozen</span><strong>{frozen}</strong></div>
          </div>
          <div className="gen-meter" role="progressbar" aria-valuemin={0} aria-valuemax={total} aria-valuenow={frozen} aria-label="Frozen requirements">
            <i style={{ width: `${(frozen / total) * 100}%` }} />
          </div>
          <p className="muted small"><strong>{total - frozen}</strong> of {total} still to freeze for <strong>{session.selected_name}</strong>. Approve a document, then freeze it to hand it to Technical Design.</p>
        </div>
      ) : (
        <p className="muted">No requirements drafted yet.</p>
      )}

      {legacy.length > 0 && (
        <div className="callout">
          <Wand2 size={20} aria-hidden="true" />
          <div style={{ flex: 1 }}>
            <strong>{legacy.length} requirement{legacy.length > 1 ? "s are" : " is"} in the old prose format</strong>
            <p>Restructure them into readable sections with technical detail moved out. Each result comes back as a revision for you to accept or discard.</p>
            {bulk && <p className="small"><span className="spinner sm" aria-hidden="true" /> Restructuring {bulk.done} of {bulk.total}…</p>}
            {bulkError && <p className="small" style={{ color: "#8f2020" }}>{bulkError}</p>}
          </div>
          <button className="btn-primary" disabled={!!bulk} onClick={restructureAll}><Wand2 size={15} /> Restructure all</button>
        </div>
      )}

      {sorted.length > 1 && (
        <div className="doc-toolbar">
          <button type="button" className="btn-secondary sm" onClick={() => setOpenIds(allOpen ? new Set() : new Set(sorted.map((r) => r.req_id)))}>
            {allOpen ? "Collapse all" : "Expand all"}
          </button>
        </div>
      )}

      <div className="requirement-feed">
        {sorted.map((r) => (
          <RequirementCard
            key={r.req_id}
            sessionId={session.session_id}
            req={r}
            onChange={handleChange}
            open={openIds.has(r.req_id) || !!(r.revised_doc || r.revised_body)}
            onToggle={() => toggle(r.req_id)}
          />
        ))}
      </div>
    </div>
  );
}
