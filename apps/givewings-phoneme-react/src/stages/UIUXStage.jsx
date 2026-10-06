// Stage 9 — UI/UX screens in the product's own brand. Screens are rendered by
// the server (same HTML as the exported mockup file) and previewed here.
// 2026-10-06: a clickable prototype of the whole product, and the owner can
// upload their own designs (PNG/JPG/WebP/GIF/PDF) as screens of any module.
import { useRef, useState } from "react";
import { ArrowDown, ArrowUp, Download, ExternalLink, ImageUp, MousePointerClick, Pencil, Play, Save, Sparkles, Trash2, X } from "lucide-react";
import { api, fileUrl } from "../api.js";
import { GenerationBoard } from "./Generating.jsx";
import { BaselinePanel, ReviewCard, useStageDrafting } from "./ReviewKit.jsx";

const protoUrl = (sid, key) => fileUrl(`/uiux/${sid}/prototype`) + (key ? `#${key}` : "");
const keyOf = (item, sc) => `${item.ui_id}--${sc.screen_id || sc.name}`.replace(/ /g, "_");

function ScreenPreview({ sid, item, revised }) {
  const [h, setH] = useState(640);
  const doc = revised ? item.revised_doc : item.doc;
  const v = encodeURIComponent(JSON.stringify(doc).length);
  return (
    <div className="ui-preview">
      {doc?.notes?.length > 0 && <ul className="research-bullet-list">{doc.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>}
      <iframe title={`${item.module} screens`} src={fileUrl(`/uiux/${sid}/render/${item.ui_id}?revised=${revised ? 1 : 0}&v=${v}`)} style={{ height: h }}
        onLoad={(e) => { try { setH(Math.min(6000, e.target.contentDocument.documentElement.scrollHeight + 4)); } catch { /* cross-origin */ } }} />
    </div>
  );
}

// Order, rename and remove screens; upload the owner's own designs.
function ScreenManager({ sid, item, setSession }) {
  const [busy, setBusy] = useState("");
  const [error, setError] = useState(null);
  const [mode, setMode] = useState("add");
  const [editing, setEditing] = useState(null); // {id, name}
  const [drag, setDrag] = useState(false);
  const input = useRef(null);
  const locked = item.status === "Frozen" || !!item.revised_doc;
  const screens = item.doc?.screens || [];

  async function run(label, fn) {
    setBusy(label); setError(null);
    try { setSession(await fn()); return true; } catch (e) { setError(e.message); return false; } finally { setBusy(""); }
  }
  const upload = (files) => files?.length && run(`Uploading ${files.length} design${files.length > 1 ? "s" : ""}…`, () => api.uploadDesigns(sid, item.ui_id, files, mode));

  return (
    <section className="screen-manager">
      <div className="sm-head">
        <strong>Screens in this module ({screens.length})</strong>
        {screens[0] && <a className="btn-secondary sm" href={protoUrl(sid, keyOf(item, screens[0]))} target="_blank" rel="noreferrer"><Play size={13} /> Play this module</a>}
      </div>
      <ol className="sm-list">
        {screens.map((sc, i) => (
          <li key={sc.screen_id}>
            <span className="sm-num">{i + 1}</span>
            {editing?.id === sc.screen_id ? (
              <span className="sm-edit">
                <input value={editing.name} autoFocus onChange={(e) => setEditing({ ...editing, name: e.target.value })}
                  onKeyDown={(e) => e.key === "Enter" && run("Saving…", () => api.updateScreen(sid, item.ui_id, sc.screen_id, { name: editing.name })).then((ok) => ok && setEditing(null))} />
                <button className="icon-btn" title="Save" onClick={() => run("Saving…", () => api.updateScreen(sid, item.ui_id, sc.screen_id, { name: editing.name })).then((ok) => ok && setEditing(null))}><Save size={14} /></button>
                <button className="icon-btn" title="Cancel" onClick={() => setEditing(null)}><X size={14} /></button>
              </span>
            ) : (
              <span className="sm-name">{sc.name}<span className={"chip " + (sc.source === "upload" ? "good" : "")}>{sc.source === "upload" ? "Your design" : "AI"}</span></span>
            )}
            {!locked && editing?.id !== sc.screen_id && (
              <span className="sm-tools">
                <button className="icon-btn" title="Move up" disabled={!!busy || i === 0} onClick={() => run("Moving…", () => api.moveScreen(sid, item.ui_id, sc.screen_id, -1))}><ArrowUp size={14} /></button>
                <button className="icon-btn" title="Move down" disabled={!!busy || i === screens.length - 1} onClick={() => run("Moving…", () => api.moveScreen(sid, item.ui_id, sc.screen_id, 1))}><ArrowDown size={14} /></button>
                <button className="icon-btn" title="Rename" disabled={!!busy} onClick={() => setEditing({ id: sc.screen_id, name: sc.name })}><Pencil size={14} /></button>
                <button className="icon-btn danger" title="Remove screen" disabled={!!busy || screens.length === 1} onClick={() => run("Removing…", () => api.removeScreen(sid, item.ui_id, sc.screen_id))}><Trash2 size={14} /></button>
              </span>
            )}
          </li>
        ))}
      </ol>
      {!locked && (
        <div className={"upload-zone" + (drag ? " drag" : "")}
          onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
          onDrop={(e) => { e.preventDefault(); setDrag(false); upload(e.dataTransfer.files); }}>
          <ImageUp size={20} aria-hidden="true" />
          <div>
            <strong>Have your own designs?</strong>
            <p>Drop PNG, JPG, WebP, GIF or PDF files here (max 10 MB each). They become screens of this module — in the prototype, the review and the exported mockups.</p>
          </div>
          <select value={mode} onChange={(e) => setMode(e.target.value)} aria-label="Upload mode" disabled={!!busy}>
            <option value="add">Add to these screens</option>
            <option value="replace">Replace the AI screens</option>
          </select>
          <button className="btn-primary" disabled={!!busy} onClick={() => input.current?.click()}><ImageUp size={14} /> {busy.startsWith("Uploading") ? "Uploading…" : "Upload designs"}</button>
          <input ref={input} type="file" multiple hidden accept="image/png,image/jpeg,image/webp,image/gif,application/pdf"
            onChange={(e) => { upload(e.target.files); e.target.value = ""; }} />
        </div>
      )}
      {locked && <p className="muted small">{item.status === "Frozen" ? "Frozen — unfreeze to change screens." : "Accept or discard the pending revision to change screens."}</p>}
      {busy && !busy.startsWith("Uploading") && <p className="muted small">{busy}</p>}
      {error && <div className="error-banner" role="alert">{error}</div>}
    </section>
  );
}

function PrototypePanel({ sid, session }) {
  const [open, setOpen] = useState(false);
  const total = (session.ui_modules || []).reduce((n, m) => n + (m.doc?.screens?.length || 0), 0);
  if (!total) return null;
  return (
    <section className="proto-panel">
      <div className="proto-panel-head">
        <MousePointerClick size={20} aria-hidden="true" />
        <div>
          <strong>Clickable prototype</strong>
          <p>Walk through {session.selected_name} like a real product: {total} screens, buttons and the sidebar take you to the next screen, uploaded designs click through too. Use Previous / Next to follow the whole journey.</p>
        </div>
        <div className="baseline-actions">
          <button className="btn-primary" onClick={() => setOpen((o) => !o)}><Play size={15} /> {open ? "Hide prototype" : "Try the prototype"}</button>
          <a className="btn-secondary" href={protoUrl(sid)} target="_blank" rel="noreferrer"><ExternalLink size={15} /> Full screen</a>
          <a className="btn-secondary" href={fileUrl(`/uiux/${sid}/prototype?download=1`)} download><Download size={15} /> Prototype (.html)</a>
        </div>
      </div>
      {open && <iframe className="proto-frame" title="Clickable prototype" src={protoUrl(sid) + `?v=${total}`} />}
    </section>
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
  const uploads = items.reduce((n, i) => n + (i.doc?.screens?.filter((s) => s.source === "upload").length || 0), 0);
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
      <PrototypePanel sid={sid} session={session} />
      {items.length > 0 && <p className="muted small">{screens} screens across {items.length} modules{uploads ? ` (${uploads} uploaded by you)` : ""}, in {session.selected_name}'s colours. Comment on a module to rework its screens, or upload your own designs.</p>}
      <div className="requirement-feed">
        {items.map((m) => (
          <ReviewCard key={m.ui_id} kind="uiux" sessionId={sid} item={m} itemId={m.ui_id} setSession={setSession}
            title={m.module} subtitle={`Implements ${m.req_id} · ${m.doc ? `${m.doc.screens.length} screens: ${m.doc.screens.map((s) => s.name).join(", ")}` : "drafting…"}`}
            open={openIds.has(m.ui_id)} onToggle={() => toggle(m.ui_id)}
            renderDoc={(doc, revised) => (
              <>
                {!revised && <ScreenManager sid={sid} item={m} setSession={setSession} />}
                <ScreenPreview sid={sid} item={m} revised={revised} />
              </>
            )} />
        ))}
      </div>
    </div>
  );
}
