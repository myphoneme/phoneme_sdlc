import { useEffect, useState } from "react";
import { api } from "../api.js";

const SUGGESTED_NAMES = ["HireLoop", "RecruitIQ", "TalentSprint"];

export default function ResearchCard({ session, setSession }) {
  const [loading, setLoading] = useState(false);
  const [moreQuery, setMoreQuery] = useState("");
  const [customName, setCustomName] = useState("");
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (session && session.companies.length === 0) {
      setLoading(true);
      api
        .research(session.session_id)
        .then(setSession)
        .catch((e) => setError(e.message))
        .finally(() => setLoading(false));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.session_id]);

  async function searchMore() {
    if (!moreQuery.trim()) return;
    setLoading(true);
    try {
      setSession(await api.researchMore(session.session_id, moreQuery.trim()));
      setMoreQuery("");
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function checkAndSelect(name) {
    setChecking(true);
    setError(null);
    try {
      const withCheck = await api.checkName(session.session_id, name);
      setSession(withCheck);
      const chosen = await api.selectName(session.session_id, name);
      setSession(chosen);
    } catch (e) {
      setError(e.message);
    } finally {
      setChecking(false);
    }
  }

  if (!session) return null;

  return (
    <div className="stage-card">
      <h2>Competitive Research</h2>
      <p className="stage-hint">Based on your concept, here's who else plays in this space.</p>

      <div className="research-card">
        {loading && session.companies.length === 0 && <div className="stage-hint">Searching…</div>}
        {session.companies.map((c, i) => (
          <div key={i} className="research-row">
            <span className="chip accent">Found</span>
            <span>{c}</span>
          </div>
        ))}
      </div>

      <div className="research-more-row">
        <input
          value={moreQuery}
          onChange={(e) => setMoreQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && searchMore()}
          placeholder="Search for more similar companies…"
          disabled={loading}
        />
        <button className="btn-secondary" onClick={searchMore} disabled={loading || !moreQuery.trim()}>
          Search
        </button>
      </div>

      {error && <div className="error-banner">{error}</div>}

      <hr className="divider" />

      <h3>Pick a product name</h3>
      <div className="choice-row">
        {SUGGESTED_NAMES.map((n) => (
          <button key={n} className="opt-chip" disabled={checking} onClick={() => checkAndSelect(n)}>
            {n}
          </button>
        ))}
      </div>

      <div className="custom-name-row">
        <input
          value={customName}
          onChange={(e) => setCustomName(e.target.value)}
          placeholder="Or type your own name…"
          disabled={checking}
        />
        <button
          className="btn-secondary"
          disabled={checking || !customName.trim()}
          onClick={() => checkAndSelect(customName.trim())}
        >
          {checking ? "Checking…" : "Check availability & use"}
        </button>
      </div>

      {session.selected_name && (
        <div className="concept-summary-card">
          Selected: <strong>{session.selected_name}</strong> — moving to theme selection…
        </div>
      )}
    </div>
  );
}
