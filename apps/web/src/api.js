// Thin fetch wrapper over the FastAPI backend. Every wizard stage component
// talks to the backend only through these functions — no fetch() calls
// scattered through components — so the API surface stays in one place.
const BASE = "/api";

async function call(path, opts = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${opts.method || "GET"} ${path} failed (${res.status}): ${body}`);
  }
  return res.json();
}

const post = (path, body) => call(path, { method: "POST", body: JSON.stringify(body) });
const get = (path) => call(path);

export const api = {
  startSession: (initial_message) => post("/discovery/start", { initial_message }),
  chat: (session_id, message) => post("/discovery/chat", { session_id, message }),
  research: (session_id) => post("/discovery/research", { session_id, message: "" }),
  researchMore: (session_id, query) => post("/discovery/research/more", { session_id, query }),
  checkName: (session_id, name) => post("/discovery/name-check", { session_id, name }),
  selectName: (session_id, name) => post("/discovery/select-name", { session_id, name }),
  selectTheme: (session_id, theme) => post("/discovery/select-theme", { session_id, theme }),
  freeze: (session_id) => post("/wizard/freeze", { session_id }),
  generate: (session_id) => post("/wizard/generate", { session_id }),
  listRequirements: (session_id) => get(`/brdprd/${session_id}/requirements`),
  comment: (session_id, req_id, comment) => post(`/brdprd/${session_id}/comment`, { req_id, comment }),
  accept: (session_id, req_id) => post(`/brdprd/${session_id}/accept`, { req_id }),
  discard: (session_id, req_id) => post(`/brdprd/${session_id}/discard`, { req_id }),
  freezeRequirement: (session_id, req_id) => post(`/brdprd/${session_id}/freeze/${req_id}`, {}),
};
