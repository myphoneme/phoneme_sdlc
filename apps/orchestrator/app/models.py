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
    platform_core: bool = False


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


class Requirement(BaseModel):
    req_id: str
    module: str
    title: str
    body: str
    status: str = "Draft"  # Draft -> Review -> Approved -> Frozen
    revised_body: Optional[str] = None


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
