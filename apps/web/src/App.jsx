import { useEffect, useState } from "react";
import DiscoveryChat from "./stages/DiscoveryChat.jsx";
import ResearchCard from "./stages/ResearchCard.jsx";
import IdentityTheme from "./stages/IdentityTheme.jsx";
import Generating from "./stages/Generating.jsx";
import ModuleFlowReview from "./stages/ModuleFlowReview.jsx";
import BrdPrdManager from "./stages/BrdPrdManager.jsx";
import { api } from "./api.js";

const STAGES = ["discovery", "research", "identity", "freeze", "flow", "generating", "manager"];

// The backend now persists sessions durably (wizard_sessions table), but a
// browser refresh has no way to know which session_id to ask for unless we
// remember it ourselves -- that's what this key is for. Session data itself
// never lives in localStorage, only the id pointing back to it server-side.
const SESSION_STORAGE_KEY = "phoneme_sdlc_session_id";

export default function App() {
  const [session, setSession] = useState(null); // full SessionState from backend
  const [requirements, setRequirements] = useState([]);
  const [rehydrating, setRehydrating] = useState(true);

  // On mount: if a previous session_id is stored, ask the backend for it and
  // resume exactly where the user left off instead of starting blank.
  useEffect(() => {
    const storedId = localStorage.getItem(SESSION_STORAGE_KEY);
    if (!storedId) {
      setRehydrating(false);
      return;
    }
    api
      .getSession(storedId)
      .then((restored) => {
        setSession(restored);
        return api.listRequirements(storedId).catch(() => []);
      })
      .then((reqs) => setRequirements(reqs || []))
      .catch(() => {
        // Session no longer exists server-side (e.g. a DB reset) -- drop the
        // stale id rather than repeatedly failing to resume it.
        localStorage.removeItem(SESSION_STORAGE_KEY);
      })
      .finally(() => setRehydrating(false));
  }, []);

  // Keep localStorage in sync with whichever session is active so the next
  // refresh (or accidental tab close) can resume it.
  useEffect(() => {
    if (session?.session_id) {
      localStorage.setItem(SESSION_STORAGE_KEY, session.session_id);
    }
  }, [session?.session_id]);

  const stage = session?.stage || "discovery";
  const stageIndex = STAGES.indexOf(stage);

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="logo-wordmark">
          <span className="logo-phon">PHON</span>
          <span className="logo-eme">EME</span>
        </div>
        <div className="header-title">SDLC Platform — Idea to BRD/PRD</div>
      </header>

      <nav className="stage-tracker">
        {["Discovery Chat", "Research", "Identity & Theme", "Freeze Scope", "Flow Design", "Generating", "BRD/PRD Manager"].map(
          (label, i) => (
            <div key={label} className={"stage-pip" + (i <= stageIndex ? " done" : "")}>
              <span className="stage-pip-dot" />
              {label}
            </div>
          )
        )}
      </nav>

      <main className="app-main">
        {rehydrating && (
          <div className="stage-card">
            <p className="stage-hint">Resuming your session…</p>
          </div>
        )}
        {!rehydrating && stage === "discovery" && <DiscoveryChat session={session} setSession={setSession} />}
        {!rehydrating && stage === "research" && <ResearchCard session={session} setSession={setSession} />}
        {!rehydrating && stage === "identity" && <IdentityTheme session={session} setSession={setSession} />}
        {!rehydrating && stage === "freeze" && (
          <Generating session={session} setSession={setSession} setRequirements={setRequirements} freezeOnly />
        )}
        {!rehydrating && stage === "flow" && <ModuleFlowReview session={session} setSession={setSession} />}
        {!rehydrating && stage === "generating" && (
          <Generating session={session} setSession={setSession} setRequirements={setRequirements} />
        )}
        {!rehydrating && stage === "manager" && (
          <BrdPrdManager session={session} requirements={requirements} setRequirements={setRequirements} />
        )}
      </main>
    </div>
  );
}
