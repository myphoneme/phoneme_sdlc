// Final step — everything baselined: the handover pack for the build team.
import { Download, FileText, LayoutTemplate, Network, PartyPopper } from "lucide-react";
import { fileUrl } from "../api.js";
import { StackSummary } from "./TechDesignStage.jsx";

export default function HandoverPack({ session }) {
  const sid = session.session_id;
  const td = (session.tech_designs || []).find((t) => t.kind === "lld");
  const ui = td && (session.ui_modules || []).find((u) => u.req_id === td.req_id);
  const trace = td && ui ? ` (${td.req_id} → ${td.td_id} → ${ui.ui_id})` : "";
  const last = (t) => [...(session.baselines || [])].reverse().find((b) => b.doc_type === t);
  const rows = [
    { t: "brdprd", icon: FileText, name: "BRD/PRD", what: "What to build — business rules and acceptance criteria", href: fileUrl(`/brdprd/${sid}/export/brdprd.docx`), file: "Word (.docx)" },
    { t: "techdesign", icon: Network, name: "Technical Design (HLD/LLD)", what: "How to build it — architecture, data model, APIs", href: fileUrl(`/techdesign/${sid}/export/techdesign.docx`), file: "Word (.docx)" },
    { t: "uiux", icon: LayoutTemplate, name: "UI/UX mockups", what: "What it looks like — every screen in the brand", href: fileUrl(`/uiux/${sid}/export/mockups.html`), file: "HTML" },
  ];
  return (
    <div className="review">
      <div className="callout done-callout">
        <PartyPopper size={22} aria-hidden="true" />
        <div>
          <strong>{session.selected_name} is ready to build</strong>
          <p>All three SDLC documents are baselined and traceable to each other{trace}. Hand this pack to the build team; any later change goes through unfreeze → re-baseline, so every version stays on record.</p>
        </div>
      </div>
      <ul className="handover-list">
        {rows.map(({ t, icon: Icon, name, what, href, file }) => {
          const b = last(t);
          return (
            <li key={t}>
              <span className="module-icon" aria-hidden="true"><Icon size={18} /></span>
              <div><strong>{name}</strong><small>{what}</small><small>{b ? `v${b.version} · baselined ${b.at.slice(0, 10)} · ${b.description}` : "Not baselined"}</small></div>
              <a className="btn-secondary" href={href} download><Download size={15} /> {file}</a>
            </li>
          );
        })}
      </ul>
      <StackSummary stack={session.stack} />
    </div>
  );
}
