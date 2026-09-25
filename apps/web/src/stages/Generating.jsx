import { useEffect, useState } from "react";
import { api } from "../api.js";

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
      <div className="stage-card">
        <h2>Freeze Scope — Module Breakdown</h2>
        <p className="stage-hint">Platform-Core modules (auth/security/gateway) link to the shared contract instead of being drafted per project.</p>
        {error && <div className="error-banner">{error}</div>}
        {loading && session.modules.length === 0 && <div className="stage-hint">Drafting module breakdown…</div>}
        <ul className="module-list">
          {session.modules.map((m, i) => (
            <li key={i} className={m.startsWith("Platform-Core") ? "module-platform-core" : ""}>
              {m}
            </li>
          ))}
        </ul>
      </div>
    );
  }

  return (
    <div className="stage-card">
      <h2>Generating BRD/PRD…</h2>
      {error && <div className="error-banner">{error}</div>}
      {loading && <div className="stage-hint">Drafting requirements for each module — this calls the commercial model tier per the routing policy.</div>}
      <ul className="module-list">
        {generated.map((r) => (
          <li key={r.req_id}>
            <strong>{r.req_id}</strong> — {r.title}
          </li>
        ))}
      </ul>
    </div>
  );
}
