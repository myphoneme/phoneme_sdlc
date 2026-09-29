import React, { useEffect, useMemo, useState } from 'react';
import { ArrowRight, ArrowUpRight, Bell, Check, ChevronDown, ChevronRight, CircleHelp, Command, FileText, Layers3, Lightbulb, Menu, MessageCircle, MoreHorizontal, Plus, Rocket, Search, Sparkles, UsersRound, WandSparkles, X, Zap, BarChart3, ClipboardCheck, Target, PenLine } from 'lucide-react';
import DiscoveryChat from './stages/DiscoveryChat.jsx';
import ResearchCard from './stages/ResearchCard.jsx';
import IdentityTheme from './stages/IdentityTheme.jsx';
import Generating from './stages/Generating.jsx';
import ModuleFlowReview from './stages/ModuleFlowReview.jsx';
import BrdPrdManager from './stages/BrdPrdManager.jsx';
import { api } from './api.js';

// The real backend's 7-stage wizard (apps/orchestrator/app/models.py
// SessionState.stage) -- NOT the mockup's invented 4-stage
// ['Idea','Plan','Build','Launch'] taxonomy. Every place that used to render
// 4 stages now adapts to these 7.
const STAGES = ['discovery', 'research', 'identity', 'freeze', 'flow', 'generating', 'manager'];
const STAGE_LABELS = ['Discovery Chat', 'Research', 'Identity & Theme', 'Freeze Scope', 'Flow Design', 'Generating', 'BRD/PRD Manager'];

// The backend persists sessions durably; a browser refresh has no way to
// know which session_id to resume unless we remember it ourselves. Only the
// id lives in localStorage -- never the actual session state, the backend
// is always the source of truth. Same key/behavior as the original
// apps/web/src/App.jsx this was merged from, so an in-flight wizard survives
// this merge unchanged.
const SESSION_STORAGE_KEY = 'phoneme_sdlc_session_id';

const aiActions = [
  { icon: Lightbulb, title: 'Validate an idea', subtitle: 'Turn a concept into a plan' },
  { icon: FileText, title: 'Build a PRD', subtitle: 'Generate a detailed brief' },
  { icon: Search, title: 'Find market insights', subtitle: 'Get instant research' },
  { icon: Rocket, title: 'Create a launch plan', subtitle: 'Go to market with confidence' },
];

function IconBox({ icon: Icon, tone = 'orange' }) { return <span className={`icon-box ${tone}`}><Icon size={22} strokeWidth={2} /></span>; }

// Deterministic (not random) so a card doesn't change color on every
// re-render -- picks a decorative tone from the session_id, purely cosmetic.
const TONES = ['coral', 'blue', 'green', 'violet'];
function toneFor(id) {
  let h = 0;
  for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) >>> 0;
  return TONES[h % TONES.length];
}

function timeAgo(iso) {
  if (!iso) return 'just now';
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return 'just now';
  const mins = Math.floor((Date.now() - then) / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h`;
  const days = Math.floor(hrs / 24);
  if (days < 30) return `${days}d`;
  const months = Math.floor(days / 30);
  if (months < 12) return `${months}mo`;
  return `${Math.floor(months / 12)}y`;
}

// stage -> the honest status badge (reuses the already-contrast-fixed
// .status / .status.in-progress / .status.early-stage classes; no fourth
// variant was needed since 'generating'/'manager' reuse the on-track look).
function statusFor(stage) {
  if (stage === 'discovery') return { label: 'Early stage', cls: 'early-stage' };
  if (stage === 'generating' || stage === 'manager') return { label: 'Ready for BRD/PRD', cls: '' };
  return { label: 'In progress', cls: 'in-progress' };
}

function ProductCard({ session, onOpen }) {
  const idx = Math.max(0, STAGES.indexOf(session.stage));
  const label = STAGE_LABELS[idx] || session.stage;
  const progress = Math.round(((idx + 1) / STAGES.length) * 100);
  const status = statusFor(session.stage);
  const tone = toneFor(session.session_id);
  const initial = (session.name || '?').trim().charAt(0).toUpperCase() || '?';
  return (
    <article className="product-card" onClick={() => onOpen(session.session_id)} tabIndex={0}
      onKeyDown={e => (e.key === 'Enter' || e.key === ' ') && onOpen(session.session_id)}
      aria-label={`Open ${session.name}, currently in ${label}`}>
      <div className={`product-art ${tone}`}>
        <span className="product-mark">{initial}</span>
        <button className="icon-button more" aria-label={`Details for ${session.name}`}
          onClick={e => { e.stopPropagation(); onOpen(session.session_id); }}>
          <MoreHorizontal size={20} />
        </button>
      </div>
      <div className="product-copy"><h3>{session.name}</h3><p>Started {timeAgo(session.created_at)} ago</p></div>
      <div className="stage-progress" aria-label={`Stage ${idx + 1} of ${STAGES.length}: ${label}`}>
        <div className="stage-progress-track">
          {STAGES.map((s, i) => <span key={s} className={`stage-progress-seg${i <= idx ? ' done' : ''}`} />)}
        </div>
        <span className="stage-progress-label">{label}</span>
      </div>
      <p className="completion"><strong>{progress}%</strong> through the wizard <small>Last updated {timeAgo(session.updated_at)} ago</small></p>
      <div className="product-footer" style={{ justifyContent: 'flex-end' }}>
        <span className={`status ${status.cls}`}><span /> {status.label}</span>
      </div>
    </article>
  );
}

function Dashboard({ sessions, loading, error, onOpen, onCreate, onRetry }) {
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState('All');
  const [showAll, setShowAll] = useState(false);
  const [modal, setModal] = useState(null); // 'new' | null
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    const listener = e => { if (e.key === 'Escape') setModal(null); };
    window.addEventListener('keydown', listener);
    return () => window.removeEventListener('keydown', listener);
  }, []);

  const filtered = useMemo(() => sessions.filter(s => {
    const matchesFilter =
      filter === 'All' ||
      (filter === 'In progress' && ['research', 'identity', 'freeze', 'flow', 'generating'].includes(s.stage)) ||
      (filter === 'Early stage' && s.stage === 'discovery');
    return matchesFilter && s.name.toLowerCase().includes(query.toLowerCase());
  }), [sessions, query, filter]);

  const visible = showAll ? filtered : filtered.slice(0, 4);

  const counts = useMemo(() => ({
    discovery: sessions.filter(s => s.stage === 'discovery').length,
    inDesign: sessions.filter(s => ['research', 'identity', 'freeze', 'flow'].includes(s.stage)).length,
    readyForBrdPrd: sessions.filter(s => ['generating', 'manager'].includes(s.stage)).length,
  }), [sessions]);
  const total = sessions.length;

  function submitNew(e) {
    e.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) return;
    onCreate(trimmed, description.trim());
    setName('');
    setDescription('');
    setModal(null);
  }

  return (
    <>
      <header className="topbar">
        <div className="top-inner">
          <a className="wordmark" href="#home" aria-label="GiveWings home"><span className="wing-mark"><Zap size={20} fill="currentColor" /></span><span>GiveWings</span></a>
          <span className="nav-divider" />
          <nav className={`main-nav ${mobileOpen ? 'open' : ''}`} aria-label="Main navigation">
            {['Home', 'Ideas', 'Products', 'Roadmap', 'Team', 'Resources'].map((item, i) => (
              <a key={item} className={i === 0 ? 'active' : ''} href={i === 0 ? '#home' : i === 2 ? '#products' : '#home'}
                onClick={() => setMobileOpen(false)}>{item}</a>
            ))}
          </nav>
          <div className="header-actions">
            <label className="global-search">
              <Search size={19} />
              <input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search products..." aria-label="Search products" />
              <kbd>⌘ K</kbd>
            </label>
            <button className="header-icon" aria-label="Notifications"><Bell size={20} /><span className="notification-dot" /></button>
            <button className="profile" aria-label="Profile settings"><span>YOU</span><ChevronDown size={15} /></button>
            <button className="mobile-toggle" onClick={() => setMobileOpen(!mobileOpen)} aria-label="Toggle menu" aria-expanded={mobileOpen}>
              {mobileOpen ? <X /> : <Menu />}
            </button>
          </div>
        </div>
      </header>

      <main id="home" className="dashboard">
        <div className="intro-grid">
          <section className="welcome">
            <div className="eyebrow">YOUR PRODUCT WORKSPACE</div>
            <h1>Turn bold ideas<br />into real products.</h1>
            <p>Plan, build, and launch with clarity — all in one place.</p>
          </section>
          <section className="hero" aria-label="From idea to impact">
            <div className="hero-content">
              <span className="hero-label">ORCHESTRATE</span>
              <h2>From idea to impact</h2>
              <p>Take an idea through Discovery, Research, Identity, Flow Design and BRD/PRD drafting with GiveWings.</p>
              <button className="hero-button" onClick={() => setModal('new')}>Create new idea <ArrowRight size={17} /></button>
            </div>
            <div className="hero-art" aria-hidden="true">
              <svg viewBox="0 0 400 210" preserveAspectRatio="none"><defs><linearGradient id="heroFill" x1="0" y1="1" x2=".8" y2="0"><stop stopColor="#FF7200" stopOpacity=".03" /><stop offset="1" stopColor="#FF9345" stopOpacity=".9" /></linearGradient></defs><path d="M0 207 C90 204 128 175 173 136 S234 130 277 83 S318 97 354 12 L354 210 Z" fill="url(#heroFill)" /><path d="M0 207 C90 204 128 175 173 136 S234 130 277 83 S318 97 354 12" fill="none" stroke="#ffba87" strokeWidth="2" /></svg>
              <span className="hero-star">✦</span>
            </div>
          </section>
          <aside className="ai-card">
            <div className="ai-heading"><div><IconBox icon={Sparkles} /><h2>GiveWings AI</h2></div><span className="beta">BETA</span><p>Your always-on product partner.</p></div>
            <div className="ai-list">
              {aiActions.map(({ icon, title, subtitle }) => (
                <button key={title} className="ai-action" onClick={() => setModal('new')}>
                  <IconBox icon={icon} /><span><strong>{title}</strong><small>{subtitle}</small></span><ChevronRight size={18} />
                </button>
              ))}
            </div>
          </aside>
        </div>

        <div className="below-grid">
          <div className="left-column">
            <section className="metrics" aria-label="Workspace metrics">
              <article className="metric">
                <IconBox icon={Lightbulb} />
                <div className="metric-copy"><span>Ideas in discovery</span><strong>{counts.discovery}</strong>
                  <small>{total ? `${Math.round((counts.discovery / total) * 100)}% of ${total} total` : 'No ideas yet'}</small>
                </div>
              </article>
              <article className="metric">
                <IconBox icon={Layers3} />
                <div className="metric-copy"><span>In requirements &amp; design</span><strong>{counts.inDesign}</strong>
                  <small>{total ? `${Math.round((counts.inDesign / total) * 100)}% of ${total} total` : 'No ideas yet'}</small>
                </div>
              </article>
              <article className="metric">
                <IconBox icon={ClipboardCheck} />
                <div className="metric-copy"><span>Ready for BRD/PRD</span><strong>{counts.readyForBrdPrd}</strong>
                  <small>{total ? `${Math.round((counts.readyForBrdPrd / total) * 100)}% of ${total} total` : 'No ideas yet'}</small>
                </div>
              </article>
            </section>

            <section id="products" className="products-section">
              <div className="section-title">
                <div><h2>Your products</h2><p>Keep every idea moving forward.</p></div>
                {filtered.length > 4 && (
                  <button className="text-link" onClick={() => setShowAll(s => !s)}>
                    {showAll ? 'Show fewer' : 'View all products'} <ArrowRight size={16} />
                  </button>
                )}
              </div>
              <div className="product-toolbar">
                <div className="filters" role="group" aria-label="Filter products">
                  {['All', 'In progress', 'Early stage'].map(label => (
                    <button key={label} className={filter === label ? 'selected' : ''} onClick={() => setFilter(label)}>{label}</button>
                  ))}
                </div>
                <button className="add-small" onClick={() => setModal('new')}><Plus size={17} /> New product</button>
              </div>

              {loading ? (
                <div className="empty-state"><Sparkles size={25} /><h3>Loading your products…</h3></div>
              ) : error ? (
                <div className="empty-state"><CircleHelp size={25} /><h3>Couldn't reach the backend</h3><p>{error}</p><button onClick={onRetry}>Try again</button></div>
              ) : visible.length ? (
                <div className="products-grid">
                  {visible.map(s => <ProductCard key={s.session_id} session={s} onOpen={onOpen} />)}
                </div>
              ) : (
                <div className="empty-state">
                  <Search size={25} />
                  <h3>{sessions.length ? 'No products found' : 'No products yet'}</h3>
                  <p>{sessions.length ? 'Try another search or filter.' : 'Create your first idea to get started.'}</p>
                  <button onClick={() => (sessions.length ? (setQuery(''), setFilter('All')) : setModal('new'))}>
                    {sessions.length ? 'Clear filters' : 'Create new idea'}
                  </button>
                </div>
              )}
            </section>
          </div>
        </div>
      </main>

      {modal === 'new' && (
        <div className="modal-backdrop" onMouseDown={e => e.target === e.currentTarget && setModal(null)}>
          <div className="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title">
            <button className="modal-close" onClick={() => setModal(null)} aria-label="Close"><X size={19} /></button>
            <div className="modal-symbol"><Lightbulb /></div>
            <h2 id="modal-title">Start a new product</h2>
            <p className="modal-lead">Capture the idea now. GiveWings will run it through Discovery Chat first.</p>
            <form onSubmit={submitNew}>
              <label>Product name<input autoFocus required maxLength={60} value={name} onChange={e => setName(e.target.value)} placeholder="e.g. HealthPulse" /></label>
              <label>What does it do?<textarea rows="3" maxLength={240} value={description} onChange={e => setDescription(e.target.value)} placeholder="A short description of your product idea" /></label>
              <div className="modal-actions">
                <button type="button" className="secondary" onClick={() => setModal(null)}>Cancel</button>
                <button className="primary" type="submit">Create product <ArrowRight size={16} /></button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}

function WizardView({ session, setSession, requirements, setRequirements, onBack }) {
  const stage = session?.stage || 'discovery';
  const stageIndex = STAGES.indexOf(stage);
  return (
    <div className="wizard-shell">
      <header className="app-header">
        <div className="logo-wordmark">
          <span className="logo-phon">PHON</span>
          <span className="logo-eme">EME</span>
        </div>
        <div className="header-title">SDLC Platform — Idea to BRD/PRD</div>
        <button type="button" className="btn-secondary" onClick={onBack}>← Back to dashboard</button>
      </header>

      <nav className="stage-tracker">
        {STAGE_LABELS.map((label, i) => (
          <div key={label} className={'stage-pip' + (i <= stageIndex ? ' done' : '')}>
            <span className="stage-pip-dot" />
            {label}
          </div>
        ))}
      </nav>

      <main className="app-main">
        {stage === 'discovery' && <DiscoveryChat session={session} setSession={setSession} />}
        {stage === 'research' && <ResearchCard session={session} setSession={setSession} />}
        {stage === 'identity' && <IdentityTheme session={session} setSession={setSession} />}
        {stage === 'freeze' && (
          <Generating session={session} setSession={setSession} setRequirements={setRequirements} freezeOnly />
        )}
        {stage === 'flow' && <ModuleFlowReview session={session} setSession={setSession} />}
        {stage === 'generating' && (
          <Generating session={session} setSession={setSession} setRequirements={setRequirements} />
        )}
        {stage === 'manager' && (
          <BrdPrdManager session={session} requirements={requirements} setRequirements={setRequirements} />
        )}
      </main>
    </div>
  );
}

export default function App() {
  const [view, setView] = useState('dashboard'); // 'dashboard' | 'wizard'
  const [sessions, setSessions] = useState([]);
  const [sessionsLoading, setSessionsLoading] = useState(true);
  const [sessionsError, setSessionsError] = useState('');
  const [activeSession, setActiveSession] = useState(null); // full SessionState from backend
  const [requirements, setRequirements] = useState([]);
  const [rehydrating, setRehydrating] = useState(true);
  const [toast, setToast] = useState('');

  const notify = msg => setToast(msg);
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(''), 3500);
    return () => clearTimeout(t);
  }, [toast]);

  const refreshSessions = () => {
    setSessionsLoading(true);
    setSessionsError('');
    return api.listSessions()
      .then(rows => setSessions(rows || []))
      .catch(err => setSessionsError(err.message || 'Request failed'))
      .finally(() => setSessionsLoading(false));
  };

  // Dashboard always shows live data from the backend, never a fabricated
  // starter list or localStorage cache of products.
  useEffect(() => { refreshSessions(); }, []);

  // On mount: if a previous session_id is stored, ask the backend for it and
  // resume exactly where the user left off (real current stage) instead of
  // landing on a blank dashboard -- same rehydration this had in
  // apps/web/src/App.jsx before the merge, just also switching `view` since
  // this app now has a dashboard view to fall back to when there's nothing
  // to resume.
  useEffect(() => {
    const storedId = localStorage.getItem(SESSION_STORAGE_KEY);
    if (!storedId) {
      setRehydrating(false);
      return;
    }
    api
      .getSession(storedId)
      .then(restored => {
        setActiveSession(restored);
        setView('wizard');
        return api.listRequirements(storedId).catch(() => []);
      })
      .then(reqs => setRequirements(reqs || []))
      .catch(() => {
        // Session no longer exists server-side (e.g. a DB reset) -- drop the
        // stale id rather than repeatedly failing to resume it.
        localStorage.removeItem(SESSION_STORAGE_KEY);
      })
      .finally(() => setRehydrating(false));
  }, []);

  // Keep localStorage in sync with whichever session is active so the next
  // refresh (or accidental tab close) resumes it -- cleared when the user
  // deliberately goes back to the dashboard (see backToDashboard).
  useEffect(() => {
    if (activeSession?.session_id) {
      localStorage.setItem(SESSION_STORAGE_KEY, activeSession.session_id);
    }
  }, [activeSession?.session_id]);

  async function openSession(sessionId) {
    try {
      const full = await api.getSession(sessionId);
      const reqs = await api.listRequirements(sessionId).catch(() => []);
      setActiveSession(full);
      setRequirements(reqs || []);
      setView('wizard');
    } catch (err) {
      notify('Could not open that product — try again.');
    }
  }

  async function createProduct(name, description) {
    const initialMessage = description ? `${name}: ${description}` : name;
    try {
      const session = await api.startSession(initialMessage);
      setActiveSession(session);
      setRequirements([]);
      setView('wizard');
      notify(`${name} added to your product workspace`);
      refreshSessions();
    } catch (err) {
      notify('Could not start that idea — try again.');
    }
  }

  function backToDashboard() {
    setView('dashboard');
    setActiveSession(null);
    localStorage.removeItem(SESSION_STORAGE_KEY);
    refreshSessions();
  }

  if (rehydrating) {
    return (
      <div className="wizard-shell">
        <main className="app-main"><div className="stage-card"><p className="stage-hint">Resuming your session…</p></div></main>
      </div>
    );
  }

  return (
    <>
      {view === 'dashboard' && (
        <Dashboard
          sessions={sessions}
          loading={sessionsLoading}
          error={sessionsError}
          onOpen={openSession}
          onCreate={createProduct}
          onRetry={refreshSessions}
        />
      )}
      {view === 'wizard' && (
        <WizardView
          session={activeSession}
          setSession={setActiveSession}
          requirements={requirements}
          setRequirements={setRequirements}
          onBack={backToDashboard}
        />
      )}
      {toast && <div className="toast" role="status"><Sparkles size={18} />{toast}<button onClick={() => setToast('')} aria-label="Dismiss"><X size={15} /></button></div>}
    </>
  );
}
