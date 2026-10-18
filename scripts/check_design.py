"""Real-browser frontend acceptance checks; every injected response is local-only.

Run against: python -m http.server 8765 --bind 127.0.0.1 --directory docs
Optional QA dependencies: requirements-design.txt and npm install --prefix .qa-tools axe-core
No production Registry endpoint is used and no actual credentials are read.
"""
import copy
import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/design/qa"
OUT.mkdir(parents=True, exist_ok=True)
BASE = "http://127.0.0.1:8765"
MANIFEST = json.loads((ROOT / "docs/data/reports.json").read_text(encoding="utf-8"))
LATEST = json.loads((ROOT / "docs/reports" / MANIFEST[0]["files"]["json"]).read_text(encoding="utf-8"))
results = {"checks": [], "axe": [], "real_console_errors": [], "lab": {}}


def passed(name, **evidence):
    results["checks"].append({"name": name, "status": "PASS", **evidence})
    print("PASS", name, flush=True)


def fulfill(route, data, status=200):
    route.fulfill(status=status, content_type="application/json", body=json.dumps(data, ensure_ascii=False))


def loaded(page):
    page.goto(BASE, wait_until="networkidle")
    expect(page.locator(".front-lead h3")).to_be_visible()


def no_overflow(page):
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")


def axe(page, label):
    path = ROOT / ".qa-tools/node_modules/axe-core/axe.min.js"
    if not path.exists():
        raise RuntimeError("Install the optional axe-core dependency before acceptance QA")
    page.add_script_tag(path=str(path))
    report = page.evaluate("""async () => {
      const r = await axe.run(document, {runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa','wcag22aa']}});
      return {violations:r.violations.map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.map(n=>n.target)})),
        incomplete:r.incomplete.map(v=>({id:v.id,nodes:v.nodes.map(n=>({target:n.target,summary:n.failureSummary}))})),passes:r.passes.length};
    }""")
    results["axe"].append({"surface": label, **report})
    assert not report["violations"], json.dumps(report["violations"])


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width":1440,"height":900}, device_scale_factor=1)
        page.on("pageerror", lambda e: results["real_console_errors"].append(str(e)))
        page.on("console", lambda msg: results["real_console_errors"].append(msg.text) if msg.type == "error" else None)
        page.add_init_script("""window.qaPerf={lcp:0,cls:0,events:[]};
          new PerformanceObserver(l=>l.getEntries().forEach(e=>qaPerf.lcp=e.startTime)).observe({type:'largest-contentful-paint',buffered:true});
          new PerformanceObserver(l=>l.getEntries().forEach(e=>{if(!e.hadRecentInput)qaPerf.cls+=e.value})).observe({type:'layout-shift',buffered:true});
          new PerformanceObserver(l=>l.getEntries().forEach(e=>qaPerf.events.push({name:e.name,duration:e.duration}))).observe({type:'event',durationThreshold:16,buffered:true});
        """)
        loaded(page)
        results["lab"]["initial"] = page.evaluate("({lcp:qaPerf.lcp,cls:qaPerf.cls,resources:performance.getEntriesByType('resource').map(e=>({name:e.name,bytes:e.transferSize,duration:e.duration})),navigation:performance.getEntriesByType('navigation')[0].duration})")
        expect(page.locator("#newspaper-select option")).to_have_count(len(MANIFEST))
        expect(page.locator("#registry-admin-button")).to_be_hidden()
        assert page.locator("#source-count").inner_text() == str(LATEST["metrics"]["configured_sources"])
        passed("real manifest, metrics, eight sections and disconnected Registry", dates=len(MANIFEST))
        axe(page,"home-desktop")

        pages_by_id = {item["id"]: item for item in LATEST["newspaper"]["pages"]}
        for i in range(8):
            button = page.locator(".edition-tab").nth(i)
            section_id = button.get_attribute("data-page")
            button.click()
            expect(page.locator(".edition-tab[aria-selected=true]")).to_have_attribute("data-page",section_id)
            expect(page.locator("#newspaper-viewer")).to_have_attribute("aria-labelledby",f"tab-{section_id}")
            if section_id != "front":
                expected = len(pages_by_id[section_id]["items"])
                assert page.locator(".section-lead").count() + page.locator(".section-item").count() >= expected
        passed("all eight sections show their real payload items")
        page.locator(".edition-tab[aria-selected=true]").press("Home")
        expect(page.locator("#tab-front")).to_be_focused()
        page.locator("#tab-front").press("ArrowRight")
        expect(page.locator("#tab-opportunity")).to_be_focused()
        page.locator("#tab-opportunity").press("End")
        expect(page.locator("#tab-world")).to_be_focused()
        page.locator("#tab-world").press("Home")
        page.locator("#tab-front").press("Tab")
        expect(page.locator("#edition-notice summary")).to_be_focused()
        page.locator("#edition-notice summary").press("Tab")
        expect(page.locator("#newspaper-viewer")).to_be_focused()
        page.screenshot(path=str(OUT/"keyboard-focus.png"))
        passed("manual keyboard sequence: Home, arrows, End, Tab and visible panel focus")
        page.locator("[data-open-page=math]").click()
        expect(page.locator("#tab-math")).to_be_focused()
        page.locator("#newspaper-select").select_option(index=1)
        expect(page.locator(".section-no")).to_contain_text(MANIFEST[1]["date"])
        page.locator("#report-select").select_option(index=1)
        expect(page.locator("#report-viewer .eyebrow")).to_have_text(MANIFEST[1]["date"])
        passed("rundown opens section; independent newspaper and archive date selection")
        for name,ext in [("Markdown","md"),("LaTeX","tex")]:
            with page.expect_download() as event:
                page.get_by_role("link",name=name,exact=True).click()
            download = event.value
            target = ROOT / "docs/reports" / MANIFEST[1]["files"][ext]
            assert Path(download.path()).read_bytes() == target.read_bytes()
        assert page.get_by_role("link",name="PDF",exact=True).count() == 0
        passed("real Markdown and LaTeX downloads match files; unavailable PDF absent")
        # Opening a source is observed; remote availability is not an acceptance claim.
        original = page.locator(".front-lead .story-source a")
        href = original.get_attribute("href")
        with page.expect_popup() as popup_event:
            original.click()
        popup = popup_event.value
        popup.wait_for_url(href, wait_until="commit")
        assert popup.url == href
        popup.close()
        passed("original source opens in a new tab", url=href)
        page.get_by_role("button",name="数学 / AI for Math",exact=True).click()
        expect(page.get_by_role("button",name="数学 / AI for Math",exact=True)).to_have_attribute("aria-pressed","true")
        expect(page.locator("#source-list .source-item")).to_have_count(2)
        expect(page.locator("#source-list .health").first).to_contain_text("正常")
        passed("source group filter, pressed state and actual health records")
        results["lab"]["interactions"] = page.evaluate("({events:qaPerf.events,cls:qaPerf.cls})")
        for width,height in [(1440,900),(768,1024),(390,844),(320,720),(1920,1080)]:
            page.set_viewport_size({"width":width,"height":height})
            loaded(page)
            no_overflow(page)
            for text, target in [("日报","reports"),("信息源","sources"),("设置","settings"),("时报","newspaper")]:
                nav = page.get_by_role("navigation").get_by_role("link",name=text,exact=True)
                expect(nav).to_be_visible()
                rect = nav.bounding_box()
                assert rect["height"] >= 44 and rect["width"] >= 44
                nav.click()
                page.wait_for_timeout(300)
                assert page.url.endswith("#"+target)
            for i in range(8):
                page.locator(".edition-tab").nth(i).click()
                no_overflow(page)
                assert page.locator(".edition-tab").nth(i).bounding_box()["height"] >= 44
            page.locator(".edition-tab[aria-selected=true]").press("Home")
            if width == 320:
                axe(page,"home-320")
            passed(f"{width}x{height}: navigation, eight tabs, target sizes, no page overflow")
        page.emulate_media(reduced_motion="reduce")
        assert page.evaluate("getComputedStyle(document.documentElement).scrollBehavior") == "auto"
        assert page.locator(".edition-tab").first.evaluate("e=>getComputedStyle(e).transitionDuration") == "0s"
        passed("reduced-motion disables smooth scrolling and transitions")
        assert not results["real_console_errors"], results["real_console_errors"]
        passed("real-data browser console has no errors")
        page.close()

        # Simulated time exercises the actual five-minute browser interval.
        ctx = browser.new_context(viewport={"width":1440,"height":900})
        page = ctx.new_page()
        page.clock.install()
        loaded(page)
        page.locator(".front-lead summary").click()
        page.locator("#source-list .source-url").first.focus()
        page.clock.fast_forward(300001)
        page.wait_for_timeout(100)
        expect(page.locator(".front-lead details")).to_have_attribute("open","")
        expect(page.locator("#source-list .source-url").first).to_be_focused()
        page.route("**/reports/*.json*",lambda route: fulfill(route,{},503))
        page.clock.fast_forward(300001)
        expect(page.locator("#edition-notice")).to_contain_text("自动更新暂时失败")
        expect(page.locator(".front-lead h3")).to_be_visible()
        page.unroute("**/reports/*.json*")
        page.clock.fast_forward(300001)
        expect(page.locator("#edition-notice")).not_to_contain_text("自动更新暂时失败")
        page.locator("#newspaper-select").select_option(index=1)
        expect(page.locator(".section-no")).to_contain_text(MANIFEST[1]["date"])
        updated_manifest = [{"date":"LOCAL QA NEW EDITION","files":{"json":"local-new.json"}},*MANIFEST]
        page.route("**/data/reports.json*",lambda route: fulfill(route,updated_manifest))
        page.clock.fast_forward(300001)
        expect(page.locator("#newspaper-select option:checked")).to_have_text(MANIFEST[1]["date"])
        expect(page.locator(".section-no")).to_contain_text(MANIFEST[1]["date"])
        passed("actual five-minute refresh: expanded text preserved, failure/recovery, history remains selected")
        ctx.close()

        ctx = browser.new_context(viewport={"width":1440,"height":900})
        page = ctx.new_page()
        loaded(page)
        for select_id, check in [("newspaper-select",".section-no"),("report-select","#report-viewer .eyebrow")]:
            held = []
            pattern = "**/reports/"+MANIFEST[1]["files"]["json"]+"*"
            page.route(pattern,lambda route: held.append(route))
            page.locator("#"+select_id).select_option(index=1)
            page.wait_for_timeout(100)
            assert held
            viewer = "#newspaper-viewer" if select_id == "newspaper-select" else "#report-viewer"
            expect(page.locator(viewer+" [data-state=loading]")).to_be_visible()
            page.screenshot(path=str(OUT/(select_id+"-loading.png")))
            page.locator("#"+select_id).select_option(index=2)
            expect(page.locator(check)).to_contain_text(MANIFEST[2]["date"])
            old = json.loads((ROOT/"docs/reports"/MANIFEST[1]["files"]["json"]).read_text(encoding="utf-8"))
            for request in held: fulfill(request,old)
            page.wait_for_timeout(100)
            expect(page.locator(check)).to_contain_text(MANIFEST[2]["date"])
            page.unroute(pattern)
        passed("loading shown and delayed old date responses cannot overwrite a newer selection")
        ctx.close()

        # The rest uses isolated, marked browser response fixtures, never on-disk data.
        for case in ["manifest-error","report-error","sources-error","high-tags","empty-manifest","empty-pages","long-content"]:
            ctx = browser.new_context(viewport={"width":320,"height":720})
            page = ctx.new_page()
            if case == "manifest-error":
                page.route("**/data/reports.json*",lambda route: fulfill(route,{},503))
            elif case == "report-error":
                page.route("**/reports/*.json*",lambda route: fulfill(route,{},503))
            elif case == "empty-manifest":
                page.route("**/data/reports.json*",lambda route: fulfill(route,[]))
            elif case == "sources-error":
                page.route("**/data/sources.json",lambda route: fulfill(route,{},503))
            elif case == "high-tags":
                source={"name":"LOCAL QA LONG SOURCE","url":"https://example.com/"+"long"*120,"tags":["LOCAL-QA-LABEL-"+str(i) for i in range(40)],"watch":["LOCAL-QA-WATCH"*40],"group":"LOCAL QA GROUP"}
                page.route("**/data/sources.json",lambda route: fulfill(route,[source]))
            else:
                payload = copy.deepcopy(LATEST)
                for section in payload["newspaper"]["pages"]:
                    if case == "empty-pages": section["items"] = []
                    else:
                        for item in section["items"]:
                            item["title"] = "LOCAL QA FIXTURE — LongEnglishTitleWithoutBreaks" * 7
                            item["summary"] = "本地测试长文。" * 250
                page.route("**/reports/*.json*",lambda route, *, data=payload: fulfill(route,data))
            page.goto(BASE,wait_until="networkidle")
            if case == "sources-error":
                expect(page.locator("#source-list [data-state=error]")).to_be_visible()
                expect(page.locator("#source-groups button").first).to_be_disabled()
                page.locator("#sources").scroll_into_view_if_needed()
                page.screenshot(path=str(OUT/(case+".png")))
            elif case == "high-tags":
                page.locator("#sources").scroll_into_view_if_needed()
                expect(page.locator("#source-list .tag")).to_have_count(40)
                page.screenshot(path=str(OUT/(case+".png")))
            elif "error" in case:
                expect(page.locator("#newspaper-viewer [data-state=error]")).to_be_visible()
                assert page.locator("#newspaper-viewer").get_attribute("aria-busy") == "false"
                page.screenshot(path=str(OUT/(case+".png")))
                page.unroute_all()
                page.locator("#newspaper-viewer button").click()
                expect(page.locator(".front-lead h3")).to_be_visible()
            elif case == "empty-manifest":
                expect(page.locator("#newspaper-viewer [data-state=empty]")).to_be_visible()
                expect(page.locator("#newspaper-select")).to_be_disabled()
                page.screenshot(path=str(OUT/(case+".png")))
            elif case == "empty-pages":
                page.locator("#tab-ai").click()
                expect(page.locator(".paper-empty")).to_be_visible()
                page.screenshot(path=str(OUT/(case+".png")))
            else:
                page.locator(".front-lead summary").click()
                expect(page.locator(".front-lead details")).to_have_attribute("open","")
                page.screenshot(path=str(OUT/(case+".png")))
            no_overflow(page)
            passed("isolated fixture: " + case)
            ctx.close()

        ctx = browser.new_context(viewport={"width":390,"height":844})
        page = ctx.new_page()
        page.goto(BASE+"/admin.html",wait_until="networkidle")
        expect(page.locator("#connect-registry")).to_be_disabled()
        expect(page.locator("#admin-token")).to_be_disabled()
        expect(page.locator("#registry-editor")).to_be_hidden()
        axe(page,"admin-disconnected")
        passed("admin unconfigured: disabled token/connect, explicit disconnected state")
        page.route("**/data/runtime.json",lambda route: fulfill(route,{"registry_api_url":BASE+"/__qa_registry"}))
        registry = {"groups":[{"name":"LOCAL QA GROUP","enabled":True,"order":10}],"sources":[],"profile":{}}
        requests = []
        response_mode = {"value":"ok"}
        def registry_route(route):
            req = route.request
            requests.append({"method":req.method,"url":req.url})
            if response_mode["value"] == "fail": fulfill(route,{"detail":"LOCAL QA injected failure"},503)
            elif req.method == "PUT":
                body = req.post_data_json
                registry.update({"groups":body["groups"],"sources":body["sources"]})
                fulfill(route,{"registry":registry,"commits":[{"sha":"LOCAL-QA-ONLY"}]})
            else: fulfill(route,registry)
        page.route("**/__qa_registry",registry_route)
        page.reload(wait_until="networkidle")
        response_mode["value"] = "fail"
        page.locator("#admin-token").fill("LOCAL-QA-NOT-A-CREDENTIAL")
        page.locator("#connect-registry").click()
        expect(page.locator("#admin-message")).to_contain_text("连接失败")
        response_mode["value"] = "ok"
        page.locator("#admin-token").fill("LOCAL-QA-NOT-A-CREDENTIAL")
        page.locator("#connect-registry").click()
        expect(page.locator("#registry-editor")).to_be_visible()
        assert page.locator("#admin-token").input_value() == ""
        expect(page.locator("#save-registry")).to_be_disabled()
        page.locator("#new-group-name").fill("LOCAL QA ADDED")
        page.locator("#add-group-form button").click()
        expect(page.locator("#save-state")).to_have_attribute("data-dirty","true")
        page.locator("#discard-changes").click()
        expect(page.locator("#save-registry")).to_be_disabled()
        page.locator("#new-source-name").fill("LOCAL QA SOURCE")
        page.locator("#new-source-url").fill("https://example.com/" + "long/"*30)
        page.locator("#new-source-tags").fill(",".join("local-label-"+str(i) for i in range(25)))
        page.locator("#new-source-watch").fill("LONGKEYWORD"*30)
        page.locator("#add-source-form button").click()
        response_mode["value"] = "fail"
        page.locator("#save-registry").click()
        expect(page.locator("#admin-message")).to_contain_text("保存失败")
        expect(page.locator("#save-state")).to_have_attribute("data-dirty","true")
        response_mode["value"] = "ok"
        page.locator("#save-registry").click()
        expect(page.locator("#admin-message")).to_contain_text("保存成功")
        expect(page.locator("#save-registry")).to_be_disabled()
        assert page.evaluate("localStorage.length + sessionStorage.length") == 0
        for width in [1440,768,390,320]:
            page.set_viewport_size({"width":width,"height":900 if width>800 else 844})
            no_overflow(page)
            page.evaluate("window.scrollTo({top:0,behavior:'instant'})")
            page.screenshot(path=str(OUT/f"admin-local-fixture-{width}.png"),full_page=True)
        axe(page,"admin-configured-local-fixture")
        page.locator("#disconnect-registry").click()
        expect(page.locator("#registry-editor")).to_be_hidden()
        passed("local Registry fixture: connection failure/recovery, edits, discard, save failure/recovery, disconnect",requests=requests)
        passed("credential remains memory-only; input cleared; storage empty")
        ctx.close()
        browser.close()


if __name__ == "__main__":
    try:
        main()
    finally:
        (OUT/"results.json").write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding="utf-8")
