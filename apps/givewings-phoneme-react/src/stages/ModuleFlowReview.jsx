import { useEffect, useState } from "react";
import { api } from "../api.js";

function statusClass(status) {
  if (status === "Approved") return "chip good";
  if (status.startsWith("Revised")) return "chip warn";
  return "chip";
}

function FlowCard({ sessionId, flow, onChange }) {
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function submitComment() {
    if (!comment.trim()) return;
    setBusy(true);
    setError(null);
    try {
      onChange(await api.commentFlow(sessionId, flow.module, comment.trim()));
      setComment("");
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function accept() {
    setBusy(true);
    try {
      onChange(await api.acceptFlow(sessionId, flow.module));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function discard() {
    setBusy(true);
    try {
      onChange(await api.discardFlow(sessionId, flow.module));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="requirement-card">
      <div className="requirement-header">
        <span className="req-title">{flow.module}</span>
        <span className="req-count">{flow.steps.length} steps</span>
        <span className={statusClass(flow.status)}>{flow.status}</span>
      </div>

      <ol className="flow-step-list">
        {flow.steps.map((s, i) => (
          <li key={i}>{s}</li>
        ))}
      </ol>

      {flow.revised_steps && (
        <div className="diff-block">
          <div className="diff-label">Proposed revision</div>
          <ol className="flow-step-list flow-step-list-new">
            {flow.revised_steps.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ol>
          <div className="requirement-actions">
            <button className="btn-primary" disabled={busy} onClick={accept}>Accept &amp; use this flow</button>
            <button className="btn-secondary" disabled={busy} onClick={discard}>Discard</button>
          </div>
        </div>
      )}

      {!flow.revised_steps && (
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
            placeholder="Redirect this flow before it's locked in — e.g. which channel/integration to use, what gets auto-created vs. confirmed by the user… (Shift+Enter for a new line)"
            disabled={busy}
            rows={3}
          />
          <button className="btn-secondary" disabled={busy || !comment.trim()} onClick={submitComment}>
            Regenerate from comment
          </button>
        </div>
      )}

      {!flow.revised_steps && flow.status !== "Approved" && (
        <div className="requirement-actions">
          <button className="btn-primary" disabled={busy} onClick={accept}>Approve this flow</button>
        </div>
      )}

      {error && <div className="error-banner">{error}</div>}
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

  useEffect(() => {
    if (session && session.module_flows.length === 0) {
      setLoading(true);
      api
        .generateFlows(session.session_id)
        .then(setSession)
        .catch((e) => setError(e.message))
        .finally(() => setLoading(false));
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
      {loading && (session?.module_flows || []).length === 0 && (
        <div className="working" role="status">
          <span className="spinner" aria-hidden="true" />
          <div><strong>Drafting sequence flows for each module…</strong><p>Frontend and backend steps, in order, for every module.</p></div>
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
