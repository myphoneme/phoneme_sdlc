// Stage 9 — UI/UX screens in the product's own brand. Screens are rendered by
// the server (same HTML as the exported mockup file) and previewed here.
import { useState } from "react";
import { api, fileUrl } from "../api.js";
import { GenerationBoard } from "./Generating.jsx";
import { BaselinePanel, ReviewCard, useStageDrafting } from "./ReviewKit.jsx";

function ScreenPreview({ sid, item, revised }) {
  const [h, setH] = useState(640);
  const v = encodeURIComponent(JSON.stringify(revised ? item.revised_doc : item.doc).length);
  return (
    <div className="ui-preview">
      {(revised ? item.revised_doc : item.doc)?.notes?.length > 0 && (
        <ul className="research-bullet-list">{(revised ? item.revised_doc : item.doc).notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
      )}
      <iframe title={`${item.module} screens`} src={fileUrl(`/uiux/${sid}/render/${item.ui_id}?revised=${revised ? 1 : 0}&v=${v}`)} style={{ height: h }}
        onLoad={(e) => { try { setH(Math.min(4000, e.target.contentDocument.documentElement.scrollHeight + 4)); } catch { /* cross-origin */ } }} />
    </div>
  );
}

export default function UIUXStage({ session, setSession }) {
  const sid = session.session_id;
  const items = session.ui_modules || [];
  const [openIds, setOpenIds] = useState(() => new Set());
  const { error, running, retry } = useStageDrafting({ kind: "uiux", session, setSession, items, gen: session.ui_generation });
  const g = session.ui_generation;
  const toggle = (id) => setOpenIds((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });
  const screens = items.reduce((n, i) => n + (i.doc?.screens?.length || 0), 0);
  return (
    <div className="review">
      {(running || g?.status === "failed" || items.some((i) => !i.doc)) && g?.items?.length > 0 && (
        <>
          <GenerationBoard generation={g} />
          {g.status === "failed" && <div className="requirement-actions"><button className="btn-primary" onClick={retry}>Retry failed modules</button></div>}
        </>
      )}
      {error && <div className="error-banner" role="alert">{error}</div>}
      <BaselinePanel label="UI/UX" nextLabel="the build handover" refreshKey={items.map((i) => i.status).join()}
        fetchStatus={() => api.uiux.baseline(sid)} onBaseline={async () => setSession(await api.uiux.createBaseline(sid))}
        downloads={[{ label: "Mockups (.html)", href: fileUrl(`/uiux/${sid}/export/mockups.html`) }]} />
      {items.length > 0 && <p className="muted small">{screens} screens across {items.length} modules, in {session.selected_name}'s colours. Comment on any module to rework its screens.</p>}
      <div className="requirement-feed">
        {items.map((m) => (
          <ReviewCard key={m.ui_id} kind="uiux" sessionId={sid} item={m} itemId={m.ui_id} setSession={setSession}
            title={m.module} subtitle={`Implements ${m.req_id} · ${m.doc ? `${m.doc.screens.length} screens: ${m.doc.screens.map((s) => s.name).join(", ")}` : "drafting…"}`}
            open={openIds.has(m.ui_id)} onToggle={() => toggle(m.ui_id)}
            renderDoc={(doc, revised) => <ScreenPreview sid={sid} item={m} revised={revised} />} />
        ))}
      </div>
    </div>
  );
}
