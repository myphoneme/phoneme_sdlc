// Shared review UI for the stages after the BRD/PRD (Technical Design, UI/UX).
// Same rules the BRD/PRD Manager established: comment -> proposed revision
// (accept / discard), open questions must be answered or deferred before
// Approve/Freeze, and a frozen set is baselined as a version.
import { useEffect, useState } from "react";
import { CheckCircle2, ChevronDown, ChevronRight, CircleHelp, Clock, Download, Flag, Lock, LockOpen, MessagesSquare, Send, Sparkles } from "lucide-react";
import { api } from "../api.js";

export function statusClass(status) {
  if (status === "Approved" || status === "Frozen") return "chip good";
  if (status?.startsWith("Revised")) return "chip warn";
  return "chip";
}

function persisted(key, initial) {
  try { const v = localStorage.getItem(key); return v ? JSON.parse(v) : initial; } catch { return initial; }
}
function persist(key, value) {
  try { if (value === null) localStorage.removeItem(key); else localStorage.setItem(key, JSON.stringify(value)); } catch { /* storage unavailable */ }
}

export function OpenQuestionsPanel({ questions, storageKey, busy, onSubmit }) {
  const [ans, setAnsState] = useState(() => persisted(storageKey, {}));
  const setAns = (q, patch) => setAnsState((a) => {
    const n = { ...a, [q]: { answer: "", defer: false, ...a[q], ...patch } };
    persist(storageKey, n);
    return n;
  });
  const ready = questions.filter((q) => ans[q]?.defer || ans[q]?.answer?.trim());
  const submit = async () => {
    const payload = ready.map((q) => ({ question: q, answer: (ans[q]?.answer || "").trim(), defer: !!ans[q]?.defer }));
    if (await onSubmit(payload)) { persist(storageKey, null); setAnsState({}); }
  };
  return (
    <section className="oq-panel" aria-label="Open questions">
      <div className="oq-head">
        <CircleHelp size={18} aria-hidden="true" />
        <div>
          <strong>{questions.length} open question{questions.length === 1 ? "" : "s"} need{questions.length === 1 ? "s" : ""} a decision</strong>
          <p>Answer each one, or choose <b>Decide later</b> to record it as deferred. The document is updated with your answers; it can be approved once nothing is open.</p>
        </div>
      </div>
      <ol className="oq-list">
        {questions.map((q, i) => {
          const a = ans[q] || {};
          return (
            <li key={q} className={a.defer ? "deferred" : a.answer?.trim() ? "answered" : ""}>
              <p className="oq-q"><b>Q{i + 1}.</b> {q}</p>
              <textarea rows={2} value={a.answer || ""} disabled={!!busy} aria-label={`Answer to question ${i + 1}`}
                placeholder={a.defer ? "Why it can wait (optional)" : "Your answer…"} onChange={(e) => setAns(q, { answer: e.target.value })} />
              <label className="oq-defer">
                <input type="checkbox" checked={!!a.defer} disabled={!!busy} onChange={(e) => setAns(q, { defer: e.target.checked })} />
                <Clock size={13} aria-hidden="true" /> Decide later (record as deferred)
              </label>
            </li>
          );
        })}
      </ol>
      <div className="requirement-actions">
        <span className="muted small" style={{ flex: 1 }}>{ready.length} of {questions.length} ready</span>
        <button className="btn-primary" disabled={!!busy || ready.length === 0} onClick={submit}><Send size={14} /> {busy ? "Updating…" : `Submit ${ready.length || ""} answer${ready.length === 1 ? "" : "s"}`}</button>
      </div>
    </section>
  );
}

export function ThreadPanel({ thread = [], decisions = [] }) {
  const [open, setOpen] = useState(false);
  if (!thread.length && !decisions.length) return null;
  return (
    <section className="review-thread">
      <button type="button" className="link-btn" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />} <MessagesSquare size={14} aria-hidden="true" /> Review conversation &amp; decisions ({decisions.length} decision{decisions.length === 1 ? "" : "s"})
      </button>
      {open && (
        <>
          {decisions.length > 0 && (
            <ul className="decision-log">
              {decisions.map((d, i) => (
                <li key={i}>
                  {d.deferred ? <Clock size={14} aria-hidden="true" /> : <CheckCircle2 size={14} aria-hidden="true" />}
                  <div><b>{d.question}</b><span>{d.deferred ? `Deferred${d.answer ? ` — ${d.answer}` : ""}` : d.answer}</span></div>
                </li>
              ))}
            </ul>
          )}
          <div className="chat-log static thread-log">
            {thread.map((m, i) => (
              <div key={i} className={"msg " + (m.role === "owner" ? "user" : "bot")}>
                {m.role === "owner" ? <span className="msg-avatar user" aria-hidden="true">YOU</span> : <span className="msg-avatar bot" aria-hidden="true"><Sparkles size={16} /></span>}
                <div className="msg-body">
                  <span className="msg-author">{m.role === "owner" ? "Product owner" : "GiveWings AI"}</span>
                  <div className="msg-bubble">{m.text}</div>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </section>
  );
}

// One reviewable document: header, body (rendered by the stage), proposed
// revision, open questions, conversation, comment box and actions.
export function ReviewCard({ kind, sessionId, item, itemId, title, subtitle, setSession, renderDoc, open, onToggle, peek }) {
  const stage = api[kind];
  const draftKey = `gw_${kind}_comment_${sessionId}_${itemId}`;
  const [comment, setCommentState] = useState(() => persisted(draftKey, ""));
  const setComment = (v) => { setCommentState(v); persist(draftKey, v.trim() ? v : null); };
  const [busy, setBusy] = useState("");
  const [error, setError] = useState(null);
  const pending = !!item.revised_doc;
  const questions = item.doc?.open_questions || [];
  const needsAnswers = questions.length > 0 && !pending && item.status !== "Frozen";

  async function act(label, fn) {
    setBusy(label);
    setError(null);
    try { setSession(await fn()); return true; } catch (e) { setError(e.message); return false; } finally { setBusy(""); }
  }
  const submitComment = async () => {
    if (comment.trim() && await act("Applying your comment…", () => stage.comment(sessionId, itemId, comment.trim()))) setComment("");
  };

  return (
    <article className={"requirement-card doc-card" + (item.status === "Frozen" ? " frozen" : "") + (open ? " open" : "")}>
      <button type="button" className="doc-head" onClick={onToggle} aria-expanded={open}>
        {open ? <ChevronDown size={18} aria-hidden="true" /> : <ChevronRight size={18} aria-hidden="true" />}
        <span className="req-id">{itemId}</span>
        <span className="doc-title"><strong>{title}</strong><small>{subtitle}</small></span>
        {questions.length > 0 && item.status !== "Frozen" && <span className="chip warn">{questions.length} open question{questions.length === 1 ? "" : "s"}</span>}
        {item.status === "Frozen" && <Lock size={14} aria-hidden="true" className="frozen-lock" />}
        <span className={statusClass(item.status)}>{item.doc ? item.status : "Not drafted"}</span>
      </button>
      {!open && peek}
      {open && (
        <div className="doc-body">
          {item.doc ? renderDoc(item.doc, false) : <p className="muted">Not drafted yet.</p>}
          {pending && (
            <div className="diff-block">
              <div className="diff-label"><Sparkles size={13} aria-hidden="true" /> Revised with your comment — review, then Accept to update the document</div>
              {renderDoc(item.revised_doc, true)}
              <div className="requirement-actions">
                <button className="btn-secondary" disabled={!!busy} onClick={() => act("Discarding…", () => stage.discard(sessionId, itemId))}>Discard</button>
                <button className="btn-primary" disabled={!!busy} onClick={() => act("Accepting…", () => stage.accept(sessionId, itemId))}>Accept revision</button>
              </div>
            </div>
          )}
          {needsAnswers && (
            <OpenQuestionsPanel questions={questions} storageKey={`gw_${kind}_answers_${sessionId}_${itemId}`} busy={busy}
              onSubmit={(answers) => act("Updating the document with your answers…", () => stage.answers(sessionId, itemId, answers))} />
          )}
          {busy && <div className="working inline" role="status"><span className="spinner sm" aria-hidden="true" /><span>{busy}</span></div>}
          <ThreadPanel thread={item.thread} decisions={item.decisions} />
          {item.doc && !pending && item.status !== "Frozen" && (
            <div className="comment-row">
              <textarea className="chat-textarea" rows={2} value={comment} disabled={!!busy} onChange={(e) => setComment(e.target.value)}
                placeholder="Request a change in plain words, then click Apply comment. (Shift+Enter for a new line)"
                onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); if (!busy && comment.trim()) submitComment(); } }} />
              <div className="requirement-actions">
                {comment.trim() ? (
                  <>
                    <span className="muted small comment-hint">Apply your comment first — approving or freezing ignores unsent comments.</span>
                    <button className="btn-secondary" disabled={!!busy} onClick={() => setComment("")}>Clear</button>
                    <button className="btn-primary" disabled={!!busy} onClick={submitComment}><Sparkles size={14} /> Apply comment</button>
                  </>
                ) : questions.length > 0 ? (
                  <span className="muted small comment-hint">Answer or defer the open question{questions.length === 1 ? "" : "s"} above to approve this document.</span>
                ) : item.status === "Approved" ? (
                  <button className="btn-primary" disabled={!!busy} onClick={() => act("Freezing…", () => stage.freeze(sessionId, itemId))}><Lock size={14} /> Freeze</button>
                ) : (
                  <button className="btn-primary" disabled={!!busy} onClick={() => act("Approving…", () => stage.accept(sessionId, itemId))}>Approve</button>
                )}
              </div>
            </div>
          )}
          {item.status === "Frozen" && (
            <div className="requirement-actions">
              <span className="muted small">Frozen — part of the baseline.</span>
              <button className="btn-secondary" disabled={!!busy} onClick={() => act("Unfreezing…", () => stage.unfreeze(sessionId, itemId))}><LockOpen size={14} /> Unfreeze to change</button>
            </div>
          )}
          {error && <div className="error-banner" role="alert">{error}</div>}
        </div>
      )}
    </article>
  );
}

// Baseline + downloads. `fetchStatus` returns {all_frozen, version, changed_since, next_version}.
export function BaselinePanel({ label, nextLabel, fetchStatus, onBaseline, downloads = [], refreshKey }) {
  const [st, setSt] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  useEffect(() => { fetchStatus().then(setSt).catch(() => {}); }, [refreshKey]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!st) return null;
  const changed = st.version && st.changed_since.length > 0;
  const canBaseline = st.all_frozen && (!st.version || changed);
  const run = async () => {
    setBusy(true); setError(null);
    try { await onBaseline(); setSt(await fetchStatus()); } catch (e) { setError(e.message); } finally { setBusy(false); }
  };
  return (
    <section className={"baseline-panel" + (st.version && !changed ? " done" : "")}>
      <div className="baseline-copy">
        <Flag size={20} aria-hidden="true" />
        <div>
          {st.version && !changed ? (
            <><strong>{label} baselined as v{st.version}</strong><p>This version is locked and feeds {nextLabel}. Unfreezing and changing a document makes it v{st.next_version}.</p></>
          ) : changed ? (
            <><strong>Changes since v{st.version}: {st.changed_since.join(", ")}</strong><p>{st.all_frozen ? `Baseline them as v${st.next_version} — it is added to the document's Change Log.` : "Freeze the changed documents, then baseline the new version."}</p></>
          ) : st.all_frozen ? (
            <><strong>Every {label} document is frozen</strong><p>Baseline it as v{st.next_version} to lock this version and continue to {nextLabel}.</p></>
          ) : (
            <><strong>{label} not yet baselined</strong><p>Freeze every document to baseline v{st.next_version}. You can download a draft at any time.</p></>
          )}
        </div>
      </div>
      <div className="baseline-actions">
        {downloads.map((d) => <a key={d.href} className="btn-secondary" href={d.href} download><Download size={15} /> {d.label}</a>)}
        {canBaseline && <button className="btn-primary" disabled={busy} onClick={run}><Flag size={15} /> {busy ? "Baselining…" : `Baseline v${st.next_version}${st.version ? "" : ` & continue to ${nextLabel}`}`}</button>}
      </div>
      {error && <div className="error-banner" role="alert">{error}</div>}
    </section>
  );
}

// Background drafting with live progress, shared by both stages.
export function useStageDrafting({ kind, session, setSession, items, gen, enabled = true }) {
  const [error, setError] = useState(null);
  const running = gen?.status === "running";
  const undrafted = items.length === 0 || items.some((i) => !i.doc);
  useEffect(() => {
    if (!enabled || !session || running || !undrafted || gen?.status === "failed") return;
    api[kind].generate(session.session_id).then(setSession).catch((e) => setError(e.message));
  }, [session?.session_id, enabled]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!running) return undefined;
    const t = setInterval(() => { api.getSession(session.session_id).then(setSession).catch(() => {}); }, 2500);
    return () => clearInterval(t);
  }, [running, session?.session_id]); // eslint-disable-line react-hooks/exhaustive-deps
  const retry = () => api[kind].generate(session.session_id).then(setSession).catch((e) => setError(e.message));
  return { error, running, retry };
}
