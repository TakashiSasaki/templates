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


def check(repository: Path, site_root: Path):
    from playwright.sync_api import sync_playwright
    def load(name):
        return json.loads((repository / "contracts" / f"{name}.json").read_text())
    routes = {r["id"]: r["path"] for r in load("routes")["routes"]}
    pages = {p["id"]: p for p in load("site-structure")["pages"]}
    discovery = load("site-discovery")
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
            for width in (360, 1280):
                page.set_viewport_size({"width":width,"height":900})
                require(page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), f"horizontal overflow at {width}px")
            page.keyboard.press("Tab")
            require(page.evaluate("document.activeElement !== document.body"), "keyboard navigation unavailable")
            require(page.locator('link[rel="icon"]').count() > 0, "favicon missing")
            require(page.locator('link[rel="apple-touch-icon"]').get_attribute("href") == "/icon-180.png", "iOS icon missing")
            manifest_href = page.locator('link[rel="manifest"]').get_attribute("href")
            manifest = context.request.get(urljoin(page.url, manifest_href)).json()
            expected = load("pwa-manifest")
            for key, value in (("name",expected["name"]),("short_name",expected["shortName"]),("scope",expected["scope"]),("display",expected["display"])):
                require(manifest[key] == value, f"manifest {key} mismatch")
            for icon in expected["icons"]:
                require(any(x["src"] == icon["href"] and x["type"] == icon["mediaType"] for x in manifest["icons"]), "manifest icon missing")
                response = context.request.get(urljoin(page.url, icon["href"]))
                require(response.status == 200, "icon unreachable")
                if icon["mediaType"] == "image/png":
                    require(response.body().startswith(b"\x89PNG\r\n\x1a\n"), "invalid raster fallback")
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    return {"status":"passed","pages":checked,"viewports":[360,1280]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--site-root", type=Path, default=Path("build/site"))
    args = parser.parse_args()
    print(json.dumps(check(args.repository, args.site_root)))
