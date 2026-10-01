import { Boxes, Link2, Sparkles } from "lucide-react";
import { FlowStepText } from "./RequirementDoc.jsx";
import { ResearchReportView } from "./ResearchCard.jsx";
import { IdentitySummary } from "./IdentityStudio.jsx";
import { GenerationBoard } from "./Generating.jsx";
import ReopenScope from "./ReopenScope.jsx";

const BRIEF_FIELDS = [
  ["target_users", "Target users"], ["core_workflow", "Core workflow"], ["input_channels", "Input channels"],
  ["privacy_mode", "Privacy & visibility"], ["market", "Launch market"], ["platforms", "Launch platforms"],
];

function Empty({ children }) {
  return <p className="muted">{children}</p>;
}

function DiscoveryReview({ session }) {
  const b = session.concept_brief;
  return (
    <div className="review-stack">
      {b ? (
        <section className="review-section">
          <h3>Confirmed concept</h3>
          <p className="lead">{b.summary}</p>
          <dl className="brief-dl">
            {BRIEF_FIELDS.map(([k, label]) => b[k] ? <div key={k}><dt>{label}</dt><dd>{b[k]}</dd></div> : null)}
            {b.must_haves?.length > 0 && <div><dt>Must-haves</dt><dd>{b.must_haves.join(" · ")}</dd></div>}
            {b.out_of_scope?.length > 0 && <div><dt>Out of scope</dt><dd>{b.out_of_scope.join(" · ")}</dd></div>}
          </dl>
        </section>
      ) : session.concept_summary ? (
        <section className="review-section"><h3>Concept summary</h3><p className="lead">{session.concept_summary}</p>
          <p className="muted small">This idea was scoped before the confirm-your-concept step existed.</p></section>
      ) : null}
      <section className="review-section">
        <h3>Conversation</h3>
        <div className="chat-log static">
          {(session.messages || []).map((m, i) => (
            <div key={i} className={"msg " + (m.role === "user" ? "user" : "bot")}>
              {m.role === "user" ? <span className="msg-avatar user" aria-hidden="true">YOU</span> : <span className="msg-avatar bot" aria-hidden="true"><Sparkles size={16} /></span>}
              <div className="msg-body">
                <span className="msg-author">{m.role === "user" ? "You" : "GiveWings AI"}</span>
                <div className="msg-bubble">{m.text}</div>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function IdentityReview({ session }) {
  const b = session.brand || {};
  const domains = b.domains || [];
  return (
    <div className="review-stack">
      {session.selected_name ? <IdentitySummary session={session} /> : <Empty>No identity recorded.</Empty>}
      {!b.completed && session.selected_theme && !b.palette && (
        <p className="muted small">This idea chose its theme (“{session.selected_theme}”) before the Identity studio existed — no domain, tagline or logo was captured.</p>
      )}
      {domains.length > 0 && (
        <section className="review-section">
          <h3>Domain check for “{b.domain_checked_name}”</h3>
          <div className="domain-grid">
            <div>{domains.map((d) => (
              <div key={d.domain} className={`domain-row ${d.status}`}>
                <span className="domain-name">{d.domain}</span>
                <span className={`domain-badge ${d.status}`}>{d.status === "available" ? "Available" : d.status === "taken" ? "Taken" : "Couldn't verify"}</span>
              </div>
            ))}</div>
          </div>
        </section>
      )}
    </div>
  );
}

function ScopeReview({ session, setSession, requirements }) {
  const specs = session.module_specs?.length
    ? session.module_specs
    : (session.modules || []).map((m) => ({ name: m, description: "", platform_core: m.toLowerCase().startsWith("platform-core") }));
  if (!specs.length) return <Empty>No modules recorded.</Empty>;
  return (
    <div className="review-stack">
    <div className="scope-review-bar">
      <span className="muted">{specs.filter((m) => !m.platform_core).length} product modules were frozen. Too many, or overlapping?</span>
      <ReopenScope session={session} setSession={setSession} requirements={requirements} />
    </div>
    <ol className="module-grid review">
      {specs.map((m, i) => (
        <li key={i} className={"module-tile" + (m.platform_core ? " core" : "")}>
          <span className="module-icon" aria-hidden="true">{m.platform_core ? <Link2 size={16} /> : <Boxes size={16} />}</span>
          <span className="module-name">{m.name}{m.description && <small>{m.description}</small>}</span>
          {m.platform_core && <span className="chip">Platform-Core</span>}
        </li>
      ))}
    </ol>
    </div>
  );
}

function FlowReview({ session }) {
  const flows = session.module_flows || [];
  if (!flows.length) return <Empty>No flows recorded.</Empty>;
  return (
    <div className="requirement-feed">
      {flows.map((f) => (
        <div key={f.module} className="requirement-card">
          <div className="requirement-header">
            <span className="req-title">{f.module}</span>
            <span className="req-count">{f.steps.length} steps</span>
            <span className={f.status === "Approved" ? "chip good" : "chip"}>{f.status}</span>
          </div>
          <ol className="flow-step-list">{f.steps.map((s, i) => <li key={i}><FlowStepText text={s} /></li>)}</ol>
        </div>
      ))}
    </div>
  );
}

function GenerationReview({ session, requirements }) {
  if (session.generation?.items?.length) return <GenerationBoard generation={session.generation} showErrors={false} />;
  return (
    <div className="review-stack">
      <p className="muted">This idea was drafted before live progress tracking existed. {requirements.length} requirement document{requirements.length === 1 ? " was" : "s were"} produced:</p>
      <ul className="module-grid">
        {[...requirements].sort((a, b) => a.req_id.localeCompare(b.req_id)).map((r) => (
          <li key={r.req_id} className="module-tile"><span className="req-id">{r.req_id}</span><span className="module-name">{r.title}</span></li>
        ))}
      </ul>
    </div>
  );
}

export default function StageReview({ stage, session, setSession, requirements }) {
  if (stage === "discovery") return <DiscoveryReview session={session} />;
  if (stage === "research") return session.research ? <ResearchReportView research={session.research} /> : <Empty>No research recorded.</Empty>;
  if (stage === "identity") return <IdentityReview session={session} />;
  if (stage === "freeze") return <ScopeReview session={session} setSession={setSession} requirements={requirements} />;
  if (stage === "flow") return <FlowReview session={session} />;
  if (stage === "generating") return <GenerationReview session={session} requirements={requirements} />;
  return <Empty>Nothing to review here yet.</Empty>;
}
