import { useState } from "react";
import { api } from "../api.js";

const THEMES = [
  { id: "orange", label: "Phoneme Orange", swatch: "#D34817" },
  { id: "slate", label: "Slate", swatch: "#404040" },
  { id: "teal", label: "Teal", swatch: "#0F766E" },
];

export default function IdentityTheme({ session, setSession }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function pick(theme) {
    setLoading(true);
    setError(null);
    try {
      setSession(await api.selectTheme(session.session_id, theme));
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  if (!session) return null;

  return (
    <div className="stage-card">
      <h2>Brand Theme</h2>
      <p className="stage-hint">
        <strong>{session.selected_name}</strong> — pick a visual theme for the product.
      </p>

      {error && <div className="error-banner">{error}</div>}

      <div className="theme-grid">
        {THEMES.map((t) => (
          <button key={t.id} className="theme-swatch-btn" disabled={loading} onClick={() => pick(t.id)}>
            <span className="theme-swatch" style={{ background: t.swatch }} />
            {t.label}
          </button>
        ))}
      </div>
    </div>
  );
}
