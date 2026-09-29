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
              placeholder="Leave a review comment to request a revision… (Shift+Enter for a new line)"
              disabled={busy}
              rows={3}
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

  const frozen = requirements.filter((r) => r.status === "Frozen").length;

  return (
    <div className="review">
      {requirements.length > 0 ? (
        <div className="review-summary">
          <span><strong>{frozen}</strong> of {requirements.length} requirements frozen for <strong>{session.selected_name}</strong></span>
          <span className="review-meter" aria-hidden="true"><i style={{ width: `${(frozen / requirements.length) * 100}%` }} /></span>
        </div>
      ) : (
        <p className="muted">No requirements drafted yet.</p>
      )}
      <div className="requirement-feed">
        {requirements.map((r) => (
          <RequirementCard key={r.req_id} sessionId={session.session_id} req={r} onChange={handleChange} />
        ))}
      </div>
    </div>
  );
}
