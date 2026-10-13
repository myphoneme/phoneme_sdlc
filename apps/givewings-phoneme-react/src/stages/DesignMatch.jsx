// Step 2/3 of "bring your own designs" (2026-10-12), at UI/UX. The screens the
// owner uploaded at Identity that are not part of the frame are matched to the
// frozen modules by AI; the owner checks the sort, adds them to the modules,
// and for every module that still has no design decides: upload, or let
// GiveWings generate it in the style read off their designs.
import { useEffect, useState } from "react";
import { CheckCircle2, CircleHelp, ImageUp, Sparkles, Wand2 } from "lucide-react";
import { api, fileUrl } from "../api.js";

export default function DesignMatch({ session, setSession }) {
  const sid = session.session_id;
  const designs = session.brand?.blueprint?.designs || [];
  const byId = Object.fromEntries(designs.map((d) => [d.design_id, d]));
  const [board, setBoard] = useState(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState(null);
  const sig = JSON.stringify(designs.map((d) => [d.design_id, d.status, d.module, d.applied])) + (session.ui_modules || []).map((m) => `${m.generate_ok}${m.doc?.screens?.length}${m.status}`).join();
  useEffect(() => { api.designBoard(sid).then(setBoard).catch(() => {}); }, [sid, sig]);
  if (!board?.active) return null;

  async function run(label, fn) {
    setBusy(label); setError(null);
    try { setSession(await fn()); } catch (e) { setError(e.message); } finally { setBusy(""); }
  }
  const mods = board.modules;
  // every uploaded screen that can become a module screen -- business screens and the frame's tab/share screens,
  // a board's screens in board order (a complete mobile flow goes in whole)
  const FRAME_ONLY = ["landing", "sign_in", "sign_up", "onboarding"];
  const flowPos = {};
  (board?.flows || []).forEach((f, fi) => f.design_ids.forEach((id, i) => { flowPos[id] = fi * 100 + i; }));
  const live = designs.filter((d) => d.status !== "ignored" && !FRAME_ONLY.includes(d.kind))
    .sort((a, b) => (flowPos[a.design_id] ?? 9999 + a.order) - (flowPos[b.design_id] ?? 9999 + b.order));
  const inFlow = new Set(Object.keys(flowPos));
  const loose = live.filter((d) => !inFlow.has(d.design_id));
  const unmatchedAI = live.some((d) => !d.module && !d.applied && d.module_conf === 0);
  const thumb = (id, cls = "") => <span className={`di-thumb sm ${byId[id]?.platform} ${cls}`}><img src={fileUrl(`/identity/${sid}/designs/file/${id}`)} alt={byId[id]?.title || "Your design"} loading="lazy" /></span>;
  const pick = (d) => (
    <select aria-label={`Module for ${d.title}`} value={d.module} disabled={!!busy || !!d.applied}
      onChange={(e) => run("Saving…", () => api.assignDesign(sid, d.design_id, e.target.value))}>
      <option value="">— not matched —</option>
      <option value="__none__">Keep in the frame only</option>
      {mods.map((m) => <option key={m.ui_id} value={m.module}>{m.module}</option>)}
    </select>
  );
  const needsDecision = mods.filter((m) => m.state === "decide");

  return (
    <section className="di dm">
      <div className="di-summary">
        <Sparkles size={18} aria-hidden="true" />
        <div>
          <strong>Your designs, matched to the modules</strong>
          <p>{live.length ? `${live.length} of your screens are for the modules. GiveWings proposes where each belongs — you check it.` : "All of your screens were placed in the frame at Identity."}
            {" "}Modules without a design of yours are generated in your style — only after you agree.</p>
        </div>
        {live.some((d) => !d.applied) && <button className="btn-secondary sm" disabled={!!busy} onClick={() => run("Matching…", () => api.matchDesigns(sid))}>{unmatchedAI || live.every((d) => !d.module) ? "Match them to the modules" : "Match again"}</button>}
      </div>
      {busy && <p className="muted small">{busy}</p>}
      {error && <div className="error-banner" role="alert">{error}</div>}

      {(board?.flows || []).filter((f) => f.design_ids.length).map((f) => (
        <div key={f.flow_id} className="dm-flow">
          <div className="dm-flow-head">
            <h4 className="mini-head">{f.name} · {f.design_ids.length} screens, in order</h4>
            <select aria-label={`Put all of ${f.name} into one module`} value="" disabled={!!busy}
              onChange={(e) => { const mod = e.target.value; if (!mod) return; run("Assigning the flow…", async () => {
                let st = null;
                for (const id of f.design_ids) { const d = live.find((x) => x.design_id === id); if (d && !d.applied) st = await api.assignDesign(sid, id, mod); }
                return st || session;
              }); }}>
              <option value="">Put the whole flow into…</option>
              {mods.map((m) => <option key={m.ui_id} value={m.module}>{m.module}</option>)}
            </select>
          </div>
          <p className="muted small">The whole flow from your board becomes {f.platform === "phone" ? "mobile" : "web"} design snapshots in UI/UX — each screen inside the module it belongs to, in this order.</p>
          <div className="di-grid">{f.design_ids.map((id) => live.find((d) => d.design_id === id)).filter(Boolean).map((d) => (
            <div key={d.design_id} className={"di-card" + (!d.module && !d.applied ? " unsure" : "")}>
              {thumb(d.design_id)}
              <div>
                <strong>{d.title || "Screen"}</strong>
                <small>{d.caption ? `${d.caption} · ` : ""}{d.platform}{d.tab ? ` · ${d.tab}` : ""}</small>
                {d.applied ? <span className="chip good"><CheckCircle2 size={11} /> In {d.module}</span>
                  : d.module === "__none__" ? <span className="chip">Frame only</span>
                  : d.module ? (d.module_conf === -1 ? <span className="chip good">Your choice</span> : <span className={"chip" + (d.module_conf < 0.55 ? " warn" : "")}><CircleHelp size={11} /> {d.module_conf < 0.55 ? "Check this" : "Proposed"}</span>)
                  : <span className="chip warn"><CircleHelp size={11} /> Not matched</span>}
                <div className="di-acts">{pick(d)}</div>
              </div>
            </div>
          ))}</div>
        </div>
      ))}
      {loose.length > 0 && (
        <div className="di-grid">
          {loose.map((d) => (
            <div key={d.design_id} className={"di-card" + (!d.module && !d.applied ? " unsure" : "")}>
              {thumb(d.design_id)}
              <div>
                <strong>{d.title || "Screen"}</strong>
                <small>{d.caption ? `${d.caption} · ` : ""}{d.platform}{d.tab ? ` · ${d.tab}` : ""}</small>
                {d.applied ? <span className="chip good"><CheckCircle2 size={11} /> In {d.module}</span>
                  : d.module === "__none__" ? <span className="chip">Frame only</span>
                  : d.module ? (d.module_conf === -1 ? <span className="chip good">Your choice</span> : <span className={"chip" + (d.module_conf < 0.55 ? " warn" : "")}><CircleHelp size={11} /> {d.module_conf < 0.55 ? "Check this" : "Proposed"}</span>)
                  : <span className="chip warn"><CircleHelp size={11} /> Not matched</span>}
                <div className="di-acts">{pick(d)}</div>
              </div>
            </div>
          ))}
        </div>
      )}
      {board.pending_apply > 0 && (
        <div className="requirement-actions"><button className="btn-primary" disabled={!!busy} onClick={() => run("Adding…", () => api.applyDesigns(sid))}><ImageUp size={14} /> Add {board.pending_apply} matched screen{board.pending_apply > 1 ? "s" : ""} to their modules</button></div>
      )}

      <h4 className="mini-head">Every module</h4>
      <div className="di-mods">
        {mods.map((m) => (
          <div key={m.ui_id} className={"di-mod " + m.state}>
            <strong>{m.module}</strong>
            <div className="di-mod-thumbs">{[...m.applied, ...m.designs].map((id) => <span key={id}>{thumb(id)}</span>)}{m.uploads > m.applied.length && <small>{m.uploads - m.applied.length} uploaded here</small>}</div>
            {m.state === "yours" && <span className="chip good"><CheckCircle2 size={11} /> Your design</span>}
            {m.state === "generate" && <>
              <span className="chip"><Wand2 size={11} /> Generated in your style</span>
              {!m.frozen && <button className="link-btn" disabled={!!busy} onClick={() => run("Saving…", () => api.moduleConsent(sid, m.ui_id, false))}>Change my mind</button>}
            </>}
            {m.state === "decide" && <>
              <span className="chip warn"><CircleHelp size={11} /> No design of yours</span>
              <small>Open the module below to upload its screens, or:</small>
              <button className="btn-secondary sm" disabled={!!busy || m.frozen} onClick={() => run("Saving…", () => api.moduleConsent(sid, m.ui_id, true))}><Wand2 size={13} /> Generate it in my style</button>
            </>}
          </div>
        ))}
      </div>
      {board.blocked && <p className="notice-inline">{board.blocked}</p>}
      {!board.blocked && needsDecision.length === 0 && <p className="muted small"><CheckCircle2 size={13} /> Every module has a design of yours or your OK to generate it.</p>}
    </section>
  );
}
