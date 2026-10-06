import asyncio, json, re
import httpx
from app import ai_router, main
from app.routers import identity

LOGO = '<svg viewBox="0 0 240 80"><circle cx="40" cy="40" r="24" fill="#0F766E" onclick="alert(1)"/><script>alert(1)</script><text x="80" y="50" font-family="Manrope" font-weight="800" fill="#171717">RelayReel</text></svg>'
calls = []
async def fake(feature, prompt, system=None):
    calls.append(feature.value)
    f = feature
    if f == ai_router.Feature.DISCOVERY_CHAT_NLU:
        if system and "Enough has been shared" in system:
            return {"text": "CONCEPT SUMMARY: A forward-to-catalogue engine for everyday users, private by default."}
        return {"text": "Who are the target users, and which market launches first?"}
    if f == ai_router.Feature.CONCEPT_BRIEF:
        return {"text": json.dumps({"summary":"Forward-to-catalogue engine","target_users":"Everyday users who forward content","core_workflow":"Forward, catalogue, research, repurpose, post","input_channels":"WhatsApp number, email","privacy_mode":"Private by default; user chooses public","market":"Not stated","platforms":"Not stated","must_haves":["Catalogue by genre/topic"],"out_of_scope":[],"assumptions":["Assumed: India launch"]})}
    if f == ai_router.Feature.COMPETITIVE_RESEARCH:
        await asyncio.sleep(0.3)
        return {"text": json.dumps({"market_landscape":[{"category":"Clippers","examples":"Notion","what_they_do":"save","limitations":"no repurpose"}],"viability_verdict":"ok","suggested_names":["ThreadVault"],"recommended_features":["Phase 1: ingest"]})}
    if f == ai_router.Feature.NAME_AVAILABILITY_CHECK:
        return {"text": "Memorable and easy to say."}
    if f == ai_router.Feature.BRAND_IDENTITY:
        if "taglines" in prompt: return {"text": '{"taglines":["Forward it. Own it.","Your feed, remade"]}'}
        if "palettes" in prompt: return {"text": '{"palettes":[{"name":"Teal Tide","mood":"calm","primary":"#0F766E","ink":"#12302D","surface":"#E3F3F1","accent":"#FF7200","rationale":"x"},{"name":"bad","primary":"red","ink":"#000000","surface":"#ffffff","accent":"#000000"}]}'}
        return {"text": json.dumps({"logos":[{"concept":"relay loop","svg":LOGO},{"concept":"broken","svg":"<svg><foo"}]})}
    if f == ai_router.Feature.MODULE_BREAKDOWN and "Current modules" in prompt:
        assert "Aim for exactly 2" in prompt
        return {"text": json.dumps({"rationale": "Merged capture and cataloguing.", "modules": [
            {"name": "Capture & Catalogue", "description": "Forwarding in, sorted by topic", "platform_core": False, "merged_from": ["Ingestion Vault", "Genre & Topic Catalogue"]},
            {"name": "Repurpose Studio", "description": "text/image/video", "platform_core": False, "merged_from": ["Repurpose Studio"]},
            {"name": "Auth & Identity", "description": "login", "platform_core": True}]})}
    if f == ai_router.Feature.MODULE_BREAKDOWN and "define module boundaries" in (system or ""):
        return {"text": json.dumps({"modules": [{"name": "genre & topic catalogue", "starts_when": "Items are in the vault", "outcome": "Items are filed by topic"}, {"name": "Repurpose Studio", "starts_when": "A topic is chosen", "outcome": "Drafts exist"}]})}
    if f == ai_router.Feature.MODULE_BREAKDOWN:
        return {"text": '{"modules":[{"name":"Ingestion Vault","description":"captures forwards","platform_core":false},{"name":"Catalogue","description":"genre/topic","platform_core":false},{"name":"Auth & Identity","description":"login","platform_core":true}]}'}
    if f == ai_router.Feature.TECH_DESIGN_GENERATION and "Suggest a Technical Stack Charter" in prompt:
        return {"text": json.dumps({"product_type": "SaaS web app", "frontend": "React + Vite", "backend": "Python FastAPI, REST",
            "data": "PostgreSQL", "ai_ml": "LLM via gateway", "hosting": "TBD — confirm: AWS Mumbai or Phoneme DC",
            "integrations": "WhatsApp Business API, email inbound", "devops": "GitHub Actions", "security": "DPDP Act 2023; data in India",
            "conventions": "ruff, eslint"})}
    if f == ai_router.Feature.TECH_DESIGN_GENERATION and "High-Level Design" in prompt:
        assert "PostgreSQL" in prompt, "stack charter missing from HLD prompt"
        return {"text": json.dumps({"overview": "SPA + API + workers.", "components": [{"name": "API", "responsibility": "serves the SPA"}],
            "integrations": ["WhatsApp Business API"], "security": ["JWT sessions"], "nfr": [{"requirement": "2s screens", "approach": "caching"}],
            "sequence": ["1. User forwards", "2. API stores"], "risks": ["WhatsApp approval -> apply early"],
            "open_questions": [] if "answered open questions" in prompt else ["Which region hosts production?"]})}
    if f == ai_router.Feature.TECH_DESIGN_GENERATION and "Low-Level Design" in prompt:
        return {"text": json.dumps({"overview": "Module design.", "components": [{"name": "Svc", "responsibility": "x"}],
            "data_model": [{"name": "Item", "description": "a captured item", "fields": [{"name": "id", "type": "uuid", "notes": "pk"}]}],
            "apis": [{"method": "post", "path": "/api/items", "purpose": "create", "request": "url", "response": "item"}],
            "sequence": ["Client calls API", "API saves"], "edge_cases": ["duplicate -> merge"], "security": ["owner-only access"],
            "nfr": [{"requirement": "fast", "approach": "index"}], "open_questions": []})}
    if f == ai_router.Feature.TECH_DESIGN_GENERATION and "Design the screens" in prompt:
        return {"text": json.dumps({"screens": [{"name": "Vault inbox", "purpose": "See captured items", "route": "/inbox", "layout": "app",
            "blocks": [{"type": "stats", "items": ["Items this week: 42"]}, {"type": "list", "title": "Latest", "items": ["AI chips article — Article"]},
                       {"type": "bogus", "text": "falls back to text"}], "states": ["empty: connect WhatsApp"]}],
            "notes": ["Inbox first"], "open_questions": []})}
    if f == ai_router.Feature.TECH_DESIGN_GENERATION:
        flow_prompts.append(prompt)
        if "too technical" in prompt:
            return {"text": "1. User: forwards a link\n2. RelayReel: saves it to the vault\n3. User: sees it in the inbox"}
        return {"text": "1. User: forwards a link\n2. Gateway: calls POST /ingest/email and writes raw_messages\n3. User: sees it"}
    if f == ai_router.Feature.BRD_PRD_DRAFTING and "Review these as ONE set" in prompt:
        return {"text": json.dumps({"verdict": "Two documents overlap.", "issues": [{"documents": ["RELA-001", "RELA-002", "BOGUS"], "problem": "Both describe capturing links.", "suggestion": "Keep capture only in RELA-001."}]})}
    if f == ai_router.Feature.BRD_PRD_DRAFTING:
        await asyncio.sleep(0.05)
        if "Module: " in prompt and "All modules of this product" not in prompt and "Current requirement" not in prompt:
            raise AssertionError("draft prompt missing module map")
        if "Catalogue" in prompt and "Module: Genre" in prompt and fail_once["on"]:
            fail_once["on"] = False
            raise RuntimeError("provider timeout")
        leaky = "contains implementation detail" not in prompt and "Module: Ingestion Vault" in prompt and "Current requirement" not in prompt
        doc = {"title": "Capture forwarded content", "summary": "Users forward links and they land in a private vault.",
               "actors": ["Content creator", "RelayReel (system)"],
               "journey": [{"title": "Forward a link", "detail": "The creator forwards a link on WhatsApp.", "actor": "Content creator"},
                           {"title": "Save privately", "detail": ("The gateway calls POST /ingestion/intake and writes vault_raw_messages." if leaky else "RelayReel saves it to the private vault."), "actor": "RelayReel (system)"}],
               "business_rules": ["Items are private by default."],
               "acceptance_criteria": [{"criterion": "Given a forwarded link, when it arrives, then it appears in the vault within a minute.", "priority": "must"}, {"criterion": "", "priority": "x"}, {"criterion": "Given a duplicate, then it is merged.", "priority": "Should"}],
               "out_of_scope": [], "open_questions": []}
        return {"text": json.dumps(doc)}
    return {"text": "ok"}
fail_once = {"on": True}
flow_prompts = []
ai_router.generate = fake

async def fake_check(client, d):
    from app.models import DomainCheck
    return DomainCheck(domain=d, status="taken" if d.endswith(".com") and not d.startswith("get") else "available", method="rdap")
identity.check_domain = fake_check

import tempfile as _tf, pathlib as _pl
from app import config as _cfg0
_cfg0.DOCS_DIR = _pl.Path(_tf.mkdtemp())

async def run():
    t = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=t, base_url="http://t") as c:
        async def post(p, j, code=200):
            r = await c.post(p, json=j); assert r.status_code == code, (p, r.status_code, r.text); return r.json()
        s = await post("/api/discovery/start", {"initial_message": "IDEA :: forward engine"})
        sid = s["session_id"]
        s = await post("/api/discovery/chat", {"session_id": sid, "message": "Everyday users"})
        assert s["stage"] == "discovery", s["stage"]
        s = await post("/api/discovery/summarize", {"session_id": sid})
        assert s["stage"] == "confirm" and s["concept_brief"]["privacy_mode"].startswith("Private"), s
        await post("/api/discovery/chat", {"session_id": sid, "message": "x"}, 409)
        b = s["concept_brief"]; b["market"] = "India, English + Hindi"
        s = await post("/api/discovery/confirm", {"session_id": sid, "brief": b})
        assert s["stage"] == "research" and "India" in s["concept_summary"] and "Private" in s["concept_summary"]
        # two tabs start research at once -> one paid call
        r1, r2 = await asyncio.gather(c.post("/api/discovery/research", json={"session_id": sid, "message": ""}), c.post("/api/discovery/research", json={"session_id": sid, "message": ""}))
        assert calls.count("competitive_research") == 1, calls
        s = await post("/api/discovery/research/done", {"session_id": sid}); assert s["stage"] == "identity"
        s = await post("/api/identity/domains", {"session_id": sid, "name": "Relay Reel"})
        print("domains:", [(d["domain"], d["status"]) for d in s["brand"]["domains"]])
        s = await post("/api/identity/name", {"session_id": sid, "value": "RelayReel"})
        s = await post("/api/identity/domain", {"session_id": sid, "value": "relayreel.in"})
        await post("/api/identity/complete", {"session_id": sid}, 400)
        s = await post("/api/identity/taglines", {"session_id": sid}); assert len(s["brand"]["tagline_options"]) == 2
        s = await post("/api/identity/tagline", {"session_id": sid, "value": "Forward it. Own it."})
        s = await post("/api/identity/palettes", {"session_id": sid}); assert len(s["brand"]["palette_options"]) == 1, s["brand"]["palette_options"]
        s = await post("/api/identity/palette", {"session_id": sid, "palette": s["brand"]["palette_options"][0]})
        s = await post("/api/identity/logos", {"session_id": sid}); logos = s["brand"]["logo_options"]
        assert len(logos) == 1 and "script" not in logos[0]["svg"] and "onclick" not in logos[0]["svg"], logos
        print("sanitized svg:", logos[0]["svg"][:160])
        s = await post("/api/identity/logo", {"session_id": sid, "logo_id": logos[0]["id"]})
        # --- Experience Blueprint: template -> edit -> preview -> freeze (required to complete Identity)
        await post("/api/identity/complete", {"session_id": sid}, 400)
        cat = (await c.get("/api/identity/blueprint/templates")).json()
        assert len(cat["templates"]) == 6 and "mobile_otp" in cat["auth_methods"]
        await post("/api/identity/blueprint/template", {"session_id": sid, "template_key": "nope"}, 404)
        s = await post("/api/identity/blueprint/template", {"session_id": sid, "template_key": "mobile_diary"})
        bp = s["brand"]["blueprint"]; assert bp["platforms"] == "both" and bp["primary"] == "mobile" and bp["mobile"]["share_target"]
        bp["landing_sections"] = ["faq", "download", "bogus", "faq"]; bp["tokens"]["heading_font"] = "Comic Sans"; bp["mobile"]["tabs"] = ["Diary", "Search", "", "Insights", "Profile", "Extra"]
        s = await post("/api/identity/blueprint", {"session_id": sid, "blueprint": bp})
        bp = s["brand"]["blueprint"]
        assert bp["landing_sections"] == ["hero", "faq", "download"] and bp["tokens"]["heading_font"] == "Space Grotesk" and len(bp["mobile"]["tabs"]) == 5, bp
        pv = await c.get(f"/api/identity/{sid}/blueprint/preview")
        assert pv.status_code == 200 and 'class="tabbar"' in pv.text and 'class="qr"' in pv.text and "Share to RelayReel" in pv.text and "Send me a code" in pv.text, pv.text[:200]
        s = await post("/api/identity/blueprint/freeze", {"session_id": sid}); assert s["brand"]["blueprint"]["version"] == "1.0"
        await post("/api/identity/blueprint", {"session_id": sid, "blueprint": bp}, 409)
        s = await post("/api/identity/blueprint/unfreeze", {"session_id": sid})
        s = await post("/api/identity/blueprint/template", {"session_id": sid, "template_key": "saas"})
        s = await post("/api/identity/blueprint/freeze", {"session_id": sid}); bp = s["brand"]["blueprint"]
        assert bp["version"] == "1.1" and bp["platforms"] == "web" and bp["frozen"], bp
        s = await post("/api/identity/complete", {"session_id": sid}); assert s["stage"] == "freeze"
        s = await post("/api/wizard/freeze", {"session_id": sid}); assert s["stage"] == "freeze" and len(s["module_specs"]) == 6, s
        biz = [m["name"] for m in s["module_specs"] if m["kind"] == "business"]
        assert biz == ["Ingestion Vault", "Catalogue"], biz   # Auth & Identity replaced by standard modules
        assert s["modules"][0] == "Sign-in & Account" and s["modules"][-1] == "Security, Audit & Health"
        print("modules:", s["modules"])
        specs = s["module_specs"]; specs.append({"name": "Repurpose Studio", "description": "text/image/video", "access": "mixed", "access_note": "Try one free repurpose"}); specs[2]["name"] = "Genre & Topic Catalogue"
        specs[0]["tailoring"] = "Sign in with WhatsApp OTP"
        await post("/api/wizard/modules/save", {"session_id": sid, "modules": specs + [{"name": "Profile & Settings"}]}, 400)
        s = await post("/api/wizard/modules/save", {"session_id": sid, "modules": specs})
        await post("/api/wizard/modules/save", {"session_id": sid, "modules": specs + [specs[1]]}, 400)
        assert s["module_specs"][0]["tailoring"] == "Sign in with WhatsApp OTP"
        s = await post("/api/wizard/modules/save", {"session_id": sid, "modules": [m for m in specs if m.get("kind") != "standard"]})
        assert s["module_specs"][0]["tailoring"] == "Sign in with WhatsApp OTP" and len(s["module_specs"]) == 7, s["modules"]
        s = await post("/api/wizard/modules/confirm", {"session_id": sid}); assert s["stage"] == "flow"
        s = await post("/api/wizard/modules/boundary", {"session_id": sid, "module": "Ingestion Vault", "starts_when": "User sets up their vault", "outcome": "Every forwarded item lands in the vault inbox"})
        assert s["module_specs"][1]["outcome"] == "Every forwarded item lands in the vault inbox"
        await post("/api/wizard/modules/boundary", {"session_id": sid, "module": "Sign-in & Account", "starts_when": "x"}, 404)
        s = await post("/api/wizard/flows/generate", {"session_id": sid}); assert len(s["module_flows"]) == 7, [f["module"] for f in s["module_flows"]]
        std = [f for f in s["module_flows"] if f["standard"]]
        assert len(std) == 4 and all(f["status"] == "Approved" for f in std)
        await post("/api/wizard/flows/update", {"session_id": sid, "module": "Sign-in & Account", "steps": ["x"]}, 409)
        m = "Ingestion Vault"
        s = await post("/api/wizard/flows/update", {"session_id": sid, "module": m, "steps": ["A", " ", "B edited", "C new"]})
        assert next(f for f in s["module_flows"] if f["module"] == m)["steps"] == ["A", "B edited", "C new"]
        assert any("STARTS when: User sets up their vault" in p for p in flow_prompts), "boundary missing from flow prompt"
        s = await post("/api/wizard/modules/suggest-boundaries", {"session_id": sid})
        b = {m["name"]: (m["starts_when"], m["outcome"]) for m in s["module_specs"] if m["kind"] == "business"}
        assert b["Ingestion Vault"][0] == "User sets up their vault" and b["Genre & Topic Catalogue"] == ("Items are in the vault", "Items are filed by topic"), b
        from app import store as _st
        st = await _st.get_session(sid); st.module_flows = [f for f in st.module_flows if not f.standard]; await _st.save_session(st)
        s = await post("/api/wizard/flows/generate", {"session_id": sid})
        assert sum(1 for f in s["module_flows"] if f["standard"]) == 4, [f["module"] for f in s["module_flows"]]
        s = await post("/api/wizard/flows/redraft", {"session_id": sid, "module": m})
        rd = next(f for f in s["module_flows"] if f["module"] == m)
        assert rd["status"] == "Draft" and rd["steps"][0].startswith("User:") and not any("POST" in x for x in rd["steps"]), rd["steps"]
        await post("/api/wizard/flows/redraft", {"session_id": sid, "module": "Sign-in & Account"}, 409)
        s = await post("/api/wizard/flows/update", {"session_id": sid, "module": m, "steps": ["A", " ", "B edited", "C new"]})
        await post("/api/wizard/flows/freeze", {"session_id": sid}, 400)
        for f in s["module_flows"]:
            if not f["standard"]:
                s = await post("/api/wizard/flows/accept", {"session_id": sid, "module": f["module"]})
        s = await post("/api/wizard/flows/freeze", {"session_id": sid}); assert s["stage"] == "generating"
        s, s2 = await asyncio.gather(post("/api/wizard/generate", {"session_id": sid}), post("/api/wizard/generate", {"session_id": sid}))
        print("gen start:", s["generation"]["status"], s["generation"]["total"])
        for _ in range(40):
            await asyncio.sleep(0.15)
            s = (await c.get(f"/api/discovery/{sid}")).json()
            g = s["generation"]
            if g["status"] != "running": break
        print("gen end:", g["status"], g["done"], "/", g["total"], [(i["module"], i["status"], i["error"]) for i in g["items"]])
        assert g["status"] == "failed" and g["done"] == 6
        s = await post("/api/wizard/generate/retry", {"session_id": sid})
        for _ in range(40):
            await asyncio.sleep(0.15)
            s = (await c.get(f"/api/discovery/{sid}")).json()
            if s["generation"]["status"] != "running": break
        g = s["generation"]
        reqs = (await c.get(f"/api/brdprd/{sid}/requirements")).json()
        print("after retry:", g["status"], g["done"], "/", g["total"], "stage", s["stage"], "reqs", [r["req_id"] for r in reqs])
        assert g["status"] == "done" and s["stage"] == "manager" and len(reqs) == 7
        sa = next(r for r in reqs if r["module"] == "Sign-in & Account")
        assert sa["standard_version"] == "1.0" and sa["req_id"] == "RELA-001" and len(sa["doc"]["acceptance_criteria"]) == 7, sa
        assert next(r for r in reqs if r["module"] == "Ingestion Vault")["standard_version"] == ""
        print("drafting calls:", calls.count("brd_prd_drafting"))
        r1 = next(r for r in reqs if r["module"] == "Ingestion Vault")
        txt = r1["body"]
        assert "/ingestion" not in txt and "vault_raw" not in txt, txt
        assert r1["doc"]["journey"][1]["detail"] == "RelayReel saves it to the private vault."
        acs = r1["doc"]["acceptance_criteria"]
        assert [a["id"] for a in acs] == ["AC1", "AC2"] and acs[0]["priority"] == "Must", acs
        print("structured doc OK; body:\n" + txt)
        # legacy prose requirement -> restructure proposal -> discard restores status
        from app import store
        from app.models import Requirement
        legacy = Requirement(req_id="RELA-900", module="Ingestion Vault", title="Old prose", body="Users must POST /x ...", status="Approved")
        await store.add_requirement(sid, legacy)
        rr = await post(f"/api/brdprd/{sid}/restructure/RELA-900", {})
        assert rr["revised_doc"] and rr["status"].startswith("Revised"), rr
        await post(f"/api/brdprd/{sid}/freeze/RELA-900", {}, 400)
        rr = await post(f"/api/brdprd/{sid}/discard", {"req_id": "RELA-900"})
        assert rr["status"] == "Approved" and rr["doc"] is None, rr
        rr = await post(f"/api/brdprd/{sid}/restructure/RELA-900", {})
        rr = await post(f"/api/brdprd/{sid}/accept", {"req_id": "RELA-900"})
        assert rr["doc"]["summary"] and rr["title"] == "Capture forwarded content" and rr["status"] == "Approved", rr
        rr = await post(f"/api/brdprd/{sid}/comment", {"req_id": "RELA-900", "comment": "mention duplicates"})
        assert rr["revised_doc"], rr
        # --- legacy prose can't be frozen; unfreeze works
        await post(f"/api/brdprd/{sid}/accept", {"req_id": "RELA-900"})
        await post(f"/api/brdprd/{sid}/freeze/RELA-900", {}, 200)
        rr = await post(f"/api/brdprd/{sid}/unfreeze/RELA-900", {}); assert rr["status"] == "Approved"
        legacy2 = Requirement(req_id="RELA-901", module="x", title="Old", body="prose", status="Approved")
        await store.add_requirement(sid, legacy2)
        await post(f"/api/brdprd/{sid}/freeze/RELA-901", {}, 400)
        # --- open questions gate approve/freeze; answers revise the document
        from app.models import RequirementDoc
        oq = Requirement(req_id="RELA-950", module="Ingestion Vault", title="Q doc", body="x", status="Draft",
                         doc=RequirementDoc(summary="s", open_questions=["Should 2FA be required for paid users?", "What is the inactivity timeout?"]))
        await store.add_requirement(sid, oq)
        await post(f"/api/brdprd/{sid}/accept", {"req_id": "RELA-950"}, 409)
        await post(f"/api/brdprd/{sid}/freeze/RELA-950", {}, 409)
        rr = await post(f"/api/brdprd/{sid}/answers", {"req_id": "RELA-950", "answers": [
            {"question": "Should 2FA be required for paid users?", "answer": "Yes, paid users only"},
            {"question": "What is the inactivity timeout?", "answer": "decide with pilot users", "defer": True}]})
        assert rr["doc"]["open_questions"] == [], rr["doc"]["open_questions"]
        assert any("Deferred to a later release" in x for x in rr["doc"]["out_of_scope"]), rr["doc"]["out_of_scope"]
        assert len(rr["decisions"]) == 2 and rr["decisions"][1]["deferred"] and [m["role"] for m in rr["thread"]] == ["owner", "assistant"], rr["thread"]
        assert "No open questions remain" in rr["thread"][-1]["text"]
        rr = await post(f"/api/brdprd/{sid}/accept", {"req_id": "RELA-950"}); assert rr["status"] == "Approved"
        rr = await post(f"/api/brdprd/{sid}/freeze/RELA-950", {}); assert rr["status"] == "Frozen"
        await post(f"/api/brdprd/{sid}/answers", {"req_id": "RELA-950", "answers": [{"question": "x", "answer": "y"}]}, 409)
        # --- consistency check
        s = await post(f"/api/brdprd/{sid}/consistency", {})
        assert s["consistency"]["issues"][0]["documents"] == ["RELA-001", "RELA-002"], s["consistency"]
        # --- redefine scope
        await post(f"/api/wizard/modules/consolidate", {"session_id": sid, "instruction": "small"}, 409)
        await post(f"/api/brdprd/{sid}/accept", {"req_id": "RELA-001"})
        await post(f"/api/brdprd/{sid}/freeze/RELA-001", {})
        s = await post("/api/wizard/reopen-scope", {"session_id": sid, "reason": "too many modules"})
        assert s["stage"] == "freeze" and s["scope_revision"] == 1 and s["consistency"] is None
        arch = s["requirement_archive"][0]
        assert len(arch["requirements"]) == 10 and any(r["status"] == "Frozen" for r in arch["requirements"]), [r["req_id"] for r in arch["requirements"]]
        assert (await c.get(f"/api/brdprd/{sid}/requirements")).json() == []
        prop = await post("/api/wizard/modules/consolidate", {"session_id": sid, "instruction": "small project, 2 modules", "target": 2})
        assert prop["modules"][0]["merged_from"] == ["Ingestion Vault", "Genre & Topic Catalogue"] and len(prop["modules"]) == 2, prop
        s = await post("/api/wizard/modules/save", {"session_id": sid, "modules": prop["modules"]})
        s = await post("/api/wizard/modules/confirm", {"session_id": sid})
        flows = {f["module"]: f["status"] for f in s["module_flows"]}
        assert {k: v for k, v in flows.items() if k not in ("Sign-in & Account", "Profile & Settings", "Admin Dashboard & Roles", "Security, Audit & Health")} == {"Repurpose Studio": "Draft"} and flows["Sign-in & Account"] == "Approved", flows   # kept flow reset to Draft, removed ones dropped
        s = await post("/api/wizard/flows/generate", {"session_id": sid})
        assert sorted(f["module"] for f in s["module_flows"] if not f["standard"]) == ["Capture & Catalogue", "Repurpose Studio"]
        for f in s["module_flows"]:
            if not f["standard"]:
                s = await post("/api/wizard/flows/accept", {"session_id": sid, "module": f["module"]})
        s = await post("/api/wizard/flows/freeze", {"session_id": sid})
        s = await post("/api/wizard/generate", {"session_id": sid})
        for _ in range(60):
            await asyncio.sleep(0.1)
            s = (await c.get(f"/api/discovery/{sid}")).json()
            if s["generation"]["status"] != "running": break
        reqs = (await c.get(f"/api/brdprd/{sid}/requirements")).json()
        print("after redefine:", s["generation"]["status"], [(r["req_id"], r["module"]) for r in reqs])
        assert s["stage"] == "manager" and len(reqs) == 6
        # --- baseline + export
        await post(f"/api/brdprd/{sid}/baseline", {}, 409)          # not all frozen yet
        for r in reqs:
            await post(f"/api/brdprd/{sid}/accept", {"req_id": r["req_id"]})
            await post(f"/api/brdprd/{sid}/freeze/{r['req_id']}", {})
        st = (await c.get(f"/api/brdprd/{sid}/baseline")).json()
        assert st["all_frozen"] and st["version"] is None and st["next_version"] == "1.0", st
        s = await post(f"/api/brdprd/{sid}/baseline", {})
        assert s["stage"] == "techdesign" and s["baselines"][0]["version"] == "1.0", s["baselines"]
        s = await post(f"/api/brdprd/{sid}/baseline", {}); assert len(s["baselines"]) == 1   # nothing changed
        # change one document -> v1.1
        await post(f"/api/brdprd/{sid}/unfreeze/RELA-002", {})
        r2 = await store.get_requirement(sid, "RELA-002"); r2.doc.business_rules.append("Duplicates are merged."); await store.add_requirement(sid, r2)
        await post(f"/api/brdprd/{sid}/accept", {"req_id": "RELA-002"})
        await post(f"/api/brdprd/{sid}/freeze/RELA-002", {})
        st = (await c.get(f"/api/brdprd/{sid}/baseline")).json()
        assert st["changed_since"] == ["RELA-002"] and st["next_version"] == "1.1", st
        s = await post(f"/api/brdprd/{sid}/baseline", {})
        assert s["baselines"][-1]["version"] == "1.1" and "RELA-002" in s["baselines"][-1]["description"]
        x = await c.get(f"/api/brdprd/{sid}/export/brdprd.docx")
        assert x.status_code == 200 and x.content[:2] == b"PK" and "RelayReel_BRD_PRD_v1.1.docx" in x.headers["content-disposition"], x.headers
        open("/tmp/brdprd_test.docx", "wb").write(x.content)
        print("export bytes:", len(x.content), x.headers["content-disposition"])
        # ================= Stage 8: Technical Design =================
        await post(f"/api/techdesign/{sid}/generate", {}, 409)                 # stack not confirmed
        s = await post(f"/api/techdesign/{sid}/stack/suggest", {})
        assert s["stack"]["backend"] == "Python FastAPI, REST" and not s["stack"]["confirmed"]
        await post(f"/api/techdesign/{sid}/stack/confirm", {}, 400)            # TBD left
        stk = dict(s["stack"]); stk["hosting"] = "AWS Mumbai (ap-south-1)"
        s = await post(f"/api/techdesign/{sid}/stack", {"stack": stk})
        s = await post(f"/api/techdesign/{sid}/stack/confirm", {}); assert s["stack"]["confirmed"]
        s = await post(f"/api/techdesign/{sid}/generate", {})
        for _ in range(60):
            await asyncio.sleep(0.1)
            s = (await c.get(f"/api/discovery/{sid}")).json()
            if s["tech_generation"]["status"] != "running": break
        tds = s["tech_designs"]
        assert s["tech_generation"]["status"] == "done" and len(tds) == 7, (s["tech_generation"], len(tds))
        assert tds[0]["td_id"] == "RELA-TD-000" and tds[0]["kind"] == "hld" and tds[1]["td_id"] == "RELA-TD-001" and tds[1]["req_id"] == "RELA-001"
        assert tds[2]["doc"]["apis"][0]["method"] == "POST"
        hid = "RELA-TD-000"
        await post(f"/api/techdesign/{sid}/accept", {"item_id": hid}, 409)       # open question on HLD
        s = await post(f"/api/techdesign/{sid}/answers", {"item_id": hid, "answers": [{"question": "Which region hosts production?", "answer": "AWS Mumbai"}]})
        h = s["tech_designs"][0]; assert h["doc"]["open_questions"] == [] and len(h["decisions"]) == 1
        s = await post(f"/api/techdesign/{sid}/comment", {"item_id": "RELA-TD-002", "comment": "add rate limits"})
        assert s["tech_designs"][2]["revised_doc"] and s["tech_designs"][2]["status"].startswith("Revised")
        await post(f"/api/techdesign/{sid}/freeze/RELA-TD-002", {}, 409)
        for t in s["tech_designs"]:
            await post(f"/api/techdesign/{sid}/accept", {"item_id": t["td_id"]})
            s = await post(f"/api/techdesign/{sid}/freeze/{t['td_id']}", {})
        s = await post(f"/api/techdesign/{sid}/baseline", {})
        assert s["stage"] == "uiux" and [b["version"] for b in s["baselines"] if b["doc_type"] == "techdesign"] == ["1.0"]
        x = await c.get(f"/api/techdesign/{sid}/export/techdesign.docx")
        assert x.status_code == 200 and x.content[:2] == b"PK" and "RelayReel_TechDesign_v1.0.docx" in x.headers["content-disposition"]
        open("/tmp/td_test.docx", "wb").write(x.content)
        # ================= Stage 9: UI/UX =================
        s = await post(f"/api/uiux/{sid}/generate", {})
        for _ in range(60):
            await asyncio.sleep(0.1)
            s = (await c.get(f"/api/discovery/{sid}")).json()
            if s["ui_generation"]["status"] != "running": break
        uis = s["ui_modules"]
        assert s["ui_generation"]["status"] == "done" and len(uis) == 6 and uis[0]["ui_id"] == "RELA-UI-001", [u["ui_id"] for u in uis]
        acc = uis[0]["doc"]["screens"]
        assert [(x["name"], x["layout"], x["source"]) for x in acc[:3]] == [("Landing page", "public", "kit"), ("Create account", "auth", "kit"), ("Sign in", "auth", "kit")], acc[:3]
        assert [b["type"] for b in acc[0]["blocks"]] == ["hero", "promise", "features", "pricing", "faq", "cta"]
        assert next(x for x in acc if x["source"] != "kit")["blocks"][2]["type"] == "text"  # unknown block type -> text
        h1 = (await c.get(f"/api/uiux/{sid}/render/RELA-UI-001")).text
        assert 'class="site"' in h1 and 'class="hero"' in h1 and 'class="auth"' in h1 and "Space+Grotesk" in h1
        hx = await c.get(f"/api/uiux/{sid}/render/RELA-UI-002")
        assert hx.status_code == 200 and "Vault inbox" in hx.text and "#0F766E" in hx.text, hx.text[:300]
        open("/tmp/ui_test.html", "w").write(hx.text)
        # --- clickable prototype + uploaded designs
        import os, tempfile
        from app import config as _cfg
        _cfg.UPLOAD_DIR = __import__("pathlib").Path(tempfile.mkdtemp())
        PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
        up = await c.post(f"/api/uiux/{sid}/upload/RELA-UI-002", files=[("files", ("vault_setup_screen.png", PNG, "image/png"))], data={"mode": "add"})
        assert up.status_code == 200, up.text
        m2 = next(u for u in up.json()["ui_modules"] if u["ui_id"] == "RELA-UI-002")
        shots = m2["doc"]["screens"]; assert [x["source"] for x in shots] == ["ai", "upload"] and shots[1]["name"] == "vault setup screen", shots
        fid = shots[1]["asset_id"]
        f = await c.get(f"/api/uiux/{sid}/file/{fid}"); assert f.status_code == 200 and f.headers["content-type"] == "image/png" and f.headers["x-content-type-options"] == "nosniff"
        bad = await c.post(f"/api/uiux/{sid}/upload/RELA-UI-002", files=[("files", ("x.svg", b"<svg onload=alert(1)>", "image/svg+xml"))]); assert bad.status_code == 415, bad.text
        s = await post(f"/api/uiux/{sid}/screens/move", {"item_id": "RELA-UI-002", "screen_id": shots[1]["screen_id"], "direction": -1})
        m2 = next(u for u in s["ui_modules"] if u["ui_id"] == "RELA-UI-002"); assert m2["doc"]["screens"][0]["source"] == "upload"
        s = await post(f"/api/uiux/{sid}/screens/update", {"item_id": "RELA-UI-002", "screen_id": shots[1]["screen_id"], "name": "Vault setup"})
        # rework with AI keeps the upload
        s = await post(f"/api/uiux/{sid}/comment", {"item_id": "RELA-UI-002", "comment": "add an empty state"})
        await post(f"/api/uiux/{sid}/accept", {"item_id": "RELA-UI-002"})
        s = (await c.get(f"/api/discovery/{sid}")).json()
        m2 = next(u for u in s["ui_modules"] if u["ui_id"] == "RELA-UI-002")
        assert any(x["source"] == "upload" and x["name"] == "Vault setup" for x in m2["doc"]["screens"]), m2["doc"]["screens"]
        pr = await c.get(f"/api/uiux/{sid}/prototype")
        assert pr.status_code == 200 and "data-goto" in pr.text and f"/api/uiux/{sid}/file/{fid}" in pr.text and 'id="pNext"' in pr.text
        pd = await c.get(f"/api/uiux/{sid}/prototype?download=1")
        assert "data:image/png;base64," in pd.text and "RelayReel_Prototype_vdraft.html" in pd.headers["content-disposition"], pd.headers
        open("/tmp/proto_test.html", "w").write(pr.text)
        # only screen left can't be removed
        one = next(u for u in s["ui_modules"] if u["ui_id"] == "RELA-UI-003")
        await post(f"/api/uiux/{sid}/screens/remove", {"item_id": "RELA-UI-003", "screen_id": one["doc"]["screens"][0]["screen_id"]}, 400)
        s = (await c.get(f"/api/discovery/{sid}")).json(); uis = s["ui_modules"]
        for u in uis:
            await post(f"/api/uiux/{sid}/accept", {"item_id": u["ui_id"]})
            s = await post(f"/api/uiux/{sid}/freeze/{u['ui_id']}", {})
        s = await post(f"/api/uiux/{sid}/baseline", {})
        assert s["stage"] == "complete", s["stage"]
        mx = await c.get(f"/api/uiux/{sid}/export/mockups.html")
        assert mx.status_code == 200 and "RelayReel_UI_UX_Mockups_v1.0.html" in mx.headers["content-disposition"]
        # --- product folders: every baseline filed, handover zip mirrors the workspace layout
        fl = (await c.get(f"/api/handover/{sid}/files")).json()
        want = {"RelayReel/Requirement/RelayReel_BRD_PRD_v1.0.docx", "RelayReel/Requirement/RelayReel_BRD_PRD_v1.1.docx",
                "RelayReel/Technical/RelayReel_TechDesign_v1.0.docx", "RelayReel/Technical/RelayReel_Technical_Stack_Charter_v1.0.md",
                "RelayReel/UI-UX/RelayReel_UI_UX_Mockups_v1.0.html", "RelayReel/UI-UX/RelayReel_Prototype_v1.0.html"}
        assert want <= set(fl["files"]), fl
        assert any(f.startswith("RelayReel/UI-UX/designs/") for f in fl["files"]), fl
        zp = await c.get(f"/api/handover/{sid}/pack.zip")
        import zipfile, io as _io
        names = set(zipfile.ZipFile(_io.BytesIO(zp.content)).namelist())
        assert zp.headers["content-disposition"].endswith('RelayReel_SDLC_Pack.zip"') and want <= names, names
        print("pack:", sorted(names))
        print("ALL OK")
asyncio.run(run())
