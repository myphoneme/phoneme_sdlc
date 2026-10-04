"""
Word exports in Phoneme's SDLC document format (2026-10-04).

Structure follows the Phoneme BRD/PRD and Technical Design standards:
cover page with the product's own brand (name, tagline, palette), Document
Control (PHN-<CODE>-<YEAR>-..), Change Log from the stage baselines,
numbered sections, and a blank Authorization (sign-off) table. Phoneme
Solutions Pvt. Ltd. appears only as the submitting company, never merged
into the product's brand.
"""
import io
import re
from datetime import datetime, timezone

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

COMPANY = "Phoneme Solutions Pvt. Ltd."
AUTHOR = "GiveWings — Phoneme SDLC Platform"


def _rgb(hexstr: str, default: str = "171717") -> RGBColor:
    h = (hexstr or default).lstrip("#")
    if not re.fullmatch(r"[0-9a-fA-F]{6}", h):
        h = default
    return RGBColor.from_string(h.upper())


def product_code(state) -> str:
    name = re.sub(r"[^A-Za-z]", "", state.selected_name or "PROD").upper()
    return (name[:4] or "PROD")


def _shade(cell, hexstr: str) -> None:
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hexstr.lstrip("#"))
    tcPr.append(shd)


class Builder:
    def __init__(self, state, doc_title: str, ident: str):
        self.state = state
        pal = state.brand.palette if state.brand and state.brand.palette else None
        self.primary = _rgb(pal.primary if pal else "FF7200")
        self.primary_hex = (pal.primary if pal else "#FF7200").lstrip("#")
        self.ink = _rgb(pal.ink if pal else "171717")
        self.doc = Document()
        self.doc_title = doc_title
        self.ident = ident
        st = self.doc.styles["Normal"]
        st.font.name = "Calibri"
        st.font.size = Pt(10.5)
        for lvl, size in ((1, 16), (2, 13), (3, 11.5)):
            h = self.doc.styles[f"Heading {lvl}"]
            h.font.color.rgb = self.primary if lvl == 1 else self.ink
            h.font.size = Pt(size)
            h.font.name = "Calibri"
        sec = self.doc.sections[0]
        footer = sec.footer.paragraphs[0]
        footer.text = f"{ident}  ·  Submitted by {COMPANY}  ·  Confidential"
        footer.runs[0].font.size = Pt(8)

    # --- primitives
    def h(self, text: str, level: int = 1):
        return self.doc.add_heading(text, level=level)

    def p(self, text: str = "", bold: bool = False, italic: bool = False, size=None):
        para = self.doc.add_paragraph()
        run = para.add_run(text or "")
        run.bold, run.italic = bold, italic
        if size:
            run.font.size = Pt(size)
        return para

    def bullets(self, items, style: str = "List Bullet"):
        for it in items:
            if str(it).strip():
                self.doc.add_paragraph(str(it), style=style)

    def numbered(self, items):
        for i, it in enumerate(items, 1):
            para = self.doc.add_paragraph()
            r = para.add_run(f"{i}.  ")
            r.bold = True
            para.add_run(str(it))

    def table(self, header: list[str], rows: list[list[str]], widths=None):
        t = self.doc.add_table(rows=1, cols=len(header))
        t.style = "Table Grid"
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        for i, txt in enumerate(header):
            c = t.rows[0].cells[i]
            c.text = ""
            run = c.paragraphs[0].add_run(txt)
            run.bold = True
            run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
            _shade(c, self.primary_hex)
        for row in rows:
            cells = t.add_row().cells
            for i, txt in enumerate(row):
                cells[i].text = str(txt or "")
        if widths:  # fractions of the 6.3in text width
            t.autofit = False
            for row in t.rows:
                for i, w in enumerate(widths):
                    row.cells[i].width = Inches(6.3 * w)
        self.doc.add_paragraph()
        return t

    def page_break(self):
        self.doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    # --- standard front matter
    def cover(self, subtitle: str, version: str):
        s = self.state
        for _ in range(6):
            self.doc.add_paragraph()
        t = self.doc.add_paragraph()
        t.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = t.add_run(s.selected_name or "Product")
        r.bold = True
        r.font.size = Pt(34)
        r.font.color.rgb = self.primary
        if s.brand and s.brand.tagline:
            tg = self.doc.add_paragraph()
            tg.alignment = WD_ALIGN_PARAGRAPH.CENTER
            rr = tg.add_run(s.brand.tagline)
            rr.italic = True
            rr.font.size = Pt(14)
            rr.font.color.rgb = self.ink
        self.doc.add_paragraph()
        d = self.doc.add_paragraph()
        d.alignment = WD_ALIGN_PARAGRAPH.CENTER
        rd = d.add_run(self.doc_title)
        rd.bold = True
        rd.font.size = Pt(18)
        if subtitle:
            sub = self.doc.add_paragraph()
            sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
            sub.add_run(subtitle).font.size = Pt(11)
        for _ in range(8):
            self.doc.add_paragraph()
        f = self.doc.add_paragraph()
        f.alignment = WD_ALIGN_PARAGRAPH.CENTER
        f.add_run(f"Version {version}   ·   Submitted by {COMPANY}").font.size = Pt(10)
        self.page_break()

    def document_control(self, description: str, version: str, status: str):
        self.h("Document Control", 1)
        self.table(["Field", "Value"], [
            ["Document Description", description],
            ["Identification", self.ident],
            ["Version", version],
            ["Status", status],
            ["Author", AUTHOR],
            ["Submitting company", COMPANY],
            ["Generated", datetime.now(timezone.utc).strftime("%d %b %Y")],
        ])

    def change_log(self, baselines):
        self.h("Change Log", 1)
        rows = [[b.version, b.at[:10], AUTHOR, b.description] for b in baselines]
        widths = [0.1, 0.15, 0.3, 0.45]
        if not rows:
            rows = [["Draft", datetime.now(timezone.utc).strftime("%Y-%m-%d"), AUTHOR, "Working draft — not yet baselined"]]
        self.table(["Version", "Date", "Author", "Description of change"], rows, widths=widths)

    def sign_off(self, number: str):
        self.h(f"{number} Authorization", 1)
        self.p("By signing below, the parties approve this document as the agreed baseline.")
        self.table(["Role", "Name", "Signature", "Date"], [
            ["Product Owner", "", "", ""], ["Business Analyst", "", "", ""],
            ["Technical Lead", "", "", ""], ["Approver", "", "", ""],
        ])

    def bytes(self) -> bytes:
        buf = io.BytesIO()
        self.doc.save(buf)
        return buf.getvalue()


def _version(state, doc_type: str):
    b = [x for x in state.baselines if x.doc_type == doc_type]
    return (b[-1].version, "Baselined — approved for the next stage") if b else ("Draft", "Draft — pending baseline")


def brdprd_docx(state, reqs) -> tuple[bytes, str]:
    year = datetime.now(timezone.utc).year
    code = product_code(state)
    ident = f"PHN-{code}-{year}-01-BRDPRD"
    version, status = _version(state, "brdprd")
    b = Builder(state, "Business & Product Requirements Document (BRD/PRD)", ident)
    b.cover("Functional scope, business rules and acceptance criteria", version)
    b.document_control(f"BRD/PRD for {state.selected_name}", version, status)
    b.change_log([x for x in state.baselines if x.doc_type == "brdprd"])
    b.page_break()

    brief = state.concept_brief
    specs = state.module_specs or []
    b.h("1. Introduction", 1)
    b.h("1.1 Purpose & Vision", 2)
    b.p((brief.summary if brief and brief.summary else state.concept_summary) or "")
    if state.research and state.research.positioning_reframe:
        b.p(state.research.positioning_reframe, italic=True)
    b.h("1.2 Scope", 2)
    b.p("In scope:", bold=True)
    b.bullets([f"{m.name}" + (" (GiveWings standard module)" if m.kind == "standard" else "") + (f" — {m.description}" if m.description and m.kind != "standard" else "") for m in specs] or [r.module for r in reqs])
    out = list(brief.out_of_scope) if brief else []
    deferred = [f"{d.question} (deferred)" for r in reqs for d in r.decisions if d.deferred]
    if out or deferred:
        b.p("Out of scope / deferred:", bold=True)
        b.bullets(out + deferred)
    if brief:
        b.h("1.3 Product context", 2)
        b.table(["Item", "Decision"], [[k, v] for k, v in (
            ("Target users", brief.target_users), ("Core workflow", brief.core_workflow),
            ("Input channels", brief.input_channels), ("Privacy & visibility", brief.privacy_mode),
            ("Launch market", brief.market), ("Launch platforms", brief.platforms),
        ) if v])

    b.h("2. Stakeholders & Personas", 1)
    actors = []
    for r in reqs:
        for a in (r.doc.actors if r.doc else []):
            if a not in actors:
                actors.append(a)
    b.table(["Role", "Appears in"], [[a, ", ".join(r.req_id for r in reqs if r.doc and a in r.doc.actors)] for a in actors])

    b.h("3. Functional Requirements", 1)
    access = {m.name: m for m in specs}
    for i, r in enumerate(reqs, 1):
        d = r.doc
        b.h(f"3.{i} {r.title}  ({r.req_id})", 2)
        meta = [f"Module: {r.module}"]
        if r.standard_version:
            meta.append(f"GiveWings standard v{r.standard_version}")
        m = access.get(r.module)
        if m and m.kind != "standard":
            meta.append({"public": "Public — no sign-in", "mixed": "Public trial + sign-in"}.get(m.access, "Signed-in users"))
        meta.append(f"Status: {r.status}")
        b.p("  ·  ".join(meta), italic=True, size=9)
        if not d:
            b.p(r.body)
            continue
        if d.summary:
            b.p(d.summary)
        if d.receives_from or d.hands_off_to:
            b.table(["Receives from", "Hands off to"], [[d.receives_from or "—", d.hands_off_to or "—"]])
        if d.actors:
            b.p("Actors: " + ", ".join(d.actors))
        if d.journey:
            b.h("How it works", 3)
            b.numbered([f"{s.title}{f' ({s.actor})' if s.actor else ''} — {s.detail}" for s in d.journey])
        if d.business_rules:
            b.h("Business rules", 3)
            b.bullets(d.business_rules)
        if d.acceptance_criteria:
            b.h("Acceptance criteria", 3)
            b.table(["#", "Criterion", "Priority"], [[a.id, a.criterion, a.priority] for a in d.acceptance_criteria], widths=[0.1, 0.75, 0.15])
        if d.out_of_scope:
            b.h("Out of scope", 3)
            b.bullets(d.out_of_scope)
        if r.decisions:
            b.h("Product-owner decisions", 3)
            b.table(["Question", "Decision"], widths=[0.5, 0.5], rows=[[x.question, ("Deferred — " + x.answer if x.answer else "Deferred") if x.deferred else x.answer] for x in r.decisions])
        if d.open_questions:
            b.h("Open questions", 3)
            b.bullets(d.open_questions)

    market = (brief.market if brief else "") or "the launch market"
    b.h("4. Non-Functional Requirements", 1)
    b.table(["Category", "Requirement"], [
        ["Performance", "Everyday screens respond within 2 seconds for typical use; long-running AI work shows progress and never blocks the user."],
        ["Security", "Covered by the Security, Audit & Health standard module: protected data, immutable audit trail, role-based access."],
        ["Scalability", "The product grows with users and content volume without redesign; background work is queued, not done inline."],
        ["Availability", "Every module is watched by the health agent; outages alert the owner and admins."],
        ["Compliance", f"Personal data is handled under the data-protection law of {market} (e.g. India's DPDP Act 2023 where applicable)."],
        ["Localization", f"Language and formats suitable for {market}."],
    ])

    b.h("5. Assumptions & Dependencies", 1)
    b.bullets((list(brief.assumptions) if brief else []) + [
        "Each product ships its own standard modules (sign-in, profile, admin, security & health) and can be hosted independently of GiveWings.",
        "Technical choices (stack, APIs, data model) are made in the Technical Design stage from this baselined document.",
    ])

    b.h("6. Success Metrics / KPIs", 1)
    b.p("Targets are to be confirmed by the product owner before launch.", italic=True)
    rows = [[f"Users reaching: {m.outcome}", "To be confirmed", "Product analytics"] for m in specs if m.kind != "standard" and m.outcome]
    rows += [["Monthly active users", "To be confirmed", "Product analytics"], ["Module availability", "To be confirmed", "Health agent reports"]]
    b.table(["Metric", "Target", "How measured"], rows)

    b.sign_off("7.")
    fname = f"{ident}_v{version}.docx".replace(" ", "_")
    return b.bytes(), fname


STACK_LABELS = [
    ("product_type", "Product type"), ("frontend", "Frontend"), ("backend", "Backend"),
    ("data", "Data"), ("ai_ml", "AI / ML components"), ("hosting", "Hosting & infra"),
    ("integrations", "Third-party integrations"), ("devops", "DevOps & CI/CD"),
    ("security", "Security & compliance baseline"), ("conventions", "Coding conventions"),
]


def techdesign_docx(state, reqs) -> tuple[bytes, str]:
    """Phoneme Technical Design Document (HLD/LLD). Module numbering mirrors
    the BRD/PRD Functional Requirements 1:1 (3.n -> 2.2.n and 3.n)."""
    year = datetime.now(timezone.utc).year
    ident = f"PHN-{product_code(state)}-{year}-TD"
    version, status = _version(state, "techdesign")
    b = Builder(state, "Technical Design Document (HLD/LLD)", ident)
    brd_v = [x.version for x in state.baselines if x.doc_type == "brdprd"]
    b.cover(f"Covers every module of BRD/PRD v{brd_v[-1] if brd_v else 'draft'}", version)
    b.document_control(f"Technical Design (HLD/LLD) for {state.selected_name}", version, status)
    b.change_log([x for x in state.baselines if x.doc_type == "techdesign"])
    b.page_break()

    hld = next((t for t in state.tech_designs if t.kind == "hld"), None)
    llds = [t for t in state.tech_designs if t.kind == "lld" and t.doc]
    order = {r.req_id: i for i, r in enumerate(reqs, 1)}
    llds.sort(key=lambda t: order.get(t.req_id, 999))

    b.h("1. Overview", 1)
    b.p((state.concept_brief.summary if state.concept_brief and state.concept_brief.summary else state.concept_summary) or "")
    b.p(f"This design implements BRD/PRD v{brd_v[-1] if brd_v else 'draft'} (PHN-{product_code(state)}-{year}-01-BRDPRD). "
        "Each module below is numbered to match the BRD/PRD Functional Requirements section.")

    b.h("2. High-Level Design", 1)
    b.h("2.1 System architecture", 2)
    if state.stack:
        b.p("Technical Stack Charter" + (" (confirmed)" if state.stack.confirmed else " (not yet confirmed)"), bold=True)
        b.table(["Area", "Decision"], [[label, getattr(state.stack, k) or "—"] for k, label in STACK_LABELS], widths=[0.3, 0.7])
    if hld and hld.doc:
        b.p(hld.doc.overview)
        if hld.doc.components:
            b.table(["Component", "Responsibility"], [[c.name, c.responsibility] for c in hld.doc.components], widths=[0.3, 0.7])
        if hld.doc.sequence:
            b.p("Main end-to-end flow", bold=True)
            b.numbered(hld.doc.sequence)
    b.h("2.2 Module breakdown", 2)
    for t in llds:
        n = order.get(t.req_id, "")
        b.h(f"2.2.{n} {t.module}  ({t.req_id} → {t.td_id})", 3)
        b.p(t.doc.overview)
        if t.doc.components:
            b.bullets([f"{c.name} — {c.responsibility}" for c in t.doc.components])
    b.h("2.3 Integration points", 2)
    integ = (hld.doc.integrations if hld and hld.doc else []) + [i for t in llds for i in t.doc.integrations]
    b.bullets(integ or ["None beyond the stack charter."])

    b.h("3. Low-Level Design", 1)
    for t in llds:
        n = order.get(t.req_id, "")
        d = t.doc
        b.h(f"3.{n} {t.module}  ({t.td_id})", 2)
        b.h(f"3.{n}.1 Data model", 3)
        if d.data_model:
            for e in d.data_model:
                b.p(f"{e.name}" + (f" — {e.description}" if e.description else ""), bold=True)
                if e.fields:
                    b.table(["Field", "Type", "Notes"], [[f.name, f.type, f.notes] for f in e.fields], widths=[0.3, 0.2, 0.5])
        else:
            b.p("No module-specific data.", italic=True)
        b.h(f"3.{n}.2 API contracts", 3)
        if d.apis:
            b.table(["Method", "Endpoint", "Purpose", "Request", "Response"],
                    [[a.method, a.path, a.purpose, a.request, a.response] for a in d.apis],
                    widths=[0.09, 0.24, 0.25, 0.21, 0.21])
        b.h(f"3.{n}.3 Key sequence flow", 3)
        b.numbered(d.sequence or ["—"])
        b.h(f"3.{n}.4 Edge cases & error handling", 3)
        b.bullets(d.edge_cases or ["—"])
        if t.decisions:
            b.p("Decisions recorded during review", bold=True)
            b.table(["Question", "Decision"], [[x.question, ("Deferred — " + x.answer if x.answer else "Deferred") if x.deferred else x.answer] for x in t.decisions], widths=[0.5, 0.5])

    b.h("4. Security & Compliance", 1)
    sec = (hld.doc.security if hld and hld.doc else []) + [f"{t.module}: {s}" for t in llds for s in t.doc.security]
    b.bullets(sec or ["See the Security, Audit & Health module."])

    b.h("5. Non-Functional Design", 1)
    nfr = (hld.doc.nfr if hld and hld.doc else []) + [x for t in llds for x in t.doc.nfr]
    b.table(["Requirement (BRD/PRD)", "How it is achieved"], [[x.requirement, x.approach] for x in nfr] or [["—", "—"]], widths=[0.4, 0.6])

    b.h("6. Open Questions / Risks", 1)
    risks = (hld.doc.risks if hld and hld.doc else []) + [f"{t.module}: {r}" for t in llds for r in t.doc.risks]
    oq = [f"{t.td_id}: {q}" for t in state.tech_designs if t.doc for q in t.doc.open_questions]
    b.table(["Item", "Owner", "Target resolution"], [[x, "Product owner / architect", "Before build start"] for x in risks + oq] or [["None open", "—", "—"]], widths=[0.6, 0.2, 0.2])

    b.sign_off("7.")
    return b.bytes(), f"{ident}_v{version}.docx"
