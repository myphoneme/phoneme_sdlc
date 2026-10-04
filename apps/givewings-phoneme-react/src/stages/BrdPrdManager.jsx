import { useState } from "react";
import { Archive, ChevronDown, ChevronRight, GitCompare, Lock, LockOpen, Sparkles, Wand2 } from "lucide-react";
import ReopenScope from "./ReopenScope.jsx";
import { api } from "../api.js";
import RequirementDoc, { FlowStrip, LegacyBody } from "./RequirementDoc.jsx";

function statusClass(status) {
  if (status === "Approved" || status === "Frozen") return "chip good";
  if (status.startsWith("Revised")) return "chip warn";
  return "chip";
}

function RequirementCard({ sessionId, req, onChange, open, onToggle }) {
  // Unsent review comments survive a refresh (2026-10-04: a typed comment
  // was left behind when the reviewer clicked Approve).
  const draftKey = `gw_comment_${sessionId}_${req.req_id}`;
  const [comment, setCommentState] = useState(() => { try { return localStorage.getItem(draftKey) || ""; } catch { return ""; } });
  const setComment = (v) => {
    setCommentState(v);
    try { if (v.trim()) localStorage.setItem(draftKey, v); else localStorage.removeItem(draftKey); } catch { /* storage unavailable */ }
  };
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
    if (await act("Applying your comment…", () => api.comment(sessionId, req.req_id, comment.trim()))) setComment("");
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
          <small>{req.module} · {counts}{req.standard_version && <> · <span className="std-tag">GiveWings standard v{req.standard_version}</span></>}</small>
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
              <div className="diff-label"><Sparkles size={13} aria-hidden="true" /> Revised with your comment — review, then Accept to update the document{req.revised_title && req.revised_title !== req.title ? ` — “${req.revised_title}”` : ""}</div>
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
                placeholder="Request a change in plain words — e.g. 'allow sign-in with Google, Apple, Meta and X; two-factor only for paid users'. Then click Apply comment. (Shift+Enter for a new line)"
                disabled={!!busy}
                rows={2}
              />
              {busy === "Applying your comment…" && (
                <div className="working inline" role="status"><span className="spinner sm" aria-hidden="true" /><span>GiveWings AI is applying your comment — the revised document will appear above for you to accept or discard.</span></div>
              )}
              <div className="requirement-actions">
                {comment.trim() ? (
                  <>
                    <span className="muted small comment-hint">Apply your comment first — approving or freezing ignores unsent comments.</span>
                    <button className="btn-secondary" disabled={!!busy} onClick={() => setComment("")}>Clear</button>
                    <button className="btn-primary" disabled={!!busy} onClick={submitComment}><Sparkles size={14} /> {busy === "Applying your comment…" ? "Applying…" : "Apply comment"}</button>
                  </>
                ) : (
                  <>
                    {!req.doc && <button className="btn-secondary" disabled={!!busy} onClick={() => act("Restructuring…", () => api.restructure(sessionId, req.req_id))}><Wand2 size={15} /> Restructure</button>}
                    {req.status === "Draft" && <button className="btn-primary" disabled={!!busy} onClick={() => act("Approving…", () => api.accept(sessionId, req.req_id))}>Approve as is</button>}
                    {req.status === "Approved" && req.doc && <button className="btn-primary" disabled={!!busy} onClick={() => act("Freezing…", () => api.freezeRequirement(sessionId, req.req_id))}><Lock size={14} /> Freeze</button>}
                    {req.status === "Approved" && !req.doc && <span className="muted small">Restructure before freezing</span>}
                  </>
                )}
              </div>
            </div>
          )}

          {req.status === "Frozen" && (
            <div className="requirement-actions">
              <span className="muted small">Frozen — locked for Technical Design.</span>
              <button className="btn-secondary" disabled={!!busy} onClick={() => act("Unfreezing…", () => api.unfreeze(sessionId, req.req_id))}><LockOpen size={14} /> Unfreeze to change</button>
            </div>
          )}

          {busy && <div className="working" role="status"><span className="spinner" aria-hidden="true" /><div><strong>{busy}</strong><p>GiveWings AI is rewriting this requirement in business language.</p></div></div>}
          {error && <div className="error-banner" role="alert">{error}</div>}
        </div>
      )}
    </article>
  );
}

export default function BrdPrdManager({ session, setSession, requirements, setRequirements }) {
  const [openIds, setOpenIds] = useState(() => new Set());
  const [bulk, setBulk] = useState(null); // {done, total}
  const [bulkError, setBulkError] = useState(null);
  const [checking, setChecking] = useState(false);
  const [checkError, setCheckError] = useState(null);
  const [applying, setApplying] = useState(null);
  const [showArchive, setShowArchive] = useState(false);
  if (!session) return null;

  async function runCheck() {
    setChecking(true);
    setCheckError(null);
    try {
      setSession(await api.checkConsistency(session.session_id));
    } catch (e) {
      setCheckError(e.message);
    } finally {
      setChecking(false);
    }
  }

  // Send the suggestion as a review comment to every unfrozen document the
  // issue names; each comes back as a revision to accept or discard.
  async function applyIssue(issue, idx) {
    setApplying(idx);
    setCheckError(null);
    const targets = issue.documents.filter((id) => requirements.find((r) => r.req_id === id && r.status !== "Frozen"));
    for (const id of targets) {
      try {
        handleChange(await api.comment(session.session_id, id, `Cross-document review: ${issue.problem} Fix: ${issue.suggestion} Only change what concerns ${id}.`));
      } catch (e) {
        setCheckError(`${id}: ${e.message}`);
      }
    }
    setApplying(null);
  }

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

      <div className="manager-tools">
        <button type="button" className="btn-secondary" disabled={checking || total < 2} onClick={runCheck}><GitCompare size={15} /> {checking ? "Checking overlaps…" : "Check overlaps across documents"}</button>
        <ReopenScope session={session} setSession={setSession} requirements={requirements} />
      </div>

      {checkError && <div className="error-banner" role="alert">{checkError}</div>}

      {session.consistency?.checked_at && (
        <section className={"consistency" + (session.consistency.issues.length ? "" : " clean")}>
          <div className="consistency-head">
            <GitCompare size={18} aria-hidden="true" />
            <div>
              <strong>{session.consistency.issues.length ? `${session.consistency.issues.length} issue${session.consistency.issues.length > 1 ? "s" : ""} across documents` : "No overlap or conflicts found"}</strong>
              {session.consistency.verdict && <p>{session.consistency.verdict}</p>}
            </div>
          </div>
          {session.consistency.issues.length > 0 && (
            <ol className="issue-list">
              {session.consistency.issues.map((it, i) => {
                const frozenIds = it.documents.filter((id) => requirements.find((r) => r.req_id === id && r.status === "Frozen"));
                return (
                  <li key={i}>
                    <div className="issue-docs">{it.documents.map((d) => <span key={d} className="req-id">{d}</span>)}</div>
                    <p className="issue-problem">{it.problem}</p>
                    {it.suggestion && <p className="issue-fix"><strong>Suggested fix:</strong> {it.suggestion}</p>}
                    <div className="requirement-actions">
                      {frozenIds.length > 0 && <span className="muted small">{frozenIds.join(", ")} frozen — unfreeze to include</span>}
                      <button className="btn-secondary sm" disabled={applying !== null || it.documents.length === frozenIds.length} onClick={() => applyIssue(it, i)}>
                        <Wand2 size={14} /> {applying === i ? "Applying…" : "Apply fix as revisions"}
                      </button>
                    </div>
                  </li>
                );
              })}
            </ol>
          )}
          <p className="muted small">If most issues are about modules doing the same job, redefining the modules is quicker than fixing documents one by one.</p>
        </section>
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

      {(session.requirement_archive || []).length > 0 && (
        <section className="archive">
          <button type="button" className="archive-toggle" onClick={() => setShowArchive((v) => !v)} aria-expanded={showArchive}>
            <Archive size={15} aria-hidden="true" /> {session.requirement_archive.length} archived set{session.requirement_archive.length > 1 ? "s" : ""} from earlier scope
            {showArchive ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
          </button>
          {showArchive && session.requirement_archive.map((a, i) => (
            <div key={i} className="archive-set">
              <p className="muted small">{new Date(a.archived_at).toLocaleString()} · {a.reason} · {a.modules.length} modules</p>
              <ul>{a.requirements.map((r) => <li key={r.req_id}><span className="req-id">{r.req_id}</span> {r.title} <span className="muted small">({r.status})</span></li>)}</ul>
            </div>
          ))}
        </section>
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
