import { useEffect, useState } from "react";
import { ArrowDown, ArrowUp, PenLine, Plus, Trash2 } from "lucide-react";
import { api } from "../api.js";

function statusClass(status) {
  if (status === "Approved") return "chip good";
  if (status.startsWith("Revised")) return "chip warn";
  return "chip";
}

function StepEditor({ steps, onSave, onCancel, busy }) {
  const [list, setList] = useState(steps);
  const edit = (i, v) => setList((l) => l.map((x, j) => (j === i ? v : x)));
  const move = (i, d) => setList((l) => {
    const n = [...l];
    const j = i + d;
    if (j < 0 || j >= n.length) return l;
    [n[i], n[j]] = [n[j], n[i]];
    return n;
  });
  const insert = (i) => setList((l) => [...l.slice(0, i + 1), "", ...l.slice(i + 1)]);
  const remove = (i) => setList((l) => l.filter((_, j) => j !== i));
  const clean = list.map((x) => x.trim()).filter(Boolean);
  return (
    <div className="step-editor">
      <ol>
        {list.map((st, i) => (
          <li key={i}>
            <span className="step-no">{i + 1}</span>
            <textarea rows={2} value={st} aria-label={`Step ${i + 1}`} placeholder="Describe this step…" onChange={(e) => edit(i, e.target.value)} />
            <span className="step-tools">
              <button type="button" className="icon-btn" aria-label="Move step up" disabled={i === 0} onClick={() => move(i, -1)}><ArrowUp size={14} /></button>
              <button type="button" className="icon-btn" aria-label="Move step down" disabled={i === list.length - 1} onClick={() => move(i, 1)}><ArrowDown size={14} /></button>
              <button type="button" className="icon-btn" aria-label="Insert a step below" onClick={() => insert(i)}><Plus size={14} /></button>
              <button type="button" className="icon-btn danger" aria-label="Delete step" onClick={() => remove(i)}><Trash2 size={14} /></button>
            </span>
          </li>
        ))}
      </ol>
      <button type="button" className="add-row" onClick={() => setList((l) => [...l, ""])}><Plus size={16} /> Add a step</button>
      <div className="requirement-actions">
        <button className="btn-secondary" disabled={busy} onClick={onCancel}>Cancel</button>
        <button className="btn-primary" disabled={busy || clean.length === 0} onClick={() => onSave(clean)}>Save flow</button>
      </div>
    </div>
  );
}

function FlowCard({ sessionId, flow, onChange }) {
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState(null);

  async function act(fn) {
    setBusy(true);
    setError(null);
    try {
      onChange(await fn());
      return true;
    } catch (e) {
      setError(e.message);
      return false;
    } finally {
      setBusy(false);
    }
  }

  const submitComment = async () => {
    if (!comment.trim()) return;
    if (await act(() => api.commentFlow(sessionId, flow.module, comment.trim()))) setComment("");
  };

  return (
    <div className={"requirement-card" + (flow.status === "Approved" ? " approved" : "")}>
      <div className="requirement-header">
        <span className="req-title">{flow.module}</span>
        <span className="req-count">{flow.steps.length} steps</span>
        <span className={statusClass(flow.status)}>{flow.status}</span>
        {!editing && !flow.revised_steps && (
          <button type="button" className="btn-secondary sm" disabled={busy} onClick={() => setEditing(true)}><PenLine size={14} /> Edit steps</button>
        )}
      </div>

      {editing ? (
        <StepEditor
          steps={flow.steps}
          busy={busy}
          onCancel={() => setEditing(false)}
          onSave={async (steps) => { if (await act(() => api.updateFlow(sessionId, flow.module, steps))) setEditing(false); }}
        />
      ) : (
        <ol className="flow-step-list">
          {flow.steps.map((s, i) => <li key={i}>{s}</li>)}
        </ol>
      )}

      {flow.revised_steps && (
        <div className="diff-block">
          <div className="diff-label">Proposed revision</div>
          <ol className="flow-step-list flow-step-list-new">
            {flow.revised_steps.map((s, i) => <li key={i}>{s}</li>)}
          </ol>
          <div className="requirement-actions">
            <button className="btn-secondary" disabled={busy} onClick={() => act(() => api.discardFlow(sessionId, flow.module))}>Discard</button>
            <button className="btn-primary" disabled={busy} onClick={() => act(() => api.acceptFlow(sessionId, flow.module))}>Accept &amp; use this flow</button>
          </div>
        </div>
      )}

      {!editing && !flow.revised_steps && (
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
            placeholder="Or describe a change and let GiveWings AI rework the whole flow — e.g. which channel to use, what is automatic vs. confirmed by the user…"
            disabled={busy}
            rows={2}
          />
          <div className="requirement-actions">
            <button className="btn-secondary" disabled={busy || !comment.trim()} onClick={submitComment}>Rework with AI</button>
            {flow.status !== "Approved" && (
              <button className="btn-primary" disabled={busy} onClick={() => act(() => api.acceptFlow(sessionId, flow.module))}>Approve flow</button>
            )}
          </div>
        </div>
      )}

      {error && <div className="error-banner" role="alert">{error}</div>}
    </div>
  );
}

export default function ModuleFlowReview({ session, setSession }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const reviewable = (session?.module_flows || []).filter(
    (f) => !f.module.toLowerCase().startsWith("platform-core")
  );
  const allApproved = reviewable.length > 0 && reviewable.every((f) => f.status === "Approved");

  const expected = (session?.modules || []).filter((m) => !m.toLowerCase().startsWith("platform-core")).length;

  useEffect(() => {
    if (session && reviewable.length < expected) {
      setLoading(true);
      // Flows are saved one by one on the server; poll so each appears as
      // soon as it is drafted instead of waiting for the whole batch.
      const poll = setInterval(() => {
        api.getSession(session.session_id).then((s) => {
          if ((s.module_flows || []).length > (session.module_flows || []).length) setSession(s);
        }).catch(() => {});
      }, 3000);
      api
        .generateFlows(session.session_id)
        .then(setSession)
        .catch((e) => setError(e.message))
        .finally(() => { clearInterval(poll); setLoading(false); });
      return () => clearInterval(poll);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.session_id]);

  function handleChange(updated) {
    setSession(updated);
  }

  async function freezeFlows() {
    setLoading(true);
    setError(null);
    try {
      setSession(await api.freezeFlows(session.session_id));
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  if (!session) return null;

  const approvedCount = reviewable.filter((f) => f.status === "Approved").length;

  return (
    <div className="review">
      {loading && (
        <div className="working" role="status">
          <span className="spinner" aria-hidden="true" />
          <div><strong>Drafting sequence flows — {reviewable.length} of {expected} ready</strong><p>You can start reviewing the ones below while the rest are drafted.</p></div>
        </div>
      )}
      {error && <div className="error-banner" role="alert">{error}</div>}

      {reviewable.length > 0 && (
        <div className="review-summary">
          <span><strong>{approvedCount}</strong> of {reviewable.length} module flows approved</span>
          <span className="review-meter" aria-hidden="true"><i style={{ width: `${(approvedCount / reviewable.length) * 100}%` }} /></span>
        </div>
      )}

      <div className="requirement-feed">
        {reviewable.map((f) => (
          <FlowCard key={f.module} sessionId={session.session_id} flow={f} onChange={handleChange} />
        ))}
      </div>

      <div className="sticky-actions">
        <span className="muted">{allApproved ? "All flows approved — ready to draft requirements." : "Approve every module flow to continue."}</span>
        <button className="btn-primary" disabled={loading || !allApproved} onClick={freezeFlows}>
          Freeze flows &amp; continue
        </button>
      </div>
    </div>
  );
}
