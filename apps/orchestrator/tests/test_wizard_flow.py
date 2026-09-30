# End-to-end check of the wizard API with the AI tier stubbed.
# Run from apps/orchestrator:  python tests/test_wizard_flow.py
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
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
    if f == ai_router.Feature.MODULE_BREAKDOWN:
        return {"text": '{"modules":[{"name":"Ingestion Vault","description":"captures forwards","platform_core":false},{"name":"Catalogue","description":"genre/topic","platform_core":false},{"name":"Auth & Identity","description":"login","platform_core":true}]}'}
    if f == ai_router.Feature.TECH_DESIGN_GENERATION:
        return {"text": "1. User forwards\n2. Webhook stores\n3. UI shows"}
    if f == ai_router.Feature.BRD_PRD_DRAFTING:
        await asyncio.sleep(0.05)
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
ai_router.generate = fake

async def fake_check(client, d):
    from app.models import DomainCheck
    return DomainCheck(domain=d, status="taken" if d.endswith(".com") and not d.startswith("get") else "available", method="rdap")
identity.check_domain = fake_check

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
        s = await post("/api/identity/complete", {"session_id": sid}); assert s["stage"] == "freeze"
        s = await post("/api/wizard/freeze", {"session_id": sid}); assert s["stage"] == "freeze" and len(s["module_specs"]) == 3, s
        print("modules:", s["modules"])
        specs = s["module_specs"]; specs.append({"name": "Repurpose Studio", "description": "text/image/video", "platform_core": False}); specs[1]["name"] = "Genre & Topic Catalogue"
        s = await post("/api/wizard/modules/save", {"session_id": sid, "modules": specs})
        await post("/api/wizard/modules/save", {"session_id": sid, "modules": specs + [specs[0]]}, 400)
        s = await post("/api/wizard/modules/confirm", {"session_id": sid}); assert s["stage"] == "flow"
        s = await post("/api/wizard/flows/generate", {"session_id": sid}); assert len(s["module_flows"]) == 3, [f["module"] for f in s["module_flows"]]
        m = s["module_flows"][0]["module"]
        s = await post("/api/wizard/flows/update", {"session_id": sid, "module": m, "steps": ["A", " ", "B edited", "C new"]})
        assert s["module_flows"][0]["steps"] == ["A", "B edited", "C new"]
        await post("/api/wizard/flows/freeze", {"session_id": sid}, 400)
        for f in s["module_flows"]:
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
        assert g["status"] == "failed" and g["done"] == 3
        s = await post("/api/wizard/generate/retry", {"session_id": sid})
        for _ in range(40):
            await asyncio.sleep(0.15)
            s = (await c.get(f"/api/discovery/{sid}")).json()
            if s["generation"]["status"] != "running": break
        g = s["generation"]
        reqs = (await c.get(f"/api/brdprd/{sid}/requirements")).json()
        print("after retry:", g["status"], g["done"], "/", g["total"], "stage", s["stage"], "reqs", [r["req_id"] for r in reqs])
        assert g["status"] == "done" and s["stage"] == "manager" and len(reqs) == 4
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
        print("ALL OK")
asyncio.run(run())
