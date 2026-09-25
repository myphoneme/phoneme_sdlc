import { useState } from "react";
import DiscoveryChat from "./stages/DiscoveryChat.jsx";
import ResearchCard from "./stages/ResearchCard.jsx";
import IdentityTheme from "./stages/IdentityTheme.jsx";
import Generating from "./stages/Generating.jsx";
import BrdPrdManager from "./stages/BrdPrdManager.jsx";

const STAGES = ["discovery", "research", "identity", "freeze", "generating", "manager"];

export default function App() {
  const [session, setSession] = useState(null); // full SessionState from backend
  const [requirements, setRequirements] = useState([]);

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
        {["Discovery Chat", "Research", "Identity & Theme", "Freeze Scope", "Generating", "BRD/PRD Manager"].map(
          (label, i) => (
            <div key={label} className={"stage-pip" + (i <= stageIndex ? " done" : "")}>
              <span className="stage-pip-dot" />
              {label}
            </div>
          )
        )}
      </nav>

      <main className="app-main">
        {stage === "discovery" && <DiscoveryChat session={session} setSession={setSession} />}
        {stage === "research" && <ResearchCard session={session} setSession={setSession} />}
        {stage === "identity" && <IdentityTheme session={session} setSession={setSession} />}
        {stage === "freeze" && (
          <Generating session={session} setSession={setSession} setRequirements={setRequirements} freezeOnly />
        )}
        {stage === "generating" && (
          <Generating session={session} setSession={setSession} setRequirements={setRequirements} />
        )}
        {stage === "manager" && (
          <BrdPrdManager session={session} requirements={requirements} setRequirements={setRequirements} />
        )}
      </main>
    </div>
  );
}
