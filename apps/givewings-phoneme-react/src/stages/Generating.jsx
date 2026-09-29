import { useEffect, useState } from "react";
import { Boxes, Link2 } from "lucide-react";
import { api } from "../api.js";

function Working({ title, text }) {
  return (
    <div className="working" role="status">
      <span className="spinner" aria-hidden="true" />
      <div><strong>{title}</strong><p>{text}</p></div>
    </div>
  );
}

export default function Generating({ session, setSession, setRequirements, freezeOnly }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [generated, setGenerated] = useState([]);

  useEffect(() => {
    if (!session) return;
    if (freezeOnly && session.modules.length === 0) {
      setLoading(true);
      api
        .freeze(session.session_id)
        .then(setSession)
        .catch((e) => setError(e.message))
        .finally(() => setLoading(false));
    }
    if (!freezeOnly) {
      setLoading(true);
      api
        .generate(session.session_id)
        .then((reqs) => {
          setGenerated(reqs);
          setRequirements(reqs);
          setSession((s) => ({ ...s, stage: "manager" }));
        })
        .catch((e) => setError(e.message))
        .finally(() => setLoading(false));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [freezeOnly, session?.session_id]);

  if (!session) return null;

  if (freezeOnly) {
    return (
      <div className="freeze">
        {error && <div className="error-banner" role="alert">{error}</div>}
        {loading && session.modules.length === 0 && (
          <Working title="Drafting the module breakdown…" text="Splitting the concept into buildable modules." />
        )}
        {session.modules.length > 0 && (
          <ul className="module-grid">
            {session.modules.map((m, i) => {
              const core = m.startsWith("Platform-Core");
              return (
                <li key={i} className={"module-tile" + (core ? " core" : "")}>
                  <span className="module-icon" aria-hidden="true">{core ? <Link2 size={16} /> : <Boxes size={16} />}</span>
                  <span className="module-name">{m}</span>
                  {core && <span className="chip">Shared contract</span>}
                </li>
              );
            })}
          </ul>
        )}
      </div>
    );
  }

  return (
    <div className="generating">
      {error && <div className="error-banner" role="alert">{error}</div>}
      {loading && (
        <Working title="Drafting requirements for each module…" text="This uses the commercial model tier per the routing policy, so it can take a minute or two." />
      )}
      {generated.length > 0 && (
        <ul className="module-grid">
          {generated.map((r) => (
            <li key={r.req_id} className="module-tile">
              <span className="req-id">{r.req_id}</span>
              <span className="module-name">{r.title}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
