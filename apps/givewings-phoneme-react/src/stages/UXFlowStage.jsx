// Stage 10 — UX Flow & Design Specification (2026-10-10). Freezes how people
// move through the UI/UX screens: journeys (trigger -> steps -> success),
// every screen's states, fixed wording, the navigation map and design tokens.
// Automatic freeze gates must pass before the baseline; the baseline closes the
// documentation stage and opens Ready to Build.
import { useEffect, useState } from "react";
import { CheckCircle2, CircleAlert, ExternalLink, Route, ShieldCheck } from "lucide-react";
import { api, fileUrl } from "../api.js";
import { GenerationBoard } from "./Generating.jsx";
import { BaselinePanel, ReviewCard, useStageDrafting } from "./ReviewKit.jsx";

function GatesPanel({ sid, refreshKey }) {
  const [rep, setRep] = useState(null);
  const [showAll, setShowAll] = useState(false);
  useEffect(() => { api.uxflow.gates(sid).then(setRep).catch(() => {}); }, [sid, refreshKey]);
  if (!rep) return null;
  const list = showAll ? rep.gates : rep.gates.filter((g) => !g.ok || g.detail.length);
  return (
    <section className={"gates-panel" + (rep.passed ? " done" : "")}>
      <div className="gates-head">
        <ShieldCheck size={20} aria-hidden="true" />
        <div>
          <strong>{rep.passed ? "All freeze gates passed" : `${rep.failed} freeze gate${rep.failed !== 1 ? "s" : ""} still open`}</strong>
          <p>{rep.passed
            ? "Every requirement has its journeys, every step is on a real screen and testable, nothing is a dead end, and every screen's states are defined. Freeze the flows and baseline to complete the documentation."
            : "GiveWings checks these automatically. The baseline unlocks when every required gate passes."}</p>
        </div>
        <button className="btn-secondary sm" onClick={() => setShowAll((v) => !v)}>{showAll ? "Show open only" : `Show all ${rep.gates.length}`}</button>
      </div>
      <ul className="gates-list">
        {list.map((g) => (
          <li key={g.key} className={g.ok ? "ok" : g.level === "must" ? "open" : "warn"}>
            {g.ok ? <CheckCircle2 size={16} aria-hidden="true" /> : <CircleAlert size={16} aria-hidden="true" />}
            <div>
              <strong>{g.label}</strong>{g.level !== "must" && <span className="chip">Advisory</span>}
              {g.detail.length > 0 && <ul>{g.detail.slice(0, 8).map((d, i) => <li key={i}>{d}</li>)}{g.detail.length > 8 && <li>… and {g.detail.length - 8} more</li>}</ul>}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

function FlowDocView({ doc }) {
  return (
    <div className="flow-doc">
      {doc.journeys.map((j) => (
        <section key={j.journey_id} className="flow-journey">
          <h4><Route size={15} aria-hidden="true" /> {j.title}</h4>
          <p className="muted small"><b>{j.persona || "User"}</b> · starts when {j.trigger || "—"} · ends when <b>{j.outcome || "—"}</b>
            {(j.entry_from || j.exits_to) && <> · {j.entry_from || "—"} → {j.exits_to || "—"}</>}</p>
          <table className="flow-table">
            <thead><tr><th>Step</th><th>Who · action</th><th>Screen</th><th>Product response</th><th>Acceptance criteria</th></tr></thead>
            <tbody>
              {j.steps.map((s) => (
                <tr key={s.step_id}>
                  <td className="mono">{s.step_id.split(".").slice(1).join(".")}</td>
                  <td><b>{s.actor}</b>: {s.action}</td>
                  <td>{s.screen}</td>
                  <td>{s.response}{s.background && <span className="muted"> · background: {s.background}</span>}{s.api && <code>{s.api}</code>}</td>
                  <td>{s.criteria.join(" ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ))}
      {doc.screen_states?.length > 0 && (
        <section>
          <h4>Screen states</h4>
          <table className="flow-table">
            <thead><tr><th>Screen</th><th>Empty</th><th>Loading</th><th>Error</th><th>Offline</th></tr></thead>
            <tbody>{doc.screen_states.map((x) => <tr key={x.screen}><td><b>{x.screen}</b></td><td>{x.empty}</td><td>{x.loading}</td><td>{x.error}</td><td>{x.offline}</td></tr>)}</tbody>
          </table>
        </section>
      )}
      {doc.microcopy?.length > 0 && <section><h4>Fixed wording</h4><ul className="research-bullet-list">{doc.microcopy.map((m, i) => <li key={i}>{m}</li>)}</ul></section>}
      {doc.notes?.length > 0 && <section><h4>Design decisions</h4><ul className="research-bullet-list">{doc.notes.map((m, i) => <li key={i}>{m}</li>)}</ul></section>}
    </div>
  );
}

export default function UXFlowStage({ session, setSession }) {
  const sid = session.session_id;
  const items = session.ux_flows || [];
  const uiBaselined = (session.baselines || []).some((b) => b.doc_type === "uiux");
  const [openIds, setOpenIds] = useState(() => new Set());
  const { error, running, retry } = useStageDrafting({ kind: "uxflow", session, setSession, items, gen: session.ux_generation, enabled: uiBaselined });
  const g = session.ux_generation;
  const toggle = (id) => setOpenIds((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });
  const refreshKey = JSON.stringify([items.map((i) => [i.status, i.doc && JSON.stringify(i.doc).length]), (session.baselines || []).length,
    (session.ui_modules || []).map((u) => u.status)]);
  const steps = items.reduce((n, i) => n + (i.doc?.journeys || []).reduce((k, j) => k + j.steps.length, 0), 0);
  if (!uiBaselined) return <div className="callout"><div><strong>Baseline the UI/UX screens first</strong><p>User flows are written over the frozen screens.</p></div></div>;
  return (
    <div className="review">
      {(running || g?.status === "failed" || items.some((i) => !i.doc)) && g?.items?.length > 0 && (
        <>
          <GenerationBoard generation={g} />
          {g.status === "failed" && <div className="requirement-actions"><button className="btn-primary" onClick={retry}>Retry failed modules</button></div>}
        </>
      )}
      {error && <div className="error-banner" role="alert">{error}</div>}
      <GatesPanel sid={sid} refreshKey={refreshKey} />
      <BaselinePanel label="UX Flow" nextLabel="Ready to Build" refreshKey={refreshKey}
        fetchStatus={() => api.uxflow.baseline(sid)} onBaseline={async () => setSession(await api.uxflow.createBaseline(sid))}
        downloads={[{ label: "UX Flow Spec (.docx)", href: fileUrl(`/uxflow/${sid}/export/uxs.docx`) },
                    { label: "Design tokens (.json)", href: fileUrl(`/uxflow/${sid}/export/tokens.json`) }]} />
      <p className="muted small">
        {items.length} module flows · {steps} journey steps, each traced to its requirement, screen and API.{" "}
        <a href={fileUrl(`/uxflow/${sid}/navmap.html`)} target="_blank" rel="noreferrer"><ExternalLink size={12} /> Navigation map</a>{" · "}
        <a href={fileUrl(`/uiux/${sid}/prototype`)} target="_blank" rel="noreferrer"><ExternalLink size={12} /> Clickable prototype</a>
      </p>
      <div className="requirement-feed">
        {items.map((f) => (
          <ReviewCard key={f.fl_id} kind="uxflow" sessionId={sid} item={f} itemId={f.fl_id} setSession={setSession}
            title={f.module} subtitle={`${f.req_id} → ${f.ui_id} → ${f.fl_id} · ${f.doc ? `${f.doc.journeys.length} journey${f.doc.journeys.length !== 1 ? "s" : ""}: ${f.doc.journeys.map((j) => j.title).join(", ")}` : "drafting…"}`}
            open={openIds.has(f.fl_id)} onToggle={() => toggle(f.fl_id)}
            renderDoc={(doc) => <FlowDocView doc={doc} />} />
        ))}
      </div>
    </div>
  );
}
