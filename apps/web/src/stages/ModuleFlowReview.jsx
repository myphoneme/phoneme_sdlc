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

  return (
    <div className="stage-card">
      <h2>Flow Design — key sequence flow per module</h2>
      <p className="stage-hint">
        Before BRD/PRD drafting starts, pin down how each module actually works — the frontend + backend
        steps in order. Comment to redirect a flow, approve it once it's right, then continue once every
        module is approved so the requirements that follow are grounded in a concrete mechanism.
      </p>

      {loading && (session?.module_flows || []).length === 0 && (
        <div className="stage-hint">Drafting sequence flows for each module…</div>
      )}
      {error && <div className="error-banner">{error}</div>}

      <div className="requirement-feed">
        {reviewable.map((f) => (
          <FlowCard key={f.module} sessionId={session.session_id} flow={f} onChange={handleChange} />
        ))}
      </div>

      <hr className="divider" />

      <div className="requirement-actions">
        <button className="btn-primary" disabled={loading || !allApproved} onClick={freezeFlows}>
          {allApproved ? "Freeze flows & continue to BRD/PRD" : "Approve every module flow to continue"}
        </button>
      </div>
    </div>
  );
}
