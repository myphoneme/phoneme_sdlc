// GiveWings standard modules (mirror of apps/orchestrator/app/foundation.py).
// Every product is self-contained: these ship inside each product's own code.
export const STANDARD_NAMES = new Set([
  "Sign-in & Account",
  "Profile & Settings",
  "Admin Dashboard & Roles",
  "Security, Audit & Health",
]);

export const STANDARD_HINTS = {
  account: "e.g. Sign in with mobile OTP over WhatsApp; Google sign-in as an option; no passwords",
  profile: "e.g. Profile holds brand voice and preferred content formats; Hindi and English",
  admin: "e.g. Roles: Owner, Editor, Viewer; admins approve public campaigns",
  ops: "e.g. Data stays in India; alert the owner on WhatsApp; keep audit records for 3 years",
};

export const ACCESS = [
  { value: "signed_in", label: "Signed-in users", hint: "Only people with an account can use it." },
  { value: "mixed", label: "Public trial + sign-in", hint: "Visitors try part of it; the full feature needs an account." },
  { value: "public", label: "Public (no sign-in)", hint: "Landing pages, contests or free tools anyone can use." },
];
export const accessLabel = (v) => (ACCESS.find((a) => a.value === v) || ACCESS[0]).label;

export const isStandard = (m) => m?.kind === "standard";
