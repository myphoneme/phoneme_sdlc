"""
Product document folders (2026-10-06).

Every generated SDLC document is filed the way Phoneme already organises its
product workspaces (see the HR Management / Teamora folders):

    <Product>/Requirement/<Product>_BRD_PRD_v1.0.docx
    <Product>/Technical/<Product>_TechDesign_v1.0.docx
    <Product>/Technical/<Product>_Technical_Stack_Charter_v1.0.md
    <Product>/UI-UX/<Product>_UI_UX_Mockups_v1.0.html
    <Product>/UI-UX/<Product>_Prototype_v1.0.html
    <Product>/UI-UX/designs/<module>/<uploaded file>

Each baseline writes its version into DOCS_DIR/<session>/..., so earlier
versions are kept side by side (v1.0, v1.1 ...) exactly like the existing
workspaces; the handover zip contains that whole tree plus the latest files.
"""
import io
import logging
import re
import zipfile
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from . import config, export, store

logger = logging.getLogger("phoneme.documents")
router = APIRouter(prefix="/api/handover", tags=["handover"])


def _root(state) -> Path:
    return config.DOCS_DIR / re.sub(r"[^0-9a-fA-F-]", "", state.session_id)


def _ver(state, doc_type):
    b = [x.version for x in state.baselines if x.doc_type == doc_type]
    return b[-1] if b else "draft"


async def render(state, doc_types=("brdprd", "techdesign", "uiux")) -> list[tuple[str, bytes]]:
    """Latest version of every document of the given stages, as (relpath, bytes)."""
    from .routers import uiux  # late import: routers depend on this module's siblings
    out: list[tuple[str, bytes]] = []
    reqs = sorted(await store.list_requirements(state.session_id), key=lambda r: r.req_id)
    if "brdprd" in doc_types and reqs:
        data, _ = export.brdprd_docx(state, reqs)
        out.append((export.relative_path(state, "brdprd", _ver(state, "brdprd")), data))
    if "techdesign" in doc_types:
        if state.stack:
            data, name = export.stack_charter_md(state)
            out.append((f"{export.product_slug(state)}/Technical/{name}", data))
        if state.tech_designs:
            data, _ = export.techdesign_docx(state, reqs)
            out.append((export.relative_path(state, "techdesign", _ver(state, "techdesign")), data))
    if "uiux" in doc_types and any(m.doc for m in state.ui_modules):
        v = _ver(state, "uiux")
        out.append((export.relative_path(state, "uiux", v), uiux.mockups_html(state).encode()))
        out.append((export.relative_path(state, "prototype", v), uiux.prototype_html(state).encode()))
        for m in state.ui_modules:
            for sc in (m.doc.screens if m.doc else []):
                if sc.source == "upload":
                    p = uiux._asset_path(state.session_id, sc)
                    if p.exists():
                        mod = re.sub(r"[^A-Za-z0-9]+", "_", m.module).strip("_")
                        nm = re.sub(r"[^A-Za-z0-9]+", "_", sc.name).strip("_") or sc.asset_id
                        out.append((f"{export.product_slug(state)}/UI-UX/designs/{mod}/{nm}{p.suffix}", p.read_bytes()))
    return out


async def archive(state, doc_type: str) -> list[str]:
    """Write the baselined version of a stage's documents into the product
    folder. Never raises: filing must not block a baseline."""
    try:
        written = []
        for rel, data in await render(state, (doc_type,)):
            path = _root(state) / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            written.append(rel)
        return written
    except Exception:  # noqa: BLE001
        logger.exception("Could not file %s documents for %s", doc_type, state.session_id)
        return []


def archived(state) -> list[str]:
    root = _root(state)
    if not root.exists():
        return []
    return sorted(str(p.relative_to(root)).replace("\\", "/") for p in root.rglob("*") if p.is_file())


@router.get("/{session_id}/files")
async def list_files(session_id: str):
    state = await store.get_session(session_id)
    if not state:
        raise HTTPException(404, "session not found")
    latest = [rel for rel, _ in await render(state)]
    return {"product_folder": export.product_slug(state), "files": sorted(set(archived(state)) | set(latest))}


@router.get("/{session_id}/pack.zip")
async def pack(session_id: str):
    """The whole product folder: every baselined version plus the latest files."""
    state = await store.get_session(session_id)
    if not state:
        raise HTTPException(404, "session not found")
    files: dict[str, bytes] = {}
    root = _root(state)
    for rel in archived(state):
        files[rel] = (root / rel).read_bytes()
    for rel, data in await render(state):
        files[rel] = data  # latest wins for the same name (e.g. drafts)
    if not files:
        raise HTTPException(400, "nothing to export yet")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in sorted(files):
            z.writestr(rel, files[rel])
    name = f"{export.product_slug(state)}_SDLC_Pack.zip"
    return Response(buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})
