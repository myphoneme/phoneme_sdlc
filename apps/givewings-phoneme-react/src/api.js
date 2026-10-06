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
    let detail = body;
    try { detail = JSON.parse(body).detail || body; } catch { /* keep raw text */ }
    const err = new Error(typeof detail === "string" ? detail : `${opts.method || "GET"} ${path} failed (${res.status})`);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

const post = (path, body) => call(path, { method: "POST", body: JSON.stringify(body) });
const get = (path) => call(path);

// Generic client for the post-BRD stages (Technical Design, UI/UX) that
// share one review engine on the server (apps/orchestrator/app/review.py).
const stageApi = (kind) => ({
  generate: (sid) => post(`/${kind}/${sid}/generate`, {}),
  comment: (sid, item_id, comment) => post(`/${kind}/${sid}/comment`, { item_id, comment }),
  accept: (sid, item_id) => post(`/${kind}/${sid}/accept`, { item_id }),
  discard: (sid, item_id) => post(`/${kind}/${sid}/discard`, { item_id }),
  answers: (sid, item_id, answers) => post(`/${kind}/${sid}/answers`, { item_id, answers }),
  freeze: (sid, item_id) => post(`/${kind}/${sid}/freeze/${item_id}`, {}),
  unfreeze: (sid, item_id) => post(`/${kind}/${sid}/unfreeze/${item_id}`, {}),
  baseline: (sid) => get(`/${kind}/${sid}/baseline`),
  createBaseline: (sid) => post(`/${kind}/${sid}/baseline`, {}),
});

export const fileUrl = (path) => `${BASE}${path}`;

export const api = {
  techdesign: stageApi("techdesign"),
  uiux: stageApi("uiux"),
  suggestStack: (sid) => post(`/techdesign/${sid}/stack/suggest`, {}),
  saveStack: (sid, stack) => post(`/techdesign/${sid}/stack`, { stack }),
  confirmStack: (sid) => post(`/techdesign/${sid}/stack/confirm`, {}),
  uploadDesigns: async (sid, ui_id, files, mode = "add") => {
    const fd = new FormData();
    [...files].forEach((f) => fd.append("files", f));
    fd.append("mode", mode);
    const res = await fetch(`${BASE}/uiux/${sid}/upload/${ui_id}`, { method: "POST", body: fd });
    if (!res.ok) {
      let d = await res.text();
      try { d = JSON.parse(d).detail || d; } catch { /* raw */ }
      throw new Error(typeof d === "string" ? d : `upload failed (${res.status})`);
    }
    return res.json();
  },
  updateScreen: (sid, item_id, screen_id, patch) => post(`/uiux/${sid}/screens/update`, { item_id, screen_id, ...patch }),
  moveScreen: (sid, item_id, screen_id, direction) => post(`/uiux/${sid}/screens/move`, { item_id, screen_id, direction }),
  removeScreen: (sid, item_id, screen_id) => post(`/uiux/${sid}/screens/remove`, { item_id, screen_id }),
  brdBaseline: (sid) => get(`/brdprd/${sid}/baseline`),
  brdCreateBaseline: (sid) => post(`/brdprd/${sid}/baseline`, {}),
  listSessions: () => get("/discovery"),
  startSession: (initial_message) => post("/discovery/start", { initial_message }),
  getSession: (session_id) => get(`/discovery/${session_id}`),
  chat: (session_id, message) => post("/discovery/chat", { session_id, message }),
  research: (session_id) => post("/discovery/research", { session_id, message: "" }),
  researchMore: (session_id, query) => post("/discovery/research/more", { session_id, query }),
  summarize: (session_id) => post("/discovery/summarize", { session_id }),
  confirmBrief: (session_id, brief) => post("/discovery/confirm", { session_id, brief }),
  researchDone: (session_id) => post("/discovery/research/done", { session_id }),
  checkDomains: (session_id, name) => post("/identity/domains", { session_id, name }),
  chooseName: (session_id, value) => post("/identity/name", { session_id, value }),
  chooseDomain: (session_id, value) => post("/identity/domain", { session_id, value }),
  genTaglines: (session_id) => post("/identity/taglines", { session_id }),
  chooseTagline: (session_id, value) => post("/identity/tagline", { session_id, value }),
  genPalettes: (session_id) => post("/identity/palettes", { session_id }),
  choosePalette: (session_id, palette) => post("/identity/palette", { session_id, palette }),
  genLogos: (session_id) => post("/identity/logos", { session_id }),
  chooseLogo: (session_id, logo_id) => post("/identity/logo", { session_id, logo_id }),
  completeIdentity: (session_id) => post("/identity/complete", { session_id }),
  saveModules: (session_id, modules) => post("/wizard/modules/save", { session_id, modules }),
  confirmModules: (session_id) => post("/wizard/modules/confirm", { session_id }),
  updateFlow: (session_id, module, steps) => post("/wizard/flows/update", { session_id, module, steps }),
  retryGenerate: (session_id) => post("/wizard/generate/retry", { session_id }),
  checkName: (session_id, name) => post("/discovery/name-check", { session_id, name }),
  selectName: (session_id, name) => post("/discovery/select-name", { session_id, name }),
  selectTheme: (session_id, theme) => post("/discovery/select-theme", { session_id, theme }),
  freeze: (session_id) => post("/wizard/freeze", { session_id }),
  generateFlows: (session_id) => post("/wizard/flows/generate", { session_id }),
  commentFlow: (session_id, module, comment) => post("/wizard/flows/comment", { session_id, module, comment }),
  acceptFlow: (session_id, module) => post("/wizard/flows/accept", { session_id, module }),
  discardFlow: (session_id, module) => post("/wizard/flows/discard", { session_id, module }),
  freezeFlows: (session_id) => post("/wizard/flows/freeze", { session_id }),
  setBoundary: (session_id, module, starts_when, outcome) => post("/wizard/modules/boundary", { session_id, module, starts_when, outcome }),
  redraftFlow: (session_id, module) => post("/wizard/flows/redraft", { session_id, module }),
  suggestBoundaries: (session_id) => post("/wizard/modules/suggest-boundaries", { session_id }),
  generate: (session_id) => post("/wizard/generate", { session_id }),
  listRequirements: (session_id) => get(`/brdprd/${session_id}/requirements`),
  comment: (session_id, req_id, comment) => post(`/brdprd/${session_id}/comment`, { req_id, comment }),
  accept: (session_id, req_id) => post(`/brdprd/${session_id}/accept`, { req_id }),
  answerQuestions: (session_id, req_id, answers) => post(`/brdprd/${session_id}/answers`, { req_id, answers }),
  discard: (session_id, req_id) => post(`/brdprd/${session_id}/discard`, { req_id }),
  consolidateModules: (session_id, instruction, target) => post("/wizard/modules/consolidate", { session_id, instruction, target }),
  reopenScope: (session_id, reason) => post("/wizard/reopen-scope", { session_id, reason }),
  unfreeze: (session_id, req_id) => post(`/brdprd/${session_id}/unfreeze/${req_id}`, {}),
  checkConsistency: (session_id) => post(`/brdprd/${session_id}/consistency`, {}),
  restructure: (session_id, req_id) => post(`/brdprd/${session_id}/restructure/${req_id}`, {}),
  freezeRequirement: (session_id, req_id) => post(`/brdprd/${session_id}/freeze/${req_id}`, {}),
};
