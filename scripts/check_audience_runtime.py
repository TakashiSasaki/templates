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


def validate_projection_parity(
    site_root: Path,
    model: dict,
    expected: dict,
    optional_destinations: set[str],
) -> None:
    documents = model.get("documents")
    routes = model.get("routes")
    assert isinstance(documents, dict), "assembled audience documents must be an object"
    assert isinstance(routes, dict), "assembled audience routes must be an object"

    expected_documents = expected["documents"]
    unexpected_documents = set(documents) - set(expected_documents)
    assert not unexpected_documents, f"unexpected assembled audience documents: {sorted(unexpected_documents)}"
    missing_required = set(expected_documents) - set(documents) - optional_destinations
    assert not missing_required, f"missing required audience documents: {sorted(missing_required)}"
    assert all(
        document == expected_documents[destination]
        for destination, document in documents.items()
    ), "assembled document audience projection drift"

    # Assembly may omit catalog documents whose optional source is absent. Keep
    # exactly the canonical routes for the documents that were actually built.
    expected_routes = {
        route: destination
        for route, destination in expected["routes"].items()
        if destination in documents
    }

    # Translation aliases are independently projected from actual published
    # records. Use that generated inventory, and require each alias to resolve to
    # an included canonical document with a real generated HTML page.
    reader_runtime = json.loads(
        (site_root / "reader-navigation-runtime.json").read_text(encoding="utf-8")
    )
    assert reader_runtime.get("schema_version") == 1, "invalid reader navigation runtime"
    assert isinstance(reader_runtime.get("locales"), list), "invalid reader locale inventory"
    aliases: dict[str, str] = {}
    for locale in reader_runtime["locales"]:
        assert isinstance(locale, dict) and isinstance(locale.get("routes"), dict), (
            "invalid reader locale routes"
        )
        for canonical_route, translated_route in locale["routes"].items():
            assert isinstance(canonical_route, str) and isinstance(translated_route, str), (
                "reader locale routes must be strings"
            )
            destination = expected_routes.get(canonical_route)
            assert destination is not None, f"translation aliases omitted document: {canonical_route}"
            assert (
                translated_route.startswith("/")
                and not translated_route.startswith("//")
                and translated_route.endswith("/")
                and ".." not in translated_route.split("/")
                and urlsplit(translated_route).path == translated_route
            ), f"invalid translated route: {translated_route}"
            html = site_root / translated_route.lstrip("/") / "index.html"
            assert html.is_file(), f"translation alias has no published page: {translated_route}"
            for alias in (translated_route, translated_route + "index.html"):
                previous = aliases.setdefault(alias, destination)
                assert previous == destination, f"conflicting translation alias: {alias}"

    complete_expected_routes = {**expected_routes, **aliases}
    assert routes == complete_expected_routes, "assembled audience route projection drift"


def skipped_optional_destinations(
    manifest,
    catalogs: dict[str, dict],
    publication_roots: dict[str, Path],
) -> set[str]:
    """Return destinations assembly may skip because an optional source is absent."""
    from scripts.publication_contract import resolve_without_symlinks

    skipped_destinations: set[str] = set()
    for document in manifest.documents:
        publication = document["publication"]
        catalog_document = catalogs[publication].get(document["document"])
        # Generated manifest documents have no provider-catalog record and are
        # required. Catalog-backed optional documents are skippable only when
        # the exact provider checkout lacks their declared source, matching the
        # successful assembly boundary rather than trusting the runtime output.
        if catalog_document is None or not catalog_document.optional:
            continue
        source = resolve_without_symlinks(
            publication_roots[publication],
            catalog_document.source,
            f"{publication}:{document['document']}",
        )
        if not source.exists():
            skipped_destinations.add(str(document["destination"]))
    return skipped_destinations


def check(
    site_root: Path,
    publication_roots: dict[str, Path],
    channel: str | None = "chrome",
) -> dict:
    from playwright.sync_api import sync_playwright

    model = json.loads((site_root / "audience-runtime.json").read_text())
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts.assemble_publications import load_manifest
    from scripts.audience_context import AudienceContextResolver
    from scripts.publication_contract import load_publication_catalog
    manifest = load_manifest(Path("site-manifest.json"))
    expected = AudienceContextResolver(manifest).export_runtime_map()
    catalogs = {
        publication: load_publication_catalog(
            root,
            label=f"{publication} publication catalog",
            validate_sources=False,
        ).documents_by_id
        for publication, root in publication_roots.items()
    }
    optional_destinations = skipped_optional_destinations(
        manifest, catalogs, publication_roots
    )
    validate_projection_parity(site_root, model, expected, optional_destinations)
    assert model["overviews"] == expected["overviews"], "assembled audience overview drift"
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
    parser.add_argument('--composition-root',type=Path,default=Path('../composition'))
    parser.add_argument('--policy-root',type=Path,default=Path('../policy'))
    args=parser.parse_args(); result=check(
        args.site_root,
        {"site": Path.cwd(), "composition": args.composition_root, "policy": args.policy_root},
        None if args.channel=='chromium' else args.channel,
    )
    args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
