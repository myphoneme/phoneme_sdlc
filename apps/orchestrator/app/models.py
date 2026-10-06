"""Pydantic request/response schemas for the wizard API."""
from typing import Optional
from pydantic import BaseModel, Field


class StartSessionRequest(BaseModel):
    initial_message: str = Field(..., description="The user's first description of their product idea")


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    text: str


class MarketLandscapeRow(BaseModel):
    category: str
    examples: str
    what_they_do: str
    limitations: str


class ResearchReport(BaseModel):
    """Structured, web-search-grounded competitive research — mirrors the
    depth of a real analyst pass (market landscape table, viability verdict,
    demand signals, legal/technical risk, phased feature recommendations,
    monetization model) rather than a bare list of company names.

    positioning_reframe / killer_feature (added 2026-09-26): the sharper,
    non-generic framing of the idea and its single standout differentiator
    -- the move that made the ChatGPT response in the user's comparison PDF
    the most build-ready of the three (it redefined the product's core
    object and named "Forward to Brain" as the central UX, rather than just
    listing competitors)."""
    market_landscape: list["MarketLandscapeRow"] = []
    viability_verdict: str = ""
    market_demand: list[str] = []
    risks: list[str] = []
    recommended_features: list[str] = []
    monetization: list[str] = []
    positioning_reframe: str = ""
    killer_feature: str = ""
    sources: list[str] = []


class ModuleFlow(BaseModel):
    """The key sequence flow for one module -- frontend + backend steps
    interleaved, e.g. 'user forwards a WhatsApp message -> webhook fires ->
    worker normalizes -> inbox UI shows it'. This is the human-in-the-loop
    gate between Freeze Scope and BRD/PRD drafting: per the 2026-09-28
    design-review thread, the BRD/PRD came out too abstract for an AI coding
    agent to build from directly because nobody had pinned down *how* each
    module actually works before the requirement text got drafted. Iterating
    this flow with the user first (comment -> regenerate -> accept, same
    loop as the BRD/PRD Manager) is what makes the eventual requirement
    text -- and any code generated from it -- concrete instead of generic."""
    module: str
    steps: list[str] = []
    revised_steps: Optional[list[str]] = None
    status: str = "Draft"  # Draft -> Revised (pending review) -> Approved
    standard: bool = False  # pre-approved GiveWings standard flow (read-only)


class ConceptBrief(BaseModel):
    """Structured, user-confirmed concept (2026-09-30 dry-run finding: the
    free-text CONCEPT SUMMARY silently dropped decisions the user had stated
    -- e.g. RelayReel's private/public choice -- and assumed an audience and
    market nobody confirmed). Every field is shown to the user and editable
    before research starts."""
    summary: str = ""
    target_users: str = ""
    core_workflow: str = ""
    input_channels: str = ""
    privacy_mode: str = ""
    market: str = ""
    platforms: str = ""
    must_haves: list[str] = []
    out_of_scope: list[str] = []
    assumptions: list[str] = []


class ModuleSpec(BaseModel):
    """One module of the frozen scope -- reviewed/edited by the user on the
    Freeze Scope screen before any flow is drafted."""
    name: str
    description: str = ""
    platform_core: bool = False  # legacy (pre 2026-10-01); see foundation.ensure
    merged_from: list[str] = []  # set when an AI consolidation proposed it
    # 2026-10-01: every product is self-contained. "standard" = GiveWings
    # standard module (sign-in, profile, admin, security/health) written
    # from a versioned template; "business" = specific to this product.
    kind: str = "business"
    standard_key: str = ""
    tailoring: str = ""  # BA notes that tailor a standard module
    # Who can use a business module: signed_in | public | mixed (public
    # trial/marketing part, full feature after sign-in).
    access: str = "signed_in"
    access_note: str = ""
    # 2026-10-01 boundary: where this module's flow starts and the outcome
    # it ends with, so flows stop retelling the whole product.
    starts_when: str = ""
    outcome: str = ""


class DomainCheck(BaseModel):
    domain: str
    status: str  # available | taken | unknown
    method: str = ""  # rdap | dns | error


class Palette(BaseModel):
    name: str = "Custom"
    mood: str = ""
    primary: str = "#FF7200"
    ink: str = "#171717"
    surface: str = "#FFF7F0"
    accent: str = "#0F766E"
    rationale: str = ""


class LogoConcept(BaseModel):
    id: str
    concept: str = ""
    svg: str


class ExperienceTokens(BaseModel):
    heading_font: str = "Space Grotesk"
    body_font: str = "IBM Plex Sans"
    radius: str = "rounded"  # sharp | rounded | soft
    density: str = "comfortable"  # comfortable | compact


class AuthSpec(BaseModel):
    methods: list[str] = ["email_password"]  # email_password | email_otp | mobile_otp | google | apple | sso
    register_fields: list[str] = ["Name", "Email", "Password"]
    onboarding: list[str] = []  # first-run steps after sign-up


class WebShell(BaseModel):
    nav: str = "sidebar"  # sidebar | top
    home: str = "dashboard"  # dashboard | feed | inbox


class MobileShell(BaseModel):
    tabs: list[str] = []  # bottom tabs, max 5
    share_target: bool = False  # appears in the phone's Share menu
    push: bool = True
    offline: bool = False


class ExperienceBlueprint(BaseModel):
    """2026-10-07: the portal's structure and look, decided and frozen at
    Identity with the brand, so UI/UX only fills module screens into an
    agreed frame (Phoneme SDLC: Brand & Experience)."""
    template_key: str = ""
    platforms: str = "web"  # web | mobile | both
    primary: str = "web"  # web | mobile
    tokens: ExperienceTokens = ExperienceTokens()
    public_pages: list[str] = []  # Landing, Pricing, About, Blog, Contact, Download app
    landing_sections: list[str] = []  # hero, promise, features, download, pricing, faq, cta (in order)
    public_features: str = ""  # what visitors may use without signing in
    auth: AuthSpec = AuthSpec()
    web: WebShell = WebShell()
    mobile: MobileShell = MobileShell()
    module_slots: dict[str, str] = {}  # module name -> sidebar item / tab (filled after Freeze Scope)
    notes: str = ""
    version: str = ""  # set when frozen: 1.0, 1.1 ...
    frozen: bool = False
    frozen_at: str = ""


class BrandIdentity(BaseModel):
    domains: list[DomainCheck] = []
    domain_checked_name: Optional[str] = None
    name_notes: str = ""
    chosen_domain: Optional[str] = None
    tagline_options: list[str] = []
    tagline: Optional[str] = None
    palette_options: list[Palette] = []
    palette: Optional[Palette] = None
    logo_options: list[LogoConcept] = []
    logo: Optional[LogoConcept] = None
    blueprint: Optional[ExperienceBlueprint] = None
    completed: bool = False


class GenerationItem(BaseModel):
    module: str
    req_id: str = ""
    status: str = "queued"  # queued | drafting | done | failed | skipped
    error: str = ""


class GenerationProgress(BaseModel):
    status: str = "idle"  # idle | running | done | failed
    total: int = 0
    done: int = 0
    items: list[GenerationItem] = []
    started_at: Optional[str] = None
    updated_at: Optional[str] = None


class SessionState(BaseModel):
    session_id: str
    messages: list[ChatMessage] = []
    concept_summary: Optional[str] = None
    concept_brief: Optional[ConceptBrief] = None
    companies: list[str] = []  # legacy flat list — kept as a fallback render path
    research: Optional[ResearchReport] = None
    suggested_names: list[str] = []
    selected_name: Optional[str] = None
    selected_theme: Optional[str] = None
    brand: BrandIdentity = BrandIdentity()
    modules: list[str] = []  # names only, kept in sync with module_specs for older callers
    module_specs: list[ModuleSpec] = []
    module_flows: list[ModuleFlow] = []
    generation: GenerationProgress = GenerationProgress()
    requirement_archive: list["ArchivedRequirementSet"] = []
    consistency: Optional["ConsistencyReport"] = None
    scope_revision: int = 0
    # 2026-10-04: frozen-set baselines (BRD/PRD v1.0, v1.1 ...) -- each
    # one is a Change Log row in the exported document.
    baselines: list["Baseline"] = []
    # Stage 8 -- Technical Design (stack charter, HLD + per-module LLD)
    stack: Optional["StackCharter"] = None
    tech_designs: list["TechDesign"] = []
    tech_generation: GenerationProgress = GenerationProgress()
    # Stage 9 -- UI/UX screens in the product's brand
    ui_modules: list["UIModule"] = []
    ui_generation: GenerationProgress = GenerationProgress()
    # discovery -> confirm -> research -> identity -> freeze -> flow -> generating -> manager
    stage: str = "discovery"


class ChatTurnRequest(BaseModel):
    session_id: str
    message: str


class ResearchMoreRequest(BaseModel):
    session_id: str
    query: str


class NameCheckRequest(BaseModel):
    session_id: str
    name: str


class SelectNameRequest(BaseModel):
    session_id: str
    name: str


class SelectThemeRequest(BaseModel):
    session_id: str
    theme: str


class FreezeRequest(BaseModel):
    session_id: str


class GenerateRequest(BaseModel):
    session_id: str


class JourneyStep(BaseModel):
    title: str
    detail: str = ""
    actor: str = ""


class AcceptanceCriterion(BaseModel):
    id: str = ""
    criterion: str
    priority: str = "Must"  # Must | Should | Could


class ArchivedRequirementSet(BaseModel):
    """A full set of requirements set aside when scope was redefined --
    kept for reference/audit, never silently thrown away."""
    archived_at: str
    reason: str = ""
    modules: list[str] = []
    requirements: list["Requirement"] = []


class ConsistencyIssue(BaseModel):
    documents: list[str] = []  # req_ids involved
    problem: str
    suggestion: str = ""


class ConsistencyReport(BaseModel):
    checked_at: Optional[str] = None
    verdict: str = ""
    issues: list[ConsistencyIssue] = []


class RequirementDoc(BaseModel):
    """Structured, stakeholder-readable requirement (2026-09-30 review:
    prose paragraphs laced with API paths and table names were unreadable
    and pre-empted Technical Design). Business language only -- the
    technical mapping (services, endpoints, data model) is produced later,
    in the Technical Design stage, from this frozen document."""
    summary: str = ""
    actors: list[str] = []
    journey: list[JourneyStep] = []
    business_rules: list[str] = []
    acceptance_criteria: list[AcceptanceCriterion] = []
    out_of_scope: list[str] = []
    open_questions: list[str] = []
    receives_from: str = ""
    hands_off_to: str = ""


class Requirement(BaseModel):
    req_id: str
    module: str
    title: str
    body: str  # plain-text rendering of `doc` (legacy/fallback + AI context)
    status: str = "Draft"  # Draft -> Review -> Approved -> Frozen
    revised_body: Optional[str] = None
    doc: Optional[RequirementDoc] = None
    revised_doc: Optional[RequirementDoc] = None
    revised_title: Optional[str] = None
    status_before_revision: Optional[str] = None
    standard_version: str = ""  # set for GiveWings standard modules
    # 2026-10-04: open questions must be answered (or explicitly deferred)
    # by the product owner before a document can be approved or frozen.
    thread: list["ReviewMessage"] = []
    decisions: list["Decision"] = []


class ReviewMessage(BaseModel):
    role: str  # owner | assistant
    text: str
    at: str = ""


class Decision(BaseModel):
    question: str
    answer: str = ""
    deferred: bool = False
    at: str = ""


class AnswerItem(BaseModel):
    question: str
    answer: str = ""
    defer: bool = False


class AnswersRequest(BaseModel):
    req_id: str
    answers: list[AnswerItem]


class CommentRequest(BaseModel):
    req_id: str
    comment: str


class AcceptRequest(BaseModel):
    req_id: str


class FlowCommentRequest(BaseModel):
    session_id: str
    module: str
    comment: str


class FlowModuleRequest(BaseModel):
    session_id: str
    module: str


class ModuleBoundaryRequest(BaseModel):
    session_id: str
    module: str
    starts_when: str = ""
    outcome: str = ""


class FlowFreezeRequest(BaseModel):
    session_id: str


class SessionRequest(BaseModel):
    session_id: str


class ConfirmBriefRequest(BaseModel):
    session_id: str
    brief: ConceptBrief


class DomainCheckRequest(BaseModel):
    session_id: str
    name: str


class ChooseRequest(BaseModel):
    """Generic 'pick this value' request for the identity sub-steps."""
    session_id: str
    value: str


class PaletteRequest(BaseModel):
    session_id: str
    palette: Palette


class BlueprintTemplateRequest(BaseModel):
    session_id: str
    template_key: str


class BlueprintSaveRequest(BaseModel):
    session_id: str
    blueprint: ExperienceBlueprint


class LogoChoiceRequest(BaseModel):
    session_id: str
    logo_id: str


class ModulesSaveRequest(BaseModel):
    session_id: str
    modules: list[ModuleSpec]


class FlowStepsUpdateRequest(BaseModel):
    session_id: str
    module: str
    steps: list[str]


class ConsolidateRequest(BaseModel):
    session_id: str
    instruction: str = ""
    target: Optional[int] = None


class ReopenScopeRequest(BaseModel):
    session_id: str
    reason: str = ""


class StackCharter(BaseModel):
    """Phoneme Technical Stack Charter -- confirmed once per product and
    referenced by every later document instead of being re-decided."""
    product_type: str = ""
    frontend: str = ""
    backend: str = ""
    data: str = ""
    ai_ml: str = ""
    hosting: str = ""
    integrations: str = ""
    devops: str = ""
    security: str = ""
    conventions: str = ""
    confirmed: bool = False
    confirmed_at: str = ""
    changelog: list[str] = []


class TDComponent(BaseModel):
    name: str
    responsibility: str = ""


class TDField(BaseModel):
    name: str
    type: str = ""
    notes: str = ""


class TDEntity(BaseModel):
    name: str
    description: str = ""
    fields: list[TDField] = []


class TDApi(BaseModel):
    method: str = "GET"
    path: str
    purpose: str = ""
    request: str = ""
    response: str = ""


class TDNfr(BaseModel):
    requirement: str
    approach: str = ""


class TechDoc(BaseModel):
    """One Technical Design section: the HLD (system architecture) or one
    module's LLD -- same shape so both share the review loop."""
    overview: str = ""
    components: list[TDComponent] = []
    data_model: list[TDEntity] = []
    apis: list[TDApi] = []
    sequence: list[str] = []
    edge_cases: list[str] = []
    integrations: list[str] = []
    security: list[str] = []
    nfr: list[TDNfr] = []
    risks: list[str] = []
    open_questions: list[str] = []


class TechDesign(BaseModel):
    td_id: str
    module: str  # "System architecture (HLD)" for the HLD
    req_id: str = ""  # traceability back to the BRD/PRD
    title: str = ""
    kind: str = "lld"  # hld | lld
    status: str = "Draft"
    doc: Optional[TechDoc] = None
    revised_doc: Optional[TechDoc] = None
    status_before_revision: Optional[str] = None
    thread: list[ReviewMessage] = []
    decisions: list[Decision] = []


class UIBlock(BaseModel):
    type: str = "text"  # header|text|list|cards|form|buttons|table|tabs|stats|notice|steps|media
    # public site blocks (2026-10-06): hero|promise|features|pricing|faq|cta
    title: str = ""
    eyebrow: str = ""  # small caps label above a site section heading
    note: str = ""  # auth forms: text before the switch link ("Don't have an account?")
    text: str = ""
    items: list[str] = []
    columns: list[str] = []
    rows: list[list[str]] = []
    actions: list[str] = []
    targets: list[str] = []  # screen each action leads to (parallel to actions)


class UIScreen(BaseModel):
    screen_id: str = ""
    name: str
    purpose: str = ""
    route: str = ""
    layout: str = "app"  # app | public | auth | mobile | image (uploaded design)
    blocks: list[UIBlock] = []
    states: list[str] = []
    source: str = "ai"  # ai | upload | kit (GiveWings public-site kit)
    asset_id: str = ""  # uploaded file id when source == upload


class UIDoc(BaseModel):
    screens: list[UIScreen] = []
    notes: list[str] = []  # design decisions / deferred items
    open_questions: list[str] = []


class UIModule(BaseModel):
    ui_id: str
    module: str
    req_id: str = ""
    title: str = ""
    kind: str = "screens"
    status: str = "Draft"
    doc: Optional[UIDoc] = None
    revised_doc: Optional[UIDoc] = None
    status_before_revision: Optional[str] = None
    thread: list[ReviewMessage] = []
    decisions: list[Decision] = []


class ItemCommentRequest(BaseModel):
    item_id: str
    comment: str


class ItemRequest(BaseModel):
    item_id: str


class ItemAnswersRequest(BaseModel):
    item_id: str
    answers: list[AnswerItem]


class ScreenEditRequest(BaseModel):
    item_id: str
    screen_id: str
    name: Optional[str] = None
    purpose: Optional[str] = None


class ScreenMoveRequest(BaseModel):
    item_id: str
    screen_id: str
    direction: int = 1  # -1 up, +1 down


class StackSaveRequest(BaseModel):
    stack: StackCharter


class Baseline(BaseModel):
    """A frozen, versioned set of documents for one SDLC stage."""
    doc_type: str = "brdprd"  # brdprd | techdesign | uiux
    version: str
    at: str
    description: str = ""
    snapshot: dict[str, str] = {}  # doc id -> content hash



SessionState.model_rebuild()
ArchivedRequirementSet.model_rebuild()

