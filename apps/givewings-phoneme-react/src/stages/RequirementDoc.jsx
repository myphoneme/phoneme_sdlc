import { ArrowRight, CircleHelp, ListChecks, Scale, Users, XCircle } from "lucide-react";

// Highlight the Given / When / Then keywords so each criterion scans as a test.
function Gwt({ text }) {
  const parts = text.split(/\b(Given|When|Then|And)\b/);
  return <>{parts.map((p, i) => (/^(Given|When|Then|And)$/.test(p) ? <strong key={i} className="gwt">{p}</strong> : <span key={i}>{p}</span>))}</>;
}

const actorTone = (actor, actors) => {
  const i = Math.max(0, actors.indexOf(actor));
  return ["a0", "a1", "a2", "a3"][i % 4];
};

export function FlowStrip({ journey }) {
  if (!journey?.length) return null;
  return (
    <ol className="flow-strip" aria-label="Flow at a glance">
      {journey.map((s, i) => (
        <li key={i}>
          <span className="flow-chip"><b>{i + 1}</b>{s.title}</span>
          {i < journey.length - 1 && <ArrowRight size={14} aria-hidden="true" className="flow-arrow" />}
        </li>
      ))}
    </ol>
  );
}

export default function RequirementDoc({ doc, compact = false }) {
  const actors = doc.actors || [];
  return (
    <div className={"req-doc" + (compact ? " compact" : "")}>
      {doc.summary && <p className="req-summary">{doc.summary}</p>}

      {actors.length > 0 && (
        <div className="req-actors">
          <span className="req-sec-label"><Users size={14} aria-hidden="true" /> Who's involved</span>
          {actors.map((a) => <span key={a} className={`actor-chip ${actorTone(a, actors)}`}>{a}</span>)}
        </div>
      )}

      {(doc.receives_from || doc.hands_off_to) && (
        <div className="handoffs">
          {doc.receives_from && <div><span>Receives from</span><p>{doc.receives_from}</p></div>}
          {doc.hands_off_to && <div><span>Hands off to</span><p>{doc.hands_off_to}</p></div>}
        </div>
      )}

      {doc.journey?.length > 0 && (
        <section className="req-sec">
          <h4 className="req-sec-title">How it works</h4>
          <FlowStrip journey={doc.journey} />
          <ol className="journey-list">
            {doc.journey.map((s, i) => (
              <li key={i}>
                <span className="jl-num" aria-hidden="true">{i + 1}</span>
                <div>
                  <div className="jl-head">
                    <strong>{s.title}</strong>
                    {s.actor && <span className={`actor-chip sm ${actorTone(s.actor, actors)}`}>{s.actor}</span>}
                  </div>
                  {s.detail && <p>{s.detail}</p>}
                </div>
              </li>
            ))}
          </ol>
        </section>
      )}

      {doc.business_rules?.length > 0 && (
        <section className="req-sec">
          <h4 className="req-sec-title"><Scale size={15} aria-hidden="true" /> Business rules</h4>
          <ul className="research-bullet-list">{doc.business_rules.map((r, i) => <li key={i}>{r}</li>)}</ul>
        </section>
      )}

      {doc.acceptance_criteria?.length > 0 && (
        <section className="req-sec">
          <h4 className="req-sec-title"><ListChecks size={15} aria-hidden="true" /> Acceptance criteria</h4>
          <div className="research-table-wrap">
            <table className="research-table ac-table">
              <thead><tr><th>#</th><th>Criterion</th><th>Priority</th></tr></thead>
              <tbody>
                {doc.acceptance_criteria.map((a) => (
                  <tr key={a.id}>
                    <td className="ac-id">{a.id}</td>
                    <td><Gwt text={a.criterion} /></td>
                    <td><span className={`prio ${a.priority.toLowerCase()}`}>{a.priority}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {(doc.out_of_scope?.length > 0 || doc.open_questions?.length > 0) && (
        <div className="req-side">
          {doc.out_of_scope?.length > 0 && (
            <section className="req-note">
              <h4 className="req-sec-title"><XCircle size={15} aria-hidden="true" /> Out of scope</h4>
              <ul className="research-bullet-list">{doc.out_of_scope.map((x, i) => <li key={i}>{x}</li>)}</ul>
            </section>
          )}
          {doc.open_questions?.length > 0 && (
            <section className="req-note warn">
              <h4 className="req-sec-title"><CircleHelp size={15} aria-hidden="true" /> Open questions</h4>
              <ul className="research-bullet-list">{doc.open_questions.map((x, i) => <li key={i}>{x}</li>)}</ul>
            </section>
          )}
        </div>
      )}
    </div>
  );
}

// Legacy requirements (drafted before the structured format) — keep them
// readable by splitting the prose into paragraphs.
export function LegacyBody({ text }) {
  return (
    <div className="req-legacy">
      {text.split(/\n\s*\n/).map((p, i) => <p key={i}>{p.trim()}</p>)}
    </div>
  );
}

// "User: forwards a link" -> actor tag + text (flows are written "Who: what").
export function FlowStepText({ text }) {
  const m = /^([A-Z][\w &'().-]{1,28}):\s+(.+)$/.exec(text || "");
  if (!m) return <>{text}</>;
  return <><span className="actor-chip sm a1 step-actor">{m[1]}</span> {m[2]}</>;
}
