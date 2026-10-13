// Bring your own designs (2026-10-10). One upload for every design — phone
// and web screenshots, mockup boards, a zip. GiveWings splits boards into
// screens, reads each with AI, fills the blueprint and places each screen in
// the frame. The owner only checks the sort; empty places are generated in the
// style read off the designs.
import { useEffect, useRef, useState } from "react";
import { CheckCircle2, CircleHelp, Download, EyeOff, FolderOpen, ImageUp, Palette, RefreshCw, Sparkles, Trash2, Wand2 } from "lucide-react";
import { api, fileUrl } from "../api.js";

const KIND = {
  landing: "Landing page", sign_in: "Sign in", sign_up: "Create account", onboarding: "Welcome / first run", home: "Home",
  list: "List / library", detail: "Detail", create: "Create", publish: "Review & publish", settings: "Settings",
  profile: "Profile", share: "Share sheet", other: "Other",
};

const kb = (n) => (n > 1048576 ? `${(n / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`);

// 2026-10-13: every uploaded file is kept, as uploaded, in the product's own
// design folder -- listed here with its screens, to download, re-read or remove.
function DesignFiles({ sid, session, setSession, frozen, busy, setBusy, setError, onAdd }) {
  const [view, setView] = useState(null);
  const [confirm, setConfirm] = useState("");
  const bp = session.brand?.blueprint;
  const sig = JSON.stringify([(bp?.design_files || []).length, (bp?.designs || []).length, session.design_import?.status]);
  useEffect(() => { api.designFiles(sid).then(setView).catch(() => {}); }, [sid, sig]);
  if (!view) return null;
  const files = view.files || [];
  const total = files.reduce((n, f) => n + (f.size || 0), 0);
  const act = async (label, fn) => {
    setBusy(label); setError(null);
    try { setSession(await fn()); } catch (e) { setError(e.message); } finally { setBusy(""); setConfirm(""); }
  };
  return (
    <div className="df">
      <div className="df-head">
        <FolderOpen size={18} aria-hidden="true" />
        <div><strong>{view.folder}</strong><small>{files.length} file{files.length !== 1 ? "s" : ""} · {files.reduce((n, f) => n + f.screens, 0)} screens{total ? ` · ${kb(total)}` : ""}</small></div>
        {!frozen && <button type="button" className="btn-secondary sm" disabled={!!busy} onClick={onAdd}><ImageUp size={14} /> Add files</button>}
      </div>
      {files.length === 0 ? <p className="muted small">No files yet. Everything you upload is kept here as uploaded, and goes into the SDLC pack under UI-UX / designs / Source.</p> : (
        <ul className="df-list">
          {files.map((f) => (
            <li key={f.file_id}>
              <span className="df-thumbs">{f.design_ids.slice(0, 3).map((id) => <img key={id} src={fileUrl(`/identity/${sid}/designs/file/${id}`)} alt="" loading="lazy" />)}</span>
              <span className="df-meta"><b title={f.name}>{f.name}</b><small>{f.screens} screen{f.screens !== 1 ? "s" : ""}{f.size ? ` · ${kb(f.size)}` : ""}{f.uploaded_at ? ` · ${f.uploaded_at.slice(0, 10)}` : ""}{!f.kept ? " · original not kept (uploaded before files were stored)" : ""}</small></span>
              <span className="df-acts">
                {f.kept && <a className="icon-btn" href={api.designSourceUrl(sid, f.file_id)} title="Download the original" aria-label={`Download ${f.name}`}><Download size={14} /></a>}
                {!frozen && <button type="button" className="icon-btn" title="Read again with AI" aria-label={`Read ${f.name} again`} disabled={!!busy} onClick={() => act("Reading again…", () => api.rereadDesignFile(sid, f.file_id))}><RefreshCw size={14} /></button>}
                {!frozen && (confirm === f.file_id
                  ? <><button type="button" className="btn-danger sm" disabled={!!busy} onClick={() => act("Removing…", () => api.removeDesignFile(sid, f.file_id))}>Remove {f.screens} screen{f.screens !== 1 ? "s" : ""}</button><button type="button" className="link-btn" onClick={() => setConfirm("")}>Keep</button></>
                  : <button type="button" className="icon-btn" title="Remove this file and its screens" aria-label={`Remove ${f.name}`} disabled={!!busy} onClick={() => setConfirm(f.file_id)}><Trash2 size={14} /></button>)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Thumb({ sid, d, size = "md" }) {
  return (
    <span className={`di-thumb ${size} ${d.platform}`}>
      <img src={fileUrl(`/identity/${sid}/designs/file/${d.design_id}`)} alt={d.title || "Your design"} loading="lazy" />
    </span>
  );
}

export default function DesignImport({ session, setSession, frozen }) {
  const sid = session.session_id;
  const bp = session.brand?.blueprint;
  const designs = bp?.designs || [];
  const g = session.design_import;
  const running = g?.status === "running";
  const [cov, setCov] = useState(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState(null);
  const [drag, setDrag] = useState(false);
  const [showIgnored, setShowIgnored] = useState(false);
  const input = useRef(null);
  const byId = Object.fromEntries(designs.map((d) => [d.design_id, d]));
  const sig = JSON.stringify(designs.map((d) => [d.design_id, d.slot, d.status, d.kind])) + (bp?.mobile?.tabs || []).join() + session.brand?.palette?.primary;

  useEffect(() => { if (designs.length) api.designCoverage(sid).then(setCov).catch(() => {}); }, [sid, sig]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!running) return undefined;
    const t = setInterval(() => api.getSession(sid).then(setSession).catch(() => {}), 2000);
    return () => clearInterval(t);
  }, [running, sid]); // eslint-disable-line react-hooks/exhaustive-deps

  async function run(label, fn) {
    setBusy(label); setError(null);
    try { setSession(await fn()); } catch (e) { setError(e.message); } finally { setBusy(""); }
  }
  const upload = (files) => files?.length && run(`Uploading ${files.length} file${files.length > 1 ? "s" : ""}…`, () => api.importDesigns(sid, files));
  const update = (design_id, patch) => run("Saving…", () => api.updateDesign(sid, design_id, patch));

  const slots = cov?.slots || [];
  const business = designs.filter((d) => d.status === "business");
  const unsureLoose = designs.filter((d) => d.status === "unsure" && !d.slot);
  const ignored = designs.filter((d) => d.status === "ignored");
  const filled = slots.filter((s) => s.design_id).length;
  const hint = bp?.design_hints;

  const dropZone = !frozen && (
    <div className={"upload-zone di-drop" + (drag ? " drag" : "")}
      onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
      onDrop={(e) => { e.preventDefault(); setDrag(false); upload(e.dataTransfer.files); }}>
      <ImageUp size={22} aria-hidden="true" />
      <div>
        <strong>{designs.length ? "Add more designs" : "Already have designs? Drop them all here"}</strong>
        <p>Phone and web screenshots, mockup boards with several screens on one image, or a zip — all at once. GiveWings splits the boards, works out which screen is which, fills in the blueprint below and places every screen. You only check the sort.</p>
      </div>
      <button className="btn-primary" disabled={!!busy || running} onClick={() => input.current?.click()}><ImageUp size={14} /> Upload designs</button>
      <input ref={input} type="file" multiple hidden accept="image/png,image/jpeg,image/webp,image/gif,application/zip,.zip"
        onChange={(e) => { upload(e.target.files); e.target.value = ""; }} />
    </div>
  );

  return (
    <section className="di">
      <DesignFiles sid={sid} session={session} setSession={setSession} frozen={frozen} busy={busy || running} setBusy={setBusy} setError={setError} onAdd={() => input.current?.click()} />
      {dropZone}
      {busy && <p className="muted small">{busy}</p>}
      {error && <div className="error-banner" role="alert">{error}</div>}
      {running && (
        <div className="working" role="status"><span className="spinner" aria-hidden="true" />
          <div><strong>Reading your designs… {g.done}/{g.total}</strong><p className="muted small">Split into {g.total} screens. Each one is being read — platform, screen type, tabs, colours and type.</p></div>
        </div>
      )}

      {!running && designs.length > 0 && (
        <>
          <div className="di-summary">
            <Sparkles size={18} aria-hidden="true" />
            <div>
              <strong>{hint?.summary || `${designs.length} designs`}</strong>
              <p>The blueprint below was filled in from them. {filled} of {slots.length} places in the frame have your design; {slots.length - filled ? `${slots.length - filled} will be generated in your style` : "nothing needs generating"}{business.length ? `, and ${business.length} more screen${business.length > 1 ? "s are" : " is"} kept for the module designs` : ""}.</p>
            </div>
          </div>

          {cov?.palette_differs && hint?.colors?.primary && (
            <div className="di-colours">
              <Palette size={18} aria-hidden="true" />
              <div>
                <strong>Your designs use different colours from the brand</strong>
                <p>
                  <span className="di-sw" style={{ background: hint.colors.primary }} /> {hint.colors.primary} in the designs ·{" "}
                  <span className="di-sw" style={{ background: session.brand?.palette?.primary }} /> {session.brand?.palette?.primary} brand ({session.brand?.palette?.name})
                </p>
              </div>
              {!frozen && <button className="btn-secondary sm" disabled={!!busy} onClick={() => run("Updating colours…", () => api.useDesignColours(sid))}>Use the designs' colours</button>}
            </div>
          )}

          {slots.length - filled > 0 && (hint?.generate_ok ? (
            <div className="di-consent ok"><CheckCircle2 size={18} aria-hidden="true" />
              <div><strong>OK — the {slots.length - filled} empty places are generated in your style</strong>
                <p>You can still upload any of them above, or pick one of your designs in its card.</p></div>
              {!frozen && <button className="btn-secondary sm" disabled={!!busy} onClick={() => run("Saving…", () => api.designConsent(sid, false))}>Change my mind</button>}
            </div>
          ) : (
            <div className="di-consent"><Wand2 size={18} aria-hidden="true" />
              <div><strong>{slots.length - filled} place{slots.length - filled > 1 ? "s" : ""} in the frame have no design yet</strong>
                <p>Upload them above, or let GiveWings generate them in the look of your designs. You can't freeze the blueprint until you choose.</p></div>
              {!frozen && <button className="btn-primary sm" disabled={!!busy} onClick={() => run("Saving…", () => api.designConsent(sid, true))}><Wand2 size={14} /> Generate them in my style</button>}
            </div>
          ))}

          <h4 className="mini-head">Your frame</h4>
          <div className="di-slots">
            {slots.map((s) => {
              const d = byId[s.design_id];
              return (
                <div key={s.slot} className={"di-slot " + s.status}>
                  <div className="di-slot-img">
                    {d ? <Thumb sid={sid} d={d} /> : <span className="di-gen"><Wand2 size={18} /><small>Will be generated in your style</small></span>}
                  </div>
                  <div className="di-slot-body">
                    <strong>{s.label}</strong>
                    {s.status === "placed" && <span className="chip good"><CheckCircle2 size={11} /> Your design</span>}
                    {s.status === "unsure" && <span className="chip warn"><CircleHelp size={11} /> Check this</span>}
                    {s.status === "generate" && <span className="chip">Generated</span>}
                    {!frozen && (
                      <select aria-label={`Design for ${s.label}`} value={s.design_id} disabled={!!busy}
                        onChange={(e) => e.target.value ? update(e.target.value, { slot: s.slot }) : update(s.design_id, { slot: "", status: "business" })}>
                        <option value="">{s.design_id ? "— generate instead —" : "Pick one of your designs…"}</option>
                        {designs.filter((x) => x.status !== "ignored").map((x) => <option key={x.design_id} value={x.design_id}>{x.title || KIND[x.kind]} · {x.platform}</option>)}
                      </select>
                    )}
                    {s.status === "unsure" && !frozen && <button className="link-btn" onClick={() => update(s.design_id, { slot: s.slot })}>Yes, that's right</button>}
                  </div>
                </div>
              );
            })}
          </div>

          {unsureLoose.length > 0 && (
            <>
              <h4 className="mini-head">Not sure about these</h4>
              <div className="di-grid">
                {unsureLoose.map((d) => (
                  <div key={d.design_id} className="di-card unsure">
                    <Thumb sid={sid} d={d} size="sm" />
                    <div>
                      <strong>{d.title || "Unnamed screen"}</strong>
                      <small>{d.description}</small>
                      {!frozen && <div className="di-acts">
                        <select aria-label="What is this screen?" value={d.kind} onChange={(e) => update(d.design_id, { kind: e.target.value, status: "business" })}>
                          {Object.entries(KIND).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
                        </select>
                        <button className="link-btn" onClick={() => update(d.design_id, { status: "business" })}>Keep for modules</button>
                        <button className="link-btn" onClick={() => update(d.design_id, { status: "ignored" })}><EyeOff size={12} /> Not a screen</button>
                      </div>}
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}

          {business.length > 0 && (
            <>
              <h4 className="mini-head">Screens for the modules</h4>
              <p className="muted small">These are matched to the modules after Freeze Scope, and become their screens in UI/UX Design.</p>
              <div className="di-grid">
                {business.map((d) => (
                  <div key={d.design_id} className="di-card">
                    <Thumb sid={sid} d={d} size="sm" />
                    <div>
                      <strong>{d.title || KIND[d.kind]}</strong>
                      <small>{KIND[d.kind]} · {d.platform}{d.tab ? ` · ${d.tab} tab` : ""}</small>
                      {!frozen && <div className="di-acts"><button className="link-btn" onClick={() => update(d.design_id, { status: "ignored" })}><EyeOff size={12} /> Not a screen</button></div>}
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}

          {ignored.length > 0 && (
            <p className="muted small">{ignored.length} image{ignored.length > 1 ? "s" : ""} left out (not a screen). <button className="link-btn" onClick={() => setShowIgnored((v) => !v)}>{showIgnored ? "Hide" : "Show"}</button></p>
          )}
          {showIgnored && <div className="di-grid">{ignored.map((d) => (
            <div key={d.design_id} className="di-card muted"><Thumb sid={sid} d={d} size="sm" /><div><strong>{d.title}</strong>
              {!frozen && <button className="link-btn" onClick={() => update(d.design_id, { status: "business" })}>It is a screen</button>}</div></div>))}</div>}
        </>
      )}
    </section>
  );
}
