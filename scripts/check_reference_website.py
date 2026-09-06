#!/usr/bin/env python3
"""Exercise the actual Pages artifact against Site's Composition worksheets."""
from __future__ import annotations

import argparse
import functools
import json
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urljoin
from xml.etree import ElementTree


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def check_page(page, meta, canonical):
    require(page.title() == meta["title"], "document title does not match consumer contract")
    require(page.locator('meta[name="description"]').get_attribute("content") == meta["description"], "description mismatch")
    require(page.locator('link[rel="canonical"]').get_attribute("href") == canonical, "canonical mismatch")
    require(page.locator("main").count() > 0, "main landmark missing")
    require(page.locator("h1").first.is_visible(), "main heading is not visible")


def check_viewport(page):
    require(page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), "horizontal document overflow")


def viewport_probes(contract):
    # The zero-width baseline is not a physical device. Use Site's 360px
    # baseline probe and every declared positive breakpoint, including new ones.
    return sorted({360, *(v["minWidthPx"] for v in contract["viewports"] if v["minWidthPx"] > 0)})


def check_link(page, identity):
    links = page.locator(f'link[rel~="{identity["relation"]}"]')
    expected_href = urljoin(page.url, identity["href"])
    expected_type = identity.get("mediaType")
    expected_sizes = set(identity.get("sizes", []))

    def matches(link):
        if urljoin(page.url, link.get_attribute("href") or "") != expected_href:
            return False
        if expected_type is not None and (link.get_attribute("type") or "").strip().casefold() != expected_type.casefold():
            return False
        if "sizes" in identity and set((link.get_attribute("sizes") or "").split()) != expected_sizes:
            return False
        return True

    require(any(matches(links.nth(i)) for i in range(links.count())),
            f"missing browser identity: {expected_href}")


def check_manifest(actual, expected, routes, manifest_url):
    for key, value in (("name", expected["name"]), ("short_name", expected["shortName"]),
                       ("display", expected["display"]), ("orientation", expected["orientation"])):
        require(actual.get(key) == value, f"manifest {key} mismatch")
    for key, value in (("scope", expected["scope"]), ("start_url", routes[expected["startRouteId"]])):
        require(urljoin(manifest_url, actual.get(key, "")) == urljoin(manifest_url, value), f"manifest {key} mismatch")
    for icon in expected["icons"]:
        require(any(urljoin(manifest_url, item.get("src", "")) == urljoin(manifest_url, icon["href"])
                    and item.get("type") == icon["mediaType"]
                    and set(item.get("sizes", "").split()) == set(icon["sizes"])
                    and set(item.get("purpose", "any").split()) == set(icon["purposes"])
                    for item in actual.get("icons", [])), f"manifest icon intent mismatch: {icon['id']}")


def check(repository: Path, site_root: Path):
    from playwright.sync_api import sync_playwright
    def load(name):
        return json.loads((repository / "contracts" / f"{name}.json").read_text())
    routes = {r["id"]: r["path"] for r in load("routes")["routes"]}
    pages = {p["id"]: p for p in load("site-structure")["pages"]}
    discovery = load("site-discovery")
    identity = load("browser-identity")
    viewport = load("viewports")
    widths = viewport_probes(viewport)
    sitemap = {node.text for node in ElementTree.parse(site_root / "sitemap.xml").iter() if node.tag.endswith("}loc")}
    robots = (site_root / "robots.txt").read_text()
    require("Allow: /" in robots and discovery["canonicalOrigin"] + "/sitemap.xml" in robots, "robots discovery mismatch")
    class Handler(SimpleHTTPRequestHandler):
        def log_message(self, *_):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Handler, directory=str(site_root)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    checked = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="chrome")
            context = browser.new_context(service_workers="block")
            page = context.new_page()
            for meta in load("document-metadata")["pages"]:
                route = routes[pages[meta["pageId"]]["routeId"]]
                canonical = discovery["canonicalOrigin"] + route
                require(canonical in sitemap, f"sitemap omitted {route}")
                response = page.goto(f"http://127.0.0.1:{server.server_port}" + route, wait_until="domcontentloaded")
                require(response.status == 200, f"unreachable route: {route}")
                check_page(page, meta, canonical)
                for width in widths:
                    page.set_viewport_size({"width":width,"height":900})
                    check_viewport(page)
                # Prove that the browser assertion rejects a corrupted product
                # value, rather than accepting any schema-valid declaration.
                page.evaluate("document.title = 'invalid consumer title'")
                try:
                    check_page(page, meta, canonical)
                except AssertionError:
                    pass
                else:
                    raise AssertionError("negative title proof did not reject corruption")
                page.evaluate("value => document.title = value", meta["title"])
                page.locator("h1").first.evaluate("element => element.style.visibility = 'hidden'")
                try:
                    check_page(page, meta, canonical)
                except AssertionError:
                    pass
                else:
                    raise AssertionError("negative page-structure proof accepted a hidden heading")
                page.locator("h1").first.evaluate("element => element.style.visibility = ''")
                checked.append(meta["pageId"])
            page.goto(f"http://127.0.0.1:{server.server_port}/", wait_until="domcontentloaded")
            for width in widths:
                page.set_viewport_size({"width":width,"height":900})
                check_viewport(page)
                page.evaluate("document.body.insertAdjacentHTML('beforeend', '<div id=negative-overflow style=width:20000px;height:1px></div>')")
                try:
                    check_viewport(page)
                except AssertionError:
                    pass
                else:
                    raise AssertionError("negative viewport proof accepted document overflow")
                page.locator("#negative-overflow").evaluate("element => element.remove()")
            page.keyboard.press("Tab")
            require(page.evaluate("document.activeElement !== document.body"), "keyboard navigation unavailable")
            check_link(page, identity["favicon"])
            icons = page.locator(f'link[rel~="{identity["favicon"]["relation"]}"]')
            require(icons.count() > 0, "favicon missing")
            icon_markup = icons.first.evaluate("element => element.outerHTML")
            for fallback in identity["favicon"]["fallbacks"]:
                check_link(page, {**fallback, "relation": identity["favicon"]["relation"]})
            icons.evaluate_all("elements => elements.forEach(element => element.remove())")
            try:
                check_link(page, identity["favicon"])
            except AssertionError:
                pass
            else:
                raise AssertionError("negative identity proof accepted missing favicon")
            page.evaluate("markup => document.head.insertAdjacentHTML('beforeend', markup)", icon_markup)
            expected = load("pwa-manifest")
            ios_identity = expected["platformCompatibility"]["ios"]["homeScreenIcon"]
            check_link(page, ios_identity)
            check_link(page, {"relation": "manifest", "href": expected["manifestPath"]})
            manifest_url = urljoin(page.url, expected["manifestPath"])
            manifest = context.request.get(manifest_url).json()
            check_manifest(manifest, expected, routes, manifest_url)
            for icon in expected["icons"]:
                response = context.request.get(urljoin(manifest_url, icon["href"]))
                require(response.status == 200, "icon unreachable")
                if icon["mediaType"] == "image/png":
                    require(response.body().startswith(b"\x89PNG\r\n\x1a\n"), "invalid raster fallback")
            # Exercise both landing paths and the existing canonical projection.
            # Product-wide browser identity must survive localization rather than
            # only matching on the primary English document.
            for prefix, language in (("", "en"), ("/ja", "ja")):
                page.goto(f"http://127.0.0.1:{server.server_port}{prefix}/", wait_until="domcontentloaded")
                check_link(page, identity["favicon"])
                for fallback in identity["favicon"]["fallbacks"]:
                    check_link(page, {**fallback, "relation": identity["favicon"]["relation"]})
                check_link(page, ios_identity)
                page.locator('section[aria-labelledby="portal-reference-consumer-title"] a').click()
                page.wait_for_url(f"**{prefix}/coexistence/#self-hosting-reference-consumer")
                require(page.locator("html").get_attribute("lang") == language, "reference explanation locale mismatch")
                require(page.locator("#self-hosting-reference-consumer").count() == 1, "reference anchor missing")
            projection = context.request.get(f"http://127.0.0.1:{server.server_port}/reference-consumer.json").json()
            require(projection == json.loads((repository / "assets/reference-consumer.json").read_text()), "served reference projection mismatch")
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    return {"status":"passed","pages":checked,"viewports":widths}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--site-root", type=Path, default=Path("build/site"))
    args = parser.parse_args()
    print(json.dumps(check(args.repository, args.site_root)))
