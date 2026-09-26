import { useEffect, useState } from "react";
import { api } from "../api.js";

export default function ResearchCard({ session, setSession }) {
  const [loading, setLoading] = useState(false);
  const [moreQuery, setMoreQuery] = useState("");
  const [customName, setCustomName] = useState("");
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState(null);

  const research = session?.research;
  const hasReport = research && (
    research.market_landscape?.length ||
    research.viability_verdict ||
    research.recommended_features?.length
  );

  useEffect(() => {
    if (session && !session.research && session.companies.length === 0) {
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

  const suggestedNames = session.suggested_names?.length ? session.suggested_names : [];

  return (
    <div className="stage-card">
      <h2>Competitive Research</h2>
      <p className="stage-hint">
        Web-search-grounded market research: who else plays in this space, whether it's viable
        for revenue, what to build, and how to price it.
      </p>

      {loading && !hasReport && <div className="stage-hint">Researching the live web…</div>}

      {hasReport && (
        <div className="research-report">
          {research.market_landscape?.length > 0 && (
            <section className="research-section">
              <h3>Market landscape</h3>
              <div className="research-table-wrap">
                <table className="research-table">
                  <thead>
                    <tr>
                      <th>Category</th>
                      <th>Examples</th>
                      <th>What they do</th>
                      <th>Limitations</th>
                    </tr>
                  </thead>
                  <tbody>
                    {research.market_landscape.map((row, i) => (
                      <tr key={i}>
                        <td className="research-cell-strong">{row.category}</td>
                        <td>{row.examples}</td>
                        <td>{row.what_they_do}</td>
                        <td>{row.limitations}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          {research.viability_verdict && (
            <section className="research-section">
              <h3>Viability &amp; revenue verdict</h3>
              <p className="research-verdict">{research.viability_verdict}</p>
            </section>
          )}

          {research.positioning_reframe && (
            <section className="research-section">
              <h3>Positioning</h3>
              <p className="research-verdict research-reframe">{research.positioning_reframe}</p>
            </section>
          )}

          {research.killer_feature && (
            <section className="research-section">
              <h3>Killer feature</h3>
              <p className="research-verdict research-killer-feature">{research.killer_feature}</p>
            </section>
          )}

          {research.market_demand?.length > 0 && (
            <section className="research-section">
              <h3>Market demand signals</h3>
              <ul className="research-bullet-list">
                {research.market_demand.map((b, i) => (
                  <li key={i}>{b}</li>
                ))}
              </ul>
            </section>
          )}

          {research.risks?.length > 0 && (
            <section className="research-section">
              <h3>Risks &amp; constraints</h3>
              <ul className="research-bullet-list research-risk-list">
                {research.risks.map((b, i) => (
                  <li key={i}>{b}</li>
                ))}
              </ul>
            </section>
          )}

          {research.recommended_features?.length > 0 && (
            <section className="research-section">
              <h3>Recommended features</h3>
              <ul className="research-bullet-list">
                {research.recommended_features.map((b, i) => (
                  <li key={i}>{b}</li>
                ))}
              </ul>
            </section>
          )}

          {research.monetization?.length > 0 && (
            <section className="research-section">
              <h3>Monetization model</h3>
              <ul className="research-bullet-list">
                {research.monetization.map((b, i) => (
                  <li key={i}>{b}</li>
                ))}
              </ul>
            </section>
          )}
        </div>
      )}

      {!hasReport && !loading && session.companies.length > 0 && (
        <div className="research-card">
          {session.companies.map((c, i) => (
            <div key={i} className="research-row">
              <span className="chip accent">Found</span>
              <span>{c}</span>
            </div>
          ))}
        </div>
      )}

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
      {suggestedNames.length > 0 ? (
        <div className="choice-row">
          {suggestedNames.map((n) => (
            <button key={n} className="opt-chip" disabled={checking} onClick={() => checkAndSelect(n)}>
              {n}
            </button>
          ))}
        </div>
      ) : (
        <p className="stage-hint">
          {loading ? "Generating name ideas from your concept…" : "Type a name below to check and use it."}
        </p>
      )}

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
