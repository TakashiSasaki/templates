#!/usr/bin/env python3
"""Qualify audience semantics in the assembled portal and its real navigation lifecycle."""
from __future__ import annotations
import argparse
import re
import functools
import json
import threading
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


def check(site_root: Path, channel: str | None = "chrome") -> dict:
    from playwright.sync_api import sync_playwright

    model = json.loads((site_root / "audience-runtime.json").read_text())
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts.audience_context import create_resolver
    expected = create_resolver().export_runtime_map()
    assert model["documents"] == expected["documents"], "assembled document audience projection drift"
    assert model["overviews"] == expected["overviews"], "assembled audience overview drift"
    assert all(model["routes"].get(r) == d for r, d in expected["routes"].items())
    provenance = json.loads((site_root / "build-provenance.json").read_text())
    assert model["audiences"] == ["use", "maintain"]
    # Every canonical published page must load the single generated controller.
    documents = model["documents"]
    def route(destination):
        return next(p for p, d in model["routes"].items() if d == destination and p.startswith("/") and p.endswith("/"))
    for destination in documents:
        html = site_root / route(destination).lstrip("/") / "index.html"
        assert html.is_file(), f"missing canonical document: {html}"
        assert len(re.findall(r'<script\b[^>]*src="[^"]*javascripts/audience-context\.js"', html.read_text())) == 1, str(html)
    class Handler(SimpleHTTPRequestHandler):
        def log_message(self, *_): pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Handler, directory=str(site_root)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    results = []
    def state(page, audience):
        page.wait_for_function("a => document.documentElement.dataset.audience === a", arg=audience)
        if audience != "neutral":
            assert page.evaluate("sessionStorage.getItem('templates-audience-context')") == audience
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(**({"channel": channel} if channel else {}))
            for path, expected in [('/web/', 'use'), ('/policy/contributing/', 'maintain'),
                    ('/composition/architecture/composer-mvp/', 'use'), ('/policy/architecture/', 'maintain'),
                    ('/?audience=maintain', 'neutral'), ('/policy/architecture/?audience=admin', 'maintain'),
                    ('/web/?audience=maintain', 'use'), ('/policy/contributing/?audience=use', 'maintain'),
                    ('/policy/architecture/?audience=use', 'use')]:
                context = browser.new_context(service_workers="block")
                page = context.new_page()
                assert page.goto(base + path).status == 200
                state(page, expected)
                assert page.locator('link[rel="canonical"]').get_attribute('href').split('?')[0].endswith(urlsplit(path).path)
                results.append({'direct': path, 'audience': expected})
                context.close()
            context = browser.new_context(service_workers="block")
            page = context.new_page()
            requests = []
            page.on('request', lambda r: requests.append(r.url) if urlsplit(r.url).path == '/audience-runtime.json' else None)
            page.goto(base + '/composition/architecture/composer-mvp/')
            state(page, 'use')
            page.wait_for_function('!!window.document$')
            page.evaluate("window.audienceProbe = {events: []}; addEventListener('templates:audience-changed', e => audienceProbe.events.push(e.detail.audience))")
            def navigate(path, expected):
                page.evaluate("""path => {
                    const link = document.createElement('a'); link.href = path;
                    link.textContent = 'Audience qualification destination';
                    document.querySelector('main').append(link); link.click();
                }""", path)
                page.wait_for_url(base + path)
                state(page, expected)
                assert page.evaluate('!!window.audienceProbe'), 'navigation reloaded instead of using document$'
            navigate('/policy/contributing/', 'maintain')
            page.go_back(); page.wait_for_url(base + '/composition/architecture/composer-mvp/'); state(page, 'use')
            page.go_forward(); page.wait_for_url(base + '/policy/contributing/'); state(page, 'maintain')
            navigate('/web/', 'use')
            navigate('/policy/architecture/', 'use')
            navigate('/composition/architecture/composer-mvp/', 'use')
            # Switch uses an actual delegated control, preserves fragment and unrelated history state.
            fragment = page.locator('h1').first.get_attribute('id')
            page.evaluate("""fragment => {
                history.replaceState({...history.state, qualification: 42}, '', '#' + fragment);
                const button = document.createElement('button'); button.dataset.audienceSwitch = 'maintain';
                button.id = 'audience-probe-switch'; document.querySelector('main').append(button);
            }""", fragment)
            page.locator('#audience-probe-switch').evaluate('button => button.click()')
            state(page, 'maintain')
            assert urlsplit(page.url).fragment == fragment
            assert page.evaluate('history.state.qualification') == 42
            assert page.evaluate('!!window.audienceProbe')
            navigate('/policy/architecture/', 'maintain')
            # Re-evaluate script + initialization and actual document$ emissions.
            before = page.evaluate('audienceProbe.events.length')
            page.add_script_tag(content=(site_root/'javascripts/audience-context.js').read_text())
            page.evaluate("TemplatesAudienceContext.init(); TemplatesAudienceContext.init(); dispatchEvent(new Event('pageshow'))")
            page.wait_for_timeout(150)
            assert page.evaluate('audienceProbe.events.length') == before, 'duplicate state event after initialization'
            navigate('/web/', 'use')
            assert page.evaluate('audienceProbe.events.length') == before + 1, 'duplicate navigation listeners/events'
            assert len(requests) == 1, f'duplicate runtime fetches: {requests}'
            # Shared services/root do not erase the stored reading journey.
            page.goto(base + '/?audience=maintain'); state(page, 'neutral')
            assert page.evaluate("sessionStorage.getItem('templates-audience-context')") == 'use'
            results.append({'instant_navigation': 'use/maintain, shared journey, history, switch, fragment, repeated initialization passed'})
            context.close()
            for path, target, overview in [('/web/', 'maintain', '/repository-trees/'),
                    ('/policy/contributing/', 'use', '/web/'), ('/', 'maintain', '/repository-trees/')]:
                context = browser.new_context(service_workers='block'); page = context.new_page()
                page.goto(base + path)
                state(page, 'neutral' if path == '/' else ('use' if path == '/web/' else 'maintain'))
                page.evaluate("target => TemplatesAudienceContext.switchAudience(target)", target)
                page.wait_for_url(base + overview); state(page, target)
                results.append({'switch_from': path, 'target': target, 'overview': overview})
                context.close()
            context = browser.new_context(service_workers='block')
            context.route('**/audience-runtime.json', lambda route: route.fulfill(
                json={'schema_version': 99, 'audiences': ['admin']}))
            page = context.new_page(); page.goto(base + '/policy/contributing/'); state(page, 'neutral')
            context.close(); results.append({'invalid_projection': 'neutral, no fabricated membership'})
            # Every actual translation alias retains the canonical membership model.
            translated = [(r,d) for r,d in model['routes'].items() if r.startswith('/ja/') and r.endswith('/')]
            assert translated, 'assembled audience map omitted published translation aliases'
            for r,d in translated:
                assert d in documents
            r,d = next((r,d) for r,d in translated if documents[d]['primary'] == 'maintain' and not documents[d]['is_landing'])
            context = browser.new_context(service_workers='block'); page=context.new_page()
            page.goto(base+r); state(page, documents[d]['primary']); context.close()
            results.append({'translation_aliases': len(translated), 'maintain_direct': r})
            # Offline reload uses the actual registered worker and precached projection/controller.
            context = browser.new_context(); page=context.new_page()
            page.goto(base+'/policy/contributing/'); state(page,'maintain')
            page.evaluate('navigator.serviceWorker.ready')
            page.wait_for_function('!!navigator.serviceWorker.controller')
            page.reload(); state(page,'maintain')
            page.wait_for_function("""async () => {
                const names=await caches.keys();
                for(const name of names) {
                    const cache=await caches.open(name);
                    if(await cache.match('/audience-runtime.json') && await cache.match('/javascripts/audience-context.js')) return true;
                } return false;
            }""")
            context.set_offline(True); page.reload(wait_until='domcontentloaded'); state(page,'maintain')
            results.append({'offline_reload': 'maintain page, controller and manifest projection available'})
            context.close(); browser.close()
    finally: server.shutdown(); server.server_close()
    return {'status':'passed', 'provenance':provenance, 'canonical_documents':len(documents), 'checks':results}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site-root',type=Path,default=Path('build/site'))
    parser.add_argument('--output',type=Path,default=Path('build/audience-runtime.json'))
    parser.add_argument('--channel',default='chrome',help='Browser channel; chromium uses Playwright bundled Chromium')
    args=parser.parse_args(); result=check(args.site_root, None if args.channel=='chromium' else args.channel)
    args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
