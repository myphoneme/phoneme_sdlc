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
    if f == ai_router.Feature.MODULE_BREAKDOWN:
        return {"text": '{"modules":[{"name":"Ingestion Vault","description":"captures forwards","platform_core":false},{"name":"Catalogue","description":"genre/topic","platform_core":false},{"name":"Auth & Identity","description":"login","platform_core":true}]}'}
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
        # --- consistency check
        s = await post(f"/api/brdprd/{sid}/consistency", {})
        assert s["consistency"]["issues"][0]["documents"] == ["RELA-001", "RELA-002"], s["consistency"]
        # --- redefine scope
        await post(f"/api/wizard/modules/consolidate", {"session_id": sid, "instruction": "small"}, 409)
        await post(f"/api/brdprd/{sid}/freeze/RELA-001", {})
        s = await post("/api/wizard/reopen-scope", {"session_id": sid, "reason": "too many modules"})
        assert s["stage"] == "freeze" and s["scope_revision"] == 1 and s["consistency"] is None
        arch = s["requirement_archive"][0]
        assert len(arch["requirements"]) == 9 and any(r["status"] == "Frozen" for r in arch["requirements"]), [r["req_id"] for r in arch["requirements"]]
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
        print("ALL OK")
asyncio.run(run())
