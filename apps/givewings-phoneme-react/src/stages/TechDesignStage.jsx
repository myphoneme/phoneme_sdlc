// Stage 8 — Technical Design (HLD/LLD). First the Technical Stack Charter is
// suggested by the AI and CONFIRMED by the owner (never assumed); then the
// HLD and one LLD per BRD/PRD module are drafted, reviewed and frozen.
import { useEffect, useState } from "react";
import { AlertTriangle, Boxes, CheckCircle2, ChevronDown, ChevronRight, Cpu, Database, PenLine, Save, Sparkles } from "lucide-react";
import { api, fileUrl } from "../api.js";
import { GenerationBoard } from "./Generating.jsx";
import { BaselinePanel, ReviewCard, useStageDrafting } from "./ReviewKit.jsx";

export const STACK_FIELDS = [
  ["product_type", "Product type", "SaaS web app, mobile app, internal tool…"],
  ["frontend", "Frontend", "Framework, styling, hosting of the web/mobile app"],
  ["backend", "Backend", "Language/framework, API style, auth approach"],
  ["data", "Data", "Main database, cache, file/blob storage"],
  ["ai_ml", "AI / ML components", "Which features use AI, which provider, human review"],
  ["hosting", "Hosting & infra", "Cloud or data centre, region, environments, domains"],
  ["integrations", "Third-party integrations", "Messaging, email, social platforms, payments, sign-in providers"],
  ["devops", "DevOps & CI/CD", "Repo, branching, CI pipeline, deployment"],
  ["security", "Security & compliance", "Data residency, PII handling, applicable law (e.g. DPDP Act 2023)"],
  ["conventions", "Coding conventions", "Folder structure, naming, lint/format tools"],
];

function StackCharterForm({ session, setSession, onDone }) {
  const sid = session.session_id;
  const [form, setForm] = useState(() => ({ ...(session.stack || {}) }));
  const [busy, setBusy] = useState("");
  const [error, setError] = useState(null);
  const confirmed = !!session.stack?.confirmed;
  useEffect(() => { setForm((f) => ({ ...(session.stack || {}), ...Object.fromEntries(Object.entries(f).filter(([, v]) => v)) })); }, [session.stack]);
  useEffect(() => {
    if (!session.stack && !confirmed) suggest();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function run(label, fn) {
    setBusy(label); setError(null);
    try { const s = await fn(); setSession(s); return s; } catch (e) { setError(e.message); return null; } finally { setBusy(""); }
  }
  const suggest = () => run("GiveWings AI is proposing a stack…", () => api.suggestStack(sid));
  const save = () => run("Saving…", () => api.saveStack(sid, form));
  const confirm = async () => {
    if (await run("Saving…", () => api.saveStack(sid, form)) && await run("Confirming…", () => api.confirmStack(sid))) onDone?.();
  };
  const tbd = STACK_FIELDS.filter(([k]) => (form[k] || "").toLowerCase().includes("tbd"));
  return (
    <section className="stack-form">
      <div className="callout">
        <Cpu size={20} aria-hidden="true" />
        <div>
          <strong>Technical Stack Charter</strong>
          <p>The technology decisions every design section and all future code will follow. GiveWings AI proposes sensible choices — edit anything, decide every item marked <b>TBD</b>, then confirm. Changes after confirmation are recorded in the charter's change log.</p>
        </div>
      </div>
      {busy && <div className="working inline" role="status"><span className="spinner sm" aria-hidden="true" /><span>{busy}</span></div>}
      <div className="stack-grid">
        {STACK_FIELDS.map(([k, label, hint]) => {
          const isTbd = (form[k] || "").toLowerCase().includes("tbd");
          return (
            <label key={k} className={"stack-field" + (isTbd ? " tbd" : "")}>
              <span>{label}{isTbd && <em> · decision needed</em>}</span>
              <textarea rows={3} value={form[k] || ""} placeholder={hint} disabled={!!busy} onChange={(e) => setForm((f) => ({ ...f, [k]: e.target.value }))} />
            </label>
          );
        })}
      </div>
      {tbd.length > 0 && <div className="callout warn-callout"><AlertTriangle size={18} aria-hidden="true" /><div><strong>{tbd.length} item{tbd.length === 1 ? "" : "s"} still marked TBD</strong><p>{tbd.map(([, l]) => l).join(", ")} — replace “TBD” with the decision before confirming.</p></div></div>}
      {session.stack?.changelog?.length > 0 && <p className="muted small">Charter log: {session.stack.changelog.join(" · ")}</p>}
      {error && <div className="error-banner" role="alert">{error}</div>}
      <div className="requirement-actions">
        <button className="btn-secondary" disabled={!!busy} onClick={suggest}><Sparkles size={14} /> Suggest empty fields with AI</button>
        <button className="btn-secondary" disabled={!!busy} onClick={save}><Save size={14} /> Save draft</button>
        <button className="btn-primary" disabled={!!busy || tbd.length > 0} onClick={confirm}><CheckCircle2 size={14} /> {confirmed ? "Save charter" : "Confirm charter & draft the design"}</button>
      </div>
    </section>
  );
}

const M = { GET: "get", POST: "post", PUT: "put", PATCH: "patch", DELETE: "del" };

export function TechDocView({ doc }) {
  return (
    <div className="req-doc td-doc">
      {doc.overview && <p className="req-summary">{doc.overview}</p>}
      {doc.components?.length > 0 && (
        <section className="req-sec"><h4 className="req-sec-title"><Boxes size={15} aria-hidden="true" /> Components</h4>
          <ul className="td-comp">{doc.components.map((c) => <li key={c.name}><b>{c.name}</b><span>{c.responsibility}</span></li>)}</ul></section>
      )}
      {doc.data_model?.length > 0 && (
        <section className="req-sec"><h4 className="req-sec-title"><Database size={15} aria-hidden="true" /> Data model</h4>
          <div className="td-entities">{doc.data_model.map((e) => (
            <div key={e.name} className="td-entity"><strong>{e.name}</strong>{e.description && <small>{e.description}</small>}
              <table className="research-table"><thead><tr><th>Field</th><th>Type</th><th>Notes</th></tr></thead>
                <tbody>{e.fields.map((f) => <tr key={f.name}><td className="mono">{f.name}</td><td className="mono">{f.type}</td><td>{f.notes}</td></tr>)}</tbody></table></div>
          ))}</div></section>
      )}
      {doc.apis?.length > 0 && (
        <section className="req-sec"><h4 className="req-sec-title">API contracts</h4>
          <div className="research-table-wrap"><table className="research-table td-api"><thead><tr><th>Endpoint</th><th>Purpose</th><th>Request</th><th>Response</th></tr></thead>
            <tbody>{doc.apis.map((a, i) => <tr key={i}><td><span className={`http ${M[a.method] || "get"}`}>{a.method}</span> <span className="mono">{a.path}</span></td><td>{a.purpose}</td><td>{a.request}</td><td>{a.response}</td></tr>)}</tbody></table></div></section>
      )}
      {doc.sequence?.length > 0 && (
        <section className="req-sec"><h4 className="req-sec-title">Key sequence flow</h4><ol className="flow-step-list">{doc.sequence.map((s, i) => <li key={i}>{s}</li>)}</ol></section>
      )}
      {[["Edge cases & error handling", doc.edge_cases], ["Integrations", doc.integrations], ["Security", doc.security], ["Risks", doc.risks]].map(([t, list]) => list?.length > 0 && (
        <section key={t} className="req-sec"><h4 className="req-sec-title">{t}</h4><ul className="research-bullet-list">{list.map((x, i) => <li key={i}>{x}</li>)}</ul></section>
      ))}
      {doc.nfr?.length > 0 && (
        <section className="req-sec"><h4 className="req-sec-title">Non-functional design</h4>
          <table className="research-table"><thead><tr><th>Requirement</th><th>How it is achieved</th></tr></thead><tbody>{doc.nfr.map((n, i) => <tr key={i}><td>{n.requirement}</td><td>{n.approach}</td></tr>)}</tbody></table></section>
      )}
    </div>
  );
}

export function StackSummary({ stack, onEdit }) {
  const [open, setOpen] = useState(false);
  if (!stack) return null;
  return (
    <section className="stack-summary">
      <button type="button" className="link-btn" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />} <Cpu size={14} aria-hidden="true" /> Technical Stack Charter {stack.confirmed ? "· confirmed" : "· draft"}
      </button>
      {open && (
        <>
          <dl className="brief-dl">{STACK_FIELDS.map(([k, l]) => stack[k] ? <div key={k}><dt>{l}</dt><dd>{stack[k]}</dd></div> : null)}</dl>
          {onEdit && <button className="btn-secondary sm" onClick={onEdit}><PenLine size={13} /> Edit charter</button>}
        </>
      )}
    </section>
  );
}

export default function TechDesignStage({ session, setSession }) {
  const sid = session.session_id;
  const [editStack, setEditStack] = useState(false);
  const [openIds, setOpenIds] = useState(() => new Set());
  const items = session.tech_designs || [];
  const confirmed = !!session.stack?.confirmed;
  const { error, running, retry } = useStageDrafting({ kind: "techdesign", session, setSession, items, gen: session.tech_generation, enabled: confirmed && !editStack });
  if (!confirmed || editStack) return <StackCharterForm session={session} setSession={setSession} onDone={() => setEditStack(false)} />;
  const g = session.tech_generation;
  const toggle = (id) => setOpenIds((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });
  const frozen = items.filter((i) => i.status === "Frozen").length;
  return (
    <div className="review">
      <StackSummary stack={session.stack} onEdit={() => setEditStack(true)} />
      {(running || g?.status === "failed" || items.some((i) => !i.doc)) && g?.items?.length > 0 && (
        <>
          <GenerationBoard generation={g} />
          {g.status === "failed" && <div className="requirement-actions"><button className="btn-primary" onClick={retry}>Retry failed documents</button></div>}
        </>
      )}
      {error && <div className="error-banner" role="alert">{error}</div>}
      <BaselinePanel label="Technical Design" nextLabel="UI/UX" refreshKey={items.map((i) => i.status).join()}
        fetchStatus={() => api.techdesign.baseline(sid)} onBaseline={async () => setSession(await api.techdesign.createBaseline(sid))}
        downloads={[{ label: "Technical Design (.docx)", href: fileUrl(`/techdesign/${sid}/export/techdesign.docx`) },
          { label: "Stack charter (.md)", href: fileUrl(`/techdesign/${sid}/export/stack.md`) }]} />
      {items.length > 0 && <p className="muted small">{frozen} of {items.length} documents frozen. Each LLD is numbered to match its BRD/PRD module.</p>}
      <div className="requirement-feed">
        {items.map((t) => (
          <ReviewCard key={t.td_id} kind="techdesign" sessionId={sid} item={t} itemId={t.td_id} setSession={setSession}
            title={t.kind === "hld" ? "System architecture (HLD)" : t.module}
            subtitle={t.kind === "hld" ? "Architecture, integrations, security, non-functional design" : `Implements ${t.req_id} · ${t.doc ? `${t.doc.apis.length} APIs · ${t.doc.data_model.length} entities` : "drafting…"}`}
            open={openIds.has(t.td_id)} onToggle={() => toggle(t.td_id)}
            renderDoc={(doc) => <TechDocView doc={doc} />} />
        ))}
      </div>
    </div>
  );
}
