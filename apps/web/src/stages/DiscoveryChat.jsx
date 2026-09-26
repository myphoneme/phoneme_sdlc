import { useState } from "react";
import { api } from "../api.js";

export default function DiscoveryChat({ session, setSession }) {
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const messages = session?.messages || [];

  async function send() {
    if (!input.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const next = session
        ? await api.chat(session.session_id, input.trim())
        : await api.startSession(input.trim());
      setSession(next);
      setInput("");
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="stage-card">
      <h2>Discovery Chat</h2>
      <p className="stage-hint">
        Describe your product idea. The assistant will reflect it back and ask clarifying
        questions until scope is clear enough to research competitors.
      </p>

      <div className="chat-log">
        {messages.length === 0 && (
          <div className="chat-bubble bot-bubble">
            What are you building? Tell me who it's for and the core workflow.
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={"chat-bubble " + (m.role === "user" ? "user-bubble" : "bot-bubble")}>
            {m.text}
          </div>
        ))}
        {loading && (
          <div className="chat-bubble bot-bubble typing">
            <span className="typing-label">Thinking</span>
            <span className="typing-dot" />
            <span className="typing-dot" />
            <span className="typing-dot" />
          </div>
        )}
      </div>

      {error && <div className="error-banner">{error}</div>}

      <div className="chat-input-row">
        <textarea
          className="chat-textarea"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
          placeholder="Describe your product idea… (Shift+Enter for a new line)"
          disabled={loading}
          rows={3}
        />
        <button className="btn-primary" onClick={send} disabled={loading || !input.trim()}>
          Send
        </button>
      </div>

      {session?.concept_summary && (
        <div className="concept-summary-card">
          <div className="concept-summary-label">Concept locked in</div>
          <p>{session.concept_summary}</p>
          <p className="stage-hint">Moving to competitive research…</p>
        </div>
      )}
    </div>
  );
}
