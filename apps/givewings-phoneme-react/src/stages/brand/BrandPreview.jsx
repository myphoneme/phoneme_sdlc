// Live preview for the Brand Studio (2026-10-13). Everything is drawn here in
// the browser from the draft palette and blueprint, so every change shows the
// moment it is made — in light and dark, on the web and on a phone.
import { Bell, Check, ChevronRight, Home, Image as ImageIcon, Lock, Plus, Search, Share2, User } from "lucide-react";
import { svgSrc, themeVars, useFonts } from "./kit.js";

const PAGE_TYPES = ["List", "Detail", "Form", "Empty state", "Settings"];

function Mark({ session, size = 22 }) {
  const logo = session.brand?.logo;
  const name = session.selected_name || "Your product";
  return logo
    ? <img className="bv-logo" src={svgSrc(logo.svg)} alt={`${name} logo`} style={{ height: size }} />
    : <b className="bv-word" style={{ fontSize: size * 0.8 }}>{name}</b>;
}

function Browser({ session, favicon, path = "", children }) {
  const domain = session.brand?.chosen_domain || `${(session.selected_name || "product").toLowerCase().replace(/[^a-z0-9]/g, "")}.com`;
  return (
    <div className="bv-browser">
      <div className="bv-tabs">
        <span className="bv-tab"><img src={favicon} alt="" width="14" height="14" />{session.selected_name || "New product"}{session.brand?.tagline ? ` — ${session.brand.tagline}` : ""}</span>
      </div>
      <div className="bv-url"><Lock size={10} /> {domain}{path}</div>
      <div className="bv-page">{children}</div>
    </div>
  );
}

function Phone({ tabs = [], active = 0, title, children, session }) {
  return (
    <div className="bv-phone">
      <div className="bv-status"><span>9:41</span><span>●●● ▮</span></div>
      <div className="bv-phead"><Mark session={session} size={18} />{title && <strong>{title}</strong>}<Bell size={15} /></div>
      <div className="bv-pbody">{children}</div>
      {tabs.length > 0 && (
        <div className="bv-tabbar">
          {tabs.slice(0, 5).map((t, i) => <span key={t} className={i === active ? "on" : ""}><i />{t}</span>)}
        </div>
      )}
    </div>
  );
}

const Btn = ({ kind = "primary", children }) => <span className={`bv-btn ${kind}`}>{children}</span>;
const Card = ({ title, children }) => <div className="bv-card">{title && <h5>{title}</h5>}{children}</div>;
const Rows = ({ n = 3, img = false }) => (
  <ul className="bv-rows">{Array.from({ length: n }, (_, i) => (
    <li key={i}>{img && <span className="bv-thumb"><ImageIcon size={12} /></span>}<span><b>{["Weekly summary", "New item saved", "Draft ready to review", "Shared with team"][i % 4]}</b><small>{["2 min ago", "Today", "Yesterday", "Mon"][i % 4]}</small></span><span className="bv-dot" /></li>
  ))}</ul>
);

/* ---------- section previews ---------- */
function ThemeSheet({ session, title }) {
  return (
    <div className="bv-sheet">
      {title && <span className="bv-mode">{title}</span>}
      <div className="bv-sw">{["--b-p", "--b-ink", "--b-tint", "--b-acc", "--b-bg"].map((v) => <i key={v} style={{ background: `var(${v})` }} />)}</div>
      <h1>{session.selected_name || "Your product"}</h1>
      <p className="bv-lead">{session.brand?.tagline || "Your tagline goes here"}</p>
      <p>Body text reads like this — clear, calm and easy on the eyes for long sessions.</p>
      <div className="bv-row"><Btn>Primary action</Btn><Btn kind="secondary">Secondary</Btn><Btn kind="ghost">Link</Btn></div>
      <div className="bv-row"><span className="bv-input">Email address</span><span className="bv-chip">Active</span><span className="bv-chip acc">New</span></div>
      <Card title="A card"><Rows n={2} /></Card>
      <div className="bv-alert">Accent highlights draw the eye to one thing at a time.</div>
    </div>
  );
}

function NamePreview({ session, favicon }) {
  const b = session.brand || {};
  return (
    <>
      <Browser session={session} favicon={favicon}>
        <div className="bv-hero sm"><Mark session={session} size={30} /><h1>{b.tagline || "Your tagline"}</h1><div className="bv-row center"><Btn>Get started</Btn><Btn kind="secondary">Sign in</Btn></div></div>
      </Browser>
      <div className="bv-serp">
        <small>{b.chosen_domain || "domain not chosen yet"}</small>
        <b>{session.selected_name || "Product name"} — {b.tagline || "tagline"}</b>
        <p>{(session.concept_summary || "").slice(0, 150) || "Search results show your name, domain and tagline together."}</p>
      </div>
    </>
  );
}

function LogoPreview({ session, favicon }) {
  return (
    <>
      <div className="bv-logo-pair">
        <div className="bv-logo-tile light"><Mark session={session} size={44} /></div>
        <div className="bv-logo-tile dark"><Mark session={session} size={44} /></div>
      </div>
      <div className="bv-favs">{[16, 32, 48, 64].map((s) => <span key={s}><img src={favicon} alt="" width={s} height={s} /><small>{s}px</small></span>)}
        <span className="bv-appicon"><img src={favicon} alt="" /><small>App icon</small></span></div>
      <Browser session={session} favicon={favicon}><div className="bv-hero sm"><Mark session={session} size={26} /></div></Browser>
    </>
  );
}

const SECTION_LABEL = { hero: "Hero", promise: "Promise", features: "How it works", download: "Download the app", pricing: "Plans & pricing", faq: "FAQ", cta: "Closing call to action" };

function LandingPreview({ session, bp, favicon, phone }) {
  const b = session.brand || {};
  const parts = (bp?.landing_sections || ["hero"]).map((k) => {
    switch (k) {
      case "hero": return <div key={k} className="bv-hero"><span className="bv-eyebrow">{(bp?.public_features || "New").slice(0, 40)}</span><h1>{b.tagline || session.selected_name}</h1><p>{(session.concept_summary || "What the product does, in one sentence.").slice(0, 140)}</p><div className="bv-row center"><Btn>Get started free</Btn><Btn kind="secondary">See how it works</Btn></div><div className="bv-hero-media"><ImageIcon size={22} /></div></div>;
      case "promise": return <div key={k} className="bv-promise">{["Fast to start", "Private by default", "Works everywhere"].map((x) => <span key={x}><Check size={12} /> {x}</span>)}</div>;
      case "features": return <div key={k} className="bv-band"><h2>How it works</h2><div className="bv-grid3">{["Capture", "Organise", "Share"].map((x, i) => <Card key={x} title={`${i + 1}. ${x}`}><p className="bv-mut">A short line on this step.</p></Card>)}</div></div>;
      case "download": return <div key={k} className="bv-band tint"><h2>Get the app</h2><div className="bv-row center"><span className="bv-store">App Store</span><span className="bv-store">Google Play</span><span className="bv-qr" /></div></div>;
      case "pricing": return <div key={k} className="bv-band"><h2>Plans</h2><div className="bv-grid3">{["Free", "Pro", "Team"].map((x, i) => <div key={x} className={"bv-card plan" + (i === 1 ? " hl" : "")}><h5>{x}</h5><b className="bv-price">{["₹0", "₹299", "₹999"][i]}</b><Btn kind={i === 1 ? "primary" : "secondary"}>Choose</Btn></div>)}</div></div>;
      case "faq": return <div key={k} className="bv-band"><h2>Questions</h2>{["Is my data private?", "Can I cancel any time?"].map((q) => <div key={q} className="bv-faq">{q}<ChevronRight size={13} /></div>)}</div>;
      case "cta": return <div key={k} className="bv-cta"><h2>Ready when you are</h2><Btn>Create your account</Btn></div>;
      default: return <div key={k} className="bv-band"><h2>{SECTION_LABEL[k] || k}</h2></div>;
    }
  });
  const nav = <div className="bv-pubnav"><Mark session={session} size={20} />{!phone && <span className="bv-links">{(bp?.public_pages || []).filter((p) => p !== "Landing").slice(0, 4).map((p) => <span key={p}>{p}</span>)}</span>}<span className="bv-row"><Btn kind="ghost">Sign in</Btn>{!phone && <Btn>Get started</Btn>}</span></div>;
  if (phone) return <div className="bv-phone landing"><div className="bv-status"><span>9:41</span><span>●●● ▮</span></div>{nav}<div className="bv-pbody">{parts}</div></div>;
  return <Browser session={session} favicon={favicon}><div className="bv-zoom">{nav}{parts}<div className="bv-foot">© {session.selected_name} · Privacy · Terms</div></div></Browser>;
}

function PageBody({ type, session }) {
  switch (type) {
    case "dashboard": return <><div className="bv-stats">{["Items", "This week", "Shared"].map((s, i) => <div key={s} className="bv-stat"><small>{s}</small><b>{[128, 24, 9][i]}</b></div>)}</div><Card title="Latest"><Rows n={3} /></Card></>;
    case "feed": return <>{[0, 1].map((i) => <Card key={i}><div className="bv-feedimg"><ImageIcon size={18} /></div><b>{["A saved reel", "An article"][i]}</b><p className="bv-mut">Summary appears here.</p></Card>)}</>;
    case "inbox": case "List": return <><div className="bv-row"><span className="bv-input grow"><Search size={12} /> Search</span><Btn><Plus size={12} /> New</Btn></div><Card><Rows n={4} img /></Card></>;
    case "Detail": return <><div className="bv-feedimg tall"><ImageIcon size={20} /></div><h4>Item title</h4><p className="bv-mut">Details, notes and status for one record.</p><div className="bv-row"><Btn>Edit</Btn><Btn kind="secondary"><Share2 size={12} /> Share</Btn></div></>;
    case "Form": return <Card title="Create"><span className="bv-label">Title</span><span className="bv-input block" /><span className="bv-label">Category</span><span className="bv-input block" /><div className="bv-row"><Btn>Save</Btn><Btn kind="ghost">Cancel</Btn></div></Card>;
    case "Empty state": return <div className="bv-empty"><span className="bv-empty-ico"><Plus size={18} /></span><b>Nothing here yet</b><p className="bv-mut">Add your first item to get started.</p><Btn>Add item</Btn></div>;
    case "Settings": return <Card title="Settings">{["Notifications", "Dark mode", "Language"].map((x, i) => <div key={x} className="bv-set">{x}<span className={"bv-switch" + (i !== 2 ? " on" : "")} /></div>)}</Card>;
    default: return null;
  }
}

function AppShell({ session, bp, children, active = 0 }) {
  const nav = (session.module_specs || []).filter((m) => m.kind !== "standard").map((m) => m.name).slice(0, 5);
  const items = ["Home", ...(nav.length ? nav : ["Library", "Create", "Reports"])];
  if (bp?.web?.nav === "top") {
    return <div className="bv-app top"><div className="bv-topnav"><Mark session={session} size={18} />{items.map((x, i) => <span key={x} className={i === active ? "on" : ""}>{x}</span>)}<span className="bv-avatar"><User size={12} /></span></div><div className="bv-content">{children}</div></div>;
  }
  return (
    <div className="bv-app">
      <div className="bv-side"><Mark session={session} size={18} />{items.map((x, i) => <span key={x} className={i === active ? "on" : ""}><Home size={12} /> {x}</span>)}</div>
      <div className="bv-main"><div className="bv-topbar"><b>{items[active]}</b><span className="bv-avatar"><User size={12} /></span></div><div className="bv-content">{children}</div></div>
    </div>
  );
}

function WebPreview({ session, bp, favicon }) {
  return (
    <>
      <Browser session={session} favicon={favicon} path="/app"><div className="bv-zoom"><AppShell session={session} bp={bp}><PageBody type={bp?.web?.home || "dashboard"} session={session} /></AppShell></div></Browser>
      <h6 className="bv-h6">Page catalogue — every module page is drawn from these</h6>
      <div className="bv-catalogue">
        {PAGE_TYPES.map((t) => <figure key={t}><div className="bv-mini"><AppShell session={session} bp={bp} active={1}><PageBody type={t} session={session} /></AppShell></div><figcaption>{t}</figcaption></figure>)}
      </div>
    </>
  );
}

function MobilePreview({ session, bp }) {
  const tabs = bp?.mobile?.tabs?.length ? bp.mobile.tabs : ["Home", "Library", "Create", "Profile"];
  const pages = [["dashboard", 0, tabs[0]], ["List", Math.min(1, tabs.length - 1), tabs[1]], ["Detail", Math.min(1, tabs.length - 1), "Item"], ["Form", Math.min(2, tabs.length - 1), tabs[2] || "Create"]];
  return (
    <div className="bv-phones">
      {pages.map(([type, act, title]) => <figure key={type}><Phone session={session} tabs={tabs} active={act} title={title}><PageBody type={type} session={session} /></Phone><figcaption>{type === "dashboard" ? "Home" : type}</figcaption></figure>)}
      {bp?.mobile?.share_target && (
        <figure><div className="bv-phone share"><div className="bv-status"><span>9:41</span><span>●●● ▮</span></div><div className="bv-pbody dim" /><div className="bv-sheetup"><b>Share to</b><div className="bv-row"><span className="bv-shareapp"><Mark session={session} size={14} /></span><span className="bv-shareapp ghost" /><span className="bv-shareapp ghost" /></div><Btn>Save to {session.selected_name}</Btn></div></div><figcaption>Share sheet</figcaption></figure>
      )}
    </div>
  );
}

export function StandardPreview({ session, bp, placement = "left", phone }) {
  const methods = bp?.auth?.methods || ["email_password"];
  const auth = (title, fields, cta, extra) => (
    <div className={"bv-auth " + placement}>
      <div className="bv-auth-logo"><Mark session={session} size={20} /></div>
      <h4>{title}</h4>
      {fields.map((f) => <span key={f}><span className="bv-label">{f}</span><span className="bv-input block" /></span>)}
      <Btn>{cta}</Btn>
      {extra}
    </div>
  );
  const cards = [
    ["Sign in", auth("Welcome back", methods.includes("mobile_otp") ? ["Mobile number"] : ["Email", "Password"], methods.includes("mobile_otp") ? "Send code" : "Sign in", methods.includes("google") && <span className="bv-social">Continue with Google</span>)],
    ["Create account", auth("Create your account", (bp?.auth?.register_fields || ["Name", "Email"]).slice(0, 3), "Create account")],
    ["Forgot password", auth("Reset your password", ["Email"], "Send reset link")],
    ["Change password", auth("Change password", ["Current password", "New password"], "Update password")],
    ["Profile & settings", <div className="bv-auth left"><div className="bv-auth-logo"><Mark session={session} size={18} /></div><div className="bv-prof"><span className="bv-avatar lg"><User size={16} /></span><b>Your name</b><small className="bv-mut">you@example.com</small></div><PageBody type="Settings" /></div>],
  ];
  return <div className={"bv-standard" + (phone ? " phone" : "")}>{cards.map(([t, c]) => <figure key={t}>{c}<figcaption>{t}</figcaption></figure>)}</div>;
}

export default function BrandPreview({ section, session, palette, bp, mode, device, favicon }) {
  useFonts([bp?.tokens?.heading_font, bp?.tokens?.body_font]);
  const p = palette || { primary: "#C2410C", ink: "#171717", surface: "#FFF7F0", accent: "#0F766E" };
  const placement = session.brand?.logo_placement || "left";
  const phone = device === "phone";
  const wrap = (m, child, label) => <div className={`bv bv-${m}`} style={themeVars(p, m, bp?.tokens)}>{label && <span className="bv-mode">{label}</span>}{child}</div>;
  let body;
  if (section === "colours") {
    return <div className="bv-split">{wrap("light", <ThemeSheet session={session} />, "Light")}{wrap("dark", <ThemeSheet session={session} />, "Dark")}</div>;
  } else if (section === "name") body = <NamePreview session={session} favicon={favicon} />;
  else if (section === "logo") body = <LogoPreview session={session} favicon={favicon} />;
  else if (section === "theme") body = <><ThemeSheet session={session} /><h6 className="bv-h6">Standard modules inherit this theme and your logo</h6><StandardPreview session={session} bp={bp} placement={placement} phone={phone} /></>;
  else if (section === "landing" || section === "designs") body = <LandingPreview session={session} bp={bp} favicon={favicon} phone={phone} />;
  else if (section === "web") body = <WebPreview session={session} bp={bp} favicon={favicon} />;
  else if (section === "mobile") body = <MobilePreview session={session} bp={bp} />;
  else if (section === "standard") body = <StandardPreview session={session} bp={bp} placement={placement} phone={phone} />;
  return wrap(mode, body);
}

