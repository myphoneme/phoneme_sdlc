// Final step — everything baselined: the handover pack for the build team,
// filed the way Phoneme organises product workspaces
// (<Product>/Requirement, /Technical, /UI-UX), every version kept.
import { useEffect, useState } from "react";
import { Download, FileText, Folder, FolderArchive, LayoutTemplate, Network, PartyPopper } from "lucide-react";
import { api, fileUrl } from "../api.js";
import { StackSummary } from "./TechDesignStage.jsx";

function FolderTree({ files }) {
  const groups = {};
  files.forEach((f) => {
    const parts = f.split("/");
    const folder = parts.slice(0, -1).join("/");
    (groups[folder] = groups[folder] || []).push(parts[parts.length - 1]);
  });
  return (
    <ul className="folder-tree">
      {Object.keys(groups).sort().map((folder) => (
        <li key={folder}>
          <span className="ft-folder"><Folder size={15} aria-hidden="true" /> {folder}/</span>
          <ul>{groups[folder].sort().map((f) => <li key={f}><FileText size={13} aria-hidden="true" /> {f}</li>)}</ul>
        </li>
      ))}
    </ul>
  );
}

export default function HandoverPack({ session }) {
  const sid = session.session_id;
  const [files, setFiles] = useState(null);
  useEffect(() => { api.handoverFiles(sid).then(setFiles).catch(() => setFiles({ files: [] })); }, [sid]);
  const td = (session.tech_designs || []).find((t) => t.kind === "lld");
  const ui = td && (session.ui_modules || []).find((u) => u.req_id === td.req_id);
  const trace = td && ui ? ` (${td.req_id} → ${td.td_id} → ${ui.ui_id})` : "";
  const last = (t) => [...(session.baselines || [])].reverse().find((b) => b.doc_type === t);
  const rows = [
    { t: "brdprd", icon: FileText, name: "BRD/PRD", what: "What to build — business rules and acceptance criteria", href: fileUrl(`/brdprd/${sid}/export/brdprd.docx`), file: "Word (.docx)" },
    { t: "techdesign", icon: Network, name: "Technical Design (HLD/LLD)", what: "How to build it — architecture, data model, APIs", href: fileUrl(`/techdesign/${sid}/export/techdesign.docx`), file: "Word (.docx)" },
    { t: "uiux", icon: LayoutTemplate, name: "UI/UX mockups & prototype", what: "What it looks like — every screen in the brand, clickable", href: fileUrl(`/uiux/${sid}/export/mockups.html`), file: "HTML" },
  ];
  return (
    <div className="review">
      <div className="callout done-callout">
        <PartyPopper size={22} aria-hidden="true" />
        <div>
          <strong>{session.selected_name} is ready to build</strong>
          <p>All three SDLC documents are baselined in Phoneme's corporate format and traceable to each other{trace}. Hand this pack to the build team; any later change goes through unfreeze → re-baseline, so every version stays on record.</p>
        </div>
      </div>
      <section className="pack-panel">
        <div className="pack-head">
          <FolderArchive size={22} aria-hidden="true" />
          <div>
            <strong>Product folder</strong>
            <p>Filed like your other product workspaces — Requirement, Technical and UI-UX — with every baselined version kept side by side.</p>
          </div>
          <a className="btn-primary" href={fileUrl(`/handover/${sid}/pack.zip`)} download><Download size={15} /> Download product folder (.zip)</a>
        </div>
        {files ? (files.files.length ? <FolderTree files={files.files} /> : <p className="muted small">No documents filed yet.</p>) : <p className="muted small">Loading…</p>}
      </section>
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
