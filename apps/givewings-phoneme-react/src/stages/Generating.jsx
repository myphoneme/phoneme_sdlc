import { useEffect, useRef, useState } from "react";
import { ArrowRight, Check, CircleAlert, Clock, FileText, RotateCcw, ShieldCheck } from "lucide-react";
import { STANDARD_NAMES } from "../standard.js";
import { api } from "../api.js";

const POLL_MS = 3000;

export function GenerationBoard({ generation, showErrors = true }) {
  const g = generation || { items: [], total: 0, done: 0, status: "idle" };
  const failed = g.items.filter((i) => i.status === "failed").length;
  const drafting = g.items.find((i) => i.status === "drafting");
  const left = g.total - g.done - failed;
  const pct = g.total ? Math.round((g.done / g.total) * 100) : 0;
  return (
    <div className="gen-board">
      <div className="gen-stats">
        <div className="gen-stat"><span>Documents</span><strong>{g.total}</strong></div>
        <div className="gen-stat good"><span>Completed</span><strong>{g.done}</strong></div>
        <div className="gen-stat"><span>Remaining</span><strong>{Math.max(0, left)}</strong></div>
        {failed > 0 && <div className="gen-stat bad"><span>Failed</span><strong>{failed}</strong></div>}
      </div>
      <div className="gen-meter" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct} aria-label="Drafting progress">
        <i style={{ width: `${pct}%` }} />
      </div>
      <p className="muted small">
        {g.status === "done" ? "All documents drafted." : drafting ? <>Now drafting <strong>{drafting.req_id}</strong> — {drafting.module}</> : g.status === "failed" ? "Some documents failed — retry them below." : "Queued…"}
        {" "}· {pct}% complete
      </p>
      <ol className="gen-list">
        {g.items.map((it) => {
          const core = STANDARD_NAMES.has(it.module) || it.module.toLowerCase().startsWith("platform-core");
          return (
            <li key={it.module} className={`gen-item ${it.status}`}>
              <span className="gen-icon" aria-hidden="true">
                {it.status === "done" ? <Check size={14} strokeWidth={3} /> : it.status === "drafting" ? <span className="spinner sm" /> : it.status === "failed" ? <CircleAlert size={15} /> : <Clock size={14} />}
              </span>
              <span className="req-id">{it.req_id}</span>
              <span className="gen-module">{core ? <ShieldCheck size={13} aria-hidden="true" /> : <FileText size={13} aria-hidden="true" />} {it.module}{STANDARD_NAMES.has(it.module) && <span className="chip std-mini">Standard</span>}</span>
              <span className={`gen-status ${it.status}`}>{{ done: "Drafted", drafting: "Drafting…", failed: "Failed", queued: "Queued", skipped: "Skipped" }[it.status] || it.status}</span>
              {showErrors && it.error && <span className="gen-error">{it.error}</span>}
            </li>
          );
        })}
      </ol>
    </div>
  );
}

export default function Generating({ session, setSession, setRequirements }) {
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const started = useRef(false);
  const g = session.generation || {};

  // Start (idempotent on the server — a second tab or a refresh just
  // re-attaches to the run already in progress).
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    if (g.status !== "running" && g.status !== "done") {
      api.generate(session.session_id).then(setSession).catch((e) => setError(e.message));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Poll live progress until the run finishes.
  useEffect(() => {
    if (g.status === "done" || g.status === "failed") return undefined;
    const t = setInterval(async () => {
      try {
        const s = await api.getSession(session.session_id);
        setSession(s);
        if (s.generation?.status === "done" || s.stage === "manager") {
          setRequirements(await api.listRequirements(session.session_id));
        }
      } catch {
        /* transient — keep polling */
      }
    }, POLL_MS);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [g.status]);

  async function retry() {
    setBusy(true);
    setError(null);
    try {
      setSession(await api.retryGenerate(session.session_id));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function openManager() {
    setRequirements(await api.listRequirements(session.session_id));
    setSession({ ...session, stage: "manager" });
  }

  return (
    <div className="generating">
      {error && <div className="error-banner" role="alert">{error}</div>}
      <GenerationBoard generation={g} />
      {g.status === "failed" && (
        <div className="sticky-actions">
          <span className="muted">The drafted documents are saved. Retry only re-runs the failed ones.</span>
          <button className="btn-primary" disabled={busy} onClick={retry}><RotateCcw size={15} /> Retry failed</button>
        </div>
      )}
      {g.status === "done" && session.stage !== "manager" && (
        <div className="sticky-actions">
          <span className="muted">All {g.total} documents drafted.</span>
          <button className="btn-primary" onClick={openManager}>Open BRD/PRD Manager <ArrowRight size={16} /></button>
        </div>
      )}
    </div>
  );
}
