import { useState } from "react";
import { Check } from "lucide-react";
import { api } from "../api.js";

// Theme ids are what the backend stores; swatches/labels are presentation.
const THEMES = [
  { id: "orange", label: "GiveWings Orange", note: "Warm, energetic, on-brand", colors: ["#ff7200", "#171717", "#fff0e5"] },
  { id: "slate", label: "Slate", note: "Calm, enterprise, neutral", colors: ["#404040", "#1c2027", "#eef0f2"] },
  { id: "teal", label: "Teal", note: "Fresh, trustworthy, clinical", colors: ["#0f766e", "#12302d", "#e3f3f1"] },
];

export default function IdentityTheme({ session, setSession }) {
  const [loading, setLoading] = useState(false);
  const [picked, setPicked] = useState(null);
  const [error, setError] = useState(null);

  async function pick(theme) {
    setPicked(theme);
    setLoading(true);
    setError(null);
    try {
      setSession(await api.selectTheme(session.session_id, theme));
    } catch (e) {
      setError(e.message);
      setPicked(null);
    } finally {
      setLoading(false);
    }
  }

  if (!session) return null;

  return (
    <div className="identity">
      <p className="lead">
        Theme for <strong>{session.selected_name}</strong>. It carries through every generated document and screen.
      </p>

      {error && <div className="error-banner" role="alert">{error}</div>}

      <div className="theme-grid">
        {THEMES.map((t) => (
          <button key={t.id} className={"theme-card" + (picked === t.id ? " selected" : "")} disabled={loading} onClick={() => pick(t.id)}>
            <span className="theme-preview" aria-hidden="true">
              <span className="theme-bar" style={{ background: t.colors[1] }}><i style={{ background: t.colors[0] }} /></span>
              <span className="theme-body" style={{ background: t.colors[2] }}>
                <i style={{ background: t.colors[0] }} /><i /><i />
              </span>
            </span>
            <span className="theme-meta">
              <strong>{t.label}</strong>
              <small>{t.note}</small>
            </span>
            <span className="theme-check" aria-hidden="true"><Check size={14} strokeWidth={3} /></span>
          </button>
        ))}
      </div>
    </div>
  );
}
