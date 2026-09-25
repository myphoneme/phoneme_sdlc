import { useState } from "react";
import { api } from "../api.js";

function statusClass(status) {
  if (status === "Approved") return "chip good";
  if (status === "Frozen") return "chip good";
  if (status.startsWith("Revised")) return "chip warn";
  return "chip";
}

function RequirementCard({ sessionId, req, onChange }) {
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function submitComment() {
    if (!comment.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await api.comment(sessionId, req.req_id, comment.trim());
      onChange(updated);
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
      onChange(await api.accept(sessionId, req.req_id));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function discard() {
    setBusy(true);
    try {
      onChange(await api.discard(sessionId, req.req_id));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function freeze() {
    setBusy(true);
    try {
      onChange(await api.freezeRequirement(sessionId, req.req_id));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="requirement-card">
      <div className="requirement-header">
        <span className="req-id">{req.req_id}</span>
        <span className="req-title">{req.title}</span>
        <span className={statusClass(req.status)}>{req.status}</span>
      </div>
      <p className="req-body">{req.body}</p>

      {req.revised_body && (
        <div className="diff-block">
          <div className="diff-label">Proposed revision</div>
          <p className="diff-new">{req.revised_body}</p>
          <div className="requirement-actions">
            <button className="btn-primary" disabled={busy} onClick={accept}>Accept &amp; commit</button>
            <button className="btn-secondary" disabled={busy} onClick={discard}>Discard</button>
          </div>
        </div>
      )}

      {!req.revised_body && req.status !== "Frozen" && (
        <>
          <div className="comment-row">
            <input
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="Leave a review comment to request a revision…"
              disabled={busy}
            />
            <button className="btn-secondary" disabled={busy || !comment.trim()} onClick={submitComment}>
              Regenerate from comment
            </button>
          </div>
          {req.status === "Approved" && (
            <div className="requirement-actions">
              <button className="btn-primary" disabled={busy} onClick={freeze}>Freeze</button>
            </div>
          )}
        </>
      )}

      {error && <div className="error-banner">{error}</div>}
    </div>
  );
}

export default function BrdPrdManager({ session, requirements, setRequirements }) {
  if (!session) return null;

  function handleChange(updated) {
    setRequirements((reqs) => reqs.map((r) => (r.req_id === updated.req_id ? updated : r)));
  }

  return (
    <div className="stage-card">
      <h2>BRD/PRD Manager — {session.selected_name}</h2>
      <p className="stage-hint">
        Review each drafted requirement. Comment to request a revision (routed through the commercial
        model tier), then Accept &amp; commit or Discard, and Freeze once approved.
      </p>
      <div className="requirement-feed">
        {requirements.map((r) => (
          <RequirementCard key={r.req_id} sessionId={session.session_id} req={r} onChange={handleChange} />
        ))}
      </div>
    </div>
  );
}
