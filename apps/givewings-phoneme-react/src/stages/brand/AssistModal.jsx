// "Ask AI" for one Brand Studio section (2026-10-13): say what to change in
// plain words; the AI answers, applies changes to this section only (the live
// preview updates behind the dialog) and the last change can be undone.
import { useEffect, useRef, useState } from "react";
import { Send, Sparkles, Undo2, X } from "lucide-react";
import { api } from "../../api.js";

const IDEAS = {
  name: ["Give me a shorter tagline", "Make the tagline more playful"],
  colours: ["Make it warmer", "Use a calmer primary colour", "Make the dark theme deeper"],
  logo: ["Use two letters on the favicon", "Use the logo itself as the favicon"],
  theme: ["Make it feel more premium", "Use rounder corners and a friendlier font", "Make it more compact"],
  landing: ["Rewrite the headline for creators", "Add plans and pricing", "Make the FAQ answer privacy questions"],
  web: ["Use a top menu", "Start on a feed instead of a dashboard"],
  mobile: ["Rename the tabs for a diary app", "Turn off push notifications"],
  standard: ["Centre the logo on sign-in", "Add Continue with Apple"],
};

export default function AssistModal({ session, setSession, section, label, onClose }) {
  const sid = session.session_id;
  const thread = session.brand?.assist?.[section] || [];
  const [text, setText] = useState("");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState(null);
  const end = useRef(null);
  useEffect(() => { end.current?.scrollIntoView({ block: "end" }); }, [thread.length, busy]);
  const send = async (msg) => {
    const m = (msg ?? text).trim();
    if (!m) return;
    setBusy("Thinking…"); setError(null); setText("");
    try { setSession(await api.assist(sid, section, m)); } catch (e) { setError(e.message); setText(m); } finally { setBusy(""); }
  };
  const undo = async () => {
    setBusy("Undoing…"); setError(null);
    try { setSession(await api.assistUndo(sid, section)); } catch (e) { setError(e.message); } finally { setBusy(""); }
  };
  const lastUndo = [...thread].reverse().find((m) => m.role === "ai" && m.undo);
  return (
    <div className="bs-assist" role="dialog" aria-modal="false" aria-labelledby="as-title">
      <div className="bs-assist-head">
        <Sparkles size={16} aria-hidden="true" />
        <strong id="as-title">Ask AI · {label}</strong>
        <button type="button" className="icon-btn" onClick={onClose} aria-label="Close"><X size={15} /></button>
      </div>
      <div className="bs-assist-body">
        {thread.length === 0 && <p className="muted small">Tell the AI what to change in this section, in your own words. Changes show in the live preview straight away, and you can undo them.</p>}
        {thread.map((m, i) => (
          <div key={i} className={"bs-msg " + m.role}>
            <p>{m.text}</p>
            {m.applied?.length > 0 && <ul className="bs-applied">{m.applied.map((x) => <li key={x}>{x}</li>)}</ul>}
            {m.undone && <small className="muted">Undone</small>}
          </div>
        ))}
        {busy && <div className="bs-msg ai"><p className="muted">{busy}</p></div>}
        <div ref={end} />
      </div>
      {error && <div className="error-banner sm" role="alert">{error}</div>}
      <div className="bs-assist-ideas">{(IDEAS[section] || []).map((x) => <button key={x} type="button" className="opt-chip sm" disabled={!!busy} onClick={() => send(x)}>{x}</button>)}</div>
      <div className="bs-assist-input">
        <textarea rows={2} value={text} placeholder="e.g. make the headline speak to students" onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }} disabled={!!busy} />
        <div className="bs-assist-acts">
          {lastUndo && <button type="button" className="btn-secondary sm" disabled={!!busy} onClick={undo}><Undo2 size={13} /> Undo last change</button>}
          <button type="button" className="btn-primary sm" disabled={!!busy || !text.trim()} onClick={() => send()}><Send size={13} /> Send</button>
        </div>
      </div>
    </div>
  );
}
