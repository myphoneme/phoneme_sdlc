import { useEffect, useState } from "react";
import { AlertTriangle, ArrowRight, BadgeCheck, Coins, ExternalLink, Lightbulb, Search, Star, Target, TrendingUp } from "lucide-react";
import { api } from "../api.js";

function Section({ icon: Icon, title, children }) {
  return (
    <section className="research-section">
      <h3><span className="section-icon" aria-hidden="true"><Icon size={16} /></span>{title}</h3>
      {children}
    </section>
  );
}


export function ResearchReportView({ research }) {
  return (
        <div className="research-report">
          {research.market_landscape?.length > 0 && (
            <Section icon={Target} title="Market landscape">
              <div className="research-table-wrap">
                <table className="research-table">
                  <thead>
                    <tr><th>Category</th><th>Examples</th><th>What they do</th><th>Limitations</th></tr>
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
            </Section>
          )}

          {(research.viability_verdict || research.positioning_reframe || research.killer_feature) && (
            <div className="insight-grid">
              {research.viability_verdict && (
                <div className="insight"><span className="insight-label"><BadgeCheck size={15} /> Viability &amp; revenue</span><p>{research.viability_verdict}</p></div>
              )}
              {research.positioning_reframe && (
                <div className="insight"><span className="insight-label"><Lightbulb size={15} /> Positioning</span><p>{research.positioning_reframe}</p></div>
              )}
              {research.killer_feature && (
                <div className="insight accent"><span className="insight-label"><Star size={15} /> Killer feature</span><p>{research.killer_feature}</p></div>
              )}
            </div>
          )}

          <div className="list-grid">
            {research.market_demand?.length > 0 && (
              <Section icon={TrendingUp} title="Market demand signals">
                <ul className="research-bullet-list">{research.market_demand.map((b, i) => <li key={i}>{b}</li>)}</ul>
              </Section>
            )}
            {research.risks?.length > 0 && (
              <Section icon={AlertTriangle} title="Risks & constraints">
                <ul className="research-bullet-list risk">{research.risks.map((b, i) => <li key={i}>{b}</li>)}</ul>
              </Section>
            )}
            {research.recommended_features?.length > 0 && (
              <Section icon={Lightbulb} title="Recommended features">
                <ul className="research-bullet-list">{research.recommended_features.map((b, i) => <li key={i}>{b}</li>)}</ul>
              </Section>
            )}
            {research.monetization?.length > 0 && (
              <Section icon={Coins} title="Monetization model">
                <ul className="research-bullet-list">{research.monetization.map((b, i) => <li key={i}>{b}</li>)}</ul>
              </Section>
            )}
          </div>

          {research.sources?.length > 0 && (
            <details className="sources">
              <summary>{research.sources.length} sources</summary>
              <ul>
                {research.sources.map((url, i) => (
                  <li key={i}><a href={url} target="_blank" rel="noopener noreferrer">{url}<ExternalLink size={12} aria-hidden="true" /></a></li>
                ))}
              </ul>
            </details>
          )}
        </div>
  );
}

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

  async function continueToIdentity() {
    setChecking(true);
    setError(null);
    try {
      setSession(await api.researchDone(session.session_id));
    } catch (e) {
      setError(e.message);
    } finally {
      setChecking(false);
    }
  }

  if (!session) return null;

  const suggestedNames = session.suggested_names?.length ? session.suggested_names : [];

  return (
    <div className="research">
      {loading && !hasReport && (
        <div className="working" role="status">
          <span className="spinner" aria-hidden="true" />
          <div><strong>Researching the live web…</strong><p>Scanning competitors, pricing and demand signals. This usually takes under a minute.</p></div>
        </div>
      )}

      {hasReport && <ResearchReportView research={research} />}

      {!hasReport && !loading && session.companies.length > 0 && (
        <div className="found-list">
          {session.companies.map((c, i) => (
            <div key={i} className="found-row"><span className="chip accent">Found</span><span>{c}</span></div>
          ))}
        </div>
      )}

      <div className="inline-field">
        <Search size={17} aria-hidden="true" />
        <input
          value={moreQuery}
          onChange={(e) => setMoreQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && searchMore()}
          placeholder="Search for more similar companies…"
          aria-label="Search for more similar companies"
          disabled={loading}
        />
        <button className="btn-secondary" onClick={searchMore} disabled={loading || !moreQuery.trim()}>Search</button>
      </div>

      {error && <div className="error-banner" role="alert">{error}</div>}

      {hasReport && (
        <div className="sticky-actions">
          <span className="muted">
            {suggestedNames.length > 0
              ? <>Name ideas from research: <strong>{suggestedNames.join(", ")}</strong> — you will pick the name and check domains next.</>
              : "Next you will pick the name, check domains, and build the brand."}
          </span>
          <button className="btn-primary" disabled={checking} onClick={continueToIdentity}>
            {checking ? "Opening…" : "Continue to Identity"} <ArrowRight size={16} />
          </button>
        </div>
      )}
    </div>
  );
}
