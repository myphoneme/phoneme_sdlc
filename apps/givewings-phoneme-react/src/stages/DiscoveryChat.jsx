import { useEffect, useRef, useState } from "react";
import { ArrowUp, CheckCircle2, Sparkles } from "lucide-react";
import { api } from "../api.js";

function Avatar({ role }) {
  return role === "user"
    ? <span className="msg-avatar user" aria-hidden="true">YOU</span>
    : <span className="msg-avatar bot" aria-hidden="true"><Sparkles size={16} /></span>;
}

export default function DiscoveryChat({ session, setSession }) {
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const logRef = useRef(null);

  const messages = session?.messages || [];

  // Keep the newest message in view as the conversation grows.
  useEffect(() => {
    const el = logRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages.length, loading]);

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
    <div className="chat">
      <div className="chat-log" ref={logRef} aria-live="polite">
        {messages.length === 0 && (
          <div className="msg bot">
            <Avatar role="bot" />
            <div className="msg-body">
              <span className="msg-author">GiveWings AI</span>
              <div className="msg-bubble">What are you building? Tell me who it's for and the core workflow.</div>
            </div>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={"msg " + (m.role === "user" ? "user" : "bot")}>
            <Avatar role={m.role} />
            <div className="msg-body">
              <span className="msg-author">{m.role === "user" ? "You" : "GiveWings AI"}</span>
              <div className="msg-bubble">{m.text}</div>
            </div>
          </div>
        ))}
        {loading && (
          <div className="msg bot">
            <Avatar role="bot" />
            <div className="msg-body">
              <span className="msg-author">GiveWings AI</span>
              <div className="msg-bubble typing" aria-label="GiveWings AI is thinking">
                <span className="typing-dot" /><span className="typing-dot" /><span className="typing-dot" />
              </div>
            </div>
          </div>
        )}
      </div>

      {error && <div className="error-banner" role="alert">{error}</div>}

      {session?.concept_summary ? (
        <div className="callout success">
          <CheckCircle2 size={20} aria-hidden="true" />
          <div>
            <strong>Concept locked in</strong>
            <p>{session.concept_summary}</p>
            <small>Moving on to market research…</small>
          </div>
        </div>
      ) : (
        <div className="composer">
          <label className="sr-only" htmlFor="discovery-input">Your reply</label>
          <textarea
            id="discovery-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
            placeholder={messages.length ? "Answer the question, or add more detail…" : "Describe your product idea…"}
            disabled={loading}
            rows={3}
          />
          <div className="composer-bar">
            <span className="composer-hint"><kbd>Enter</kbd> to send · <kbd>Shift</kbd>+<kbd>Enter</kbd> for a new line</span>
            <button className="btn-primary" onClick={send} disabled={loading || !input.trim()}>
              {loading ? "Thinking…" : "Send"} <ArrowUp size={16} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
