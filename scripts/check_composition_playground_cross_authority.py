#!/usr/bin/env python3
"""Exercise the real Composition Playground provider artifact through the built Site."""

from __future__ import annotations

import argparse
import gzip
import json
import re
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

FULL_SHA = re.compile(r"^[0-9a-f]{40}$")


class CrossAuthorityError(RuntimeError):
    pass


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CrossAuthorityError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CrossAuthorityError(f"expected object in {path}")
    return value


def validate_built_inputs(
    site_root: Path,
    *,
    expected_site_revision: str,
    expected_provider_revision: str,
    expected_semantic_revision: str,
) -> None:
    provenance = read_json(site_root / "build-provenance.json")
    if provenance.get("schema_version") != 2 or provenance.get("repository") != "TakashiSasaki/templates":
        raise CrossAuthorityError("built Site provenance contract is invalid")
    if provenance.get("site_commit") != expected_site_revision:
        raise CrossAuthorityError(
            f"built Site revision mismatch: {provenance.get('site_commit')} != {expected_site_revision}"
        )
    publications = provenance.get("publication_commits")
    if not isinstance(publications, dict):
        raise CrossAuthorityError("built Site provenance has no publication commits")
    if publications.get("composition") != expected_provider_revision:
        raise CrossAuthorityError(
            "built Site did not use the exact candidate Composition provider revision"
        )
    if not FULL_SHA.fullmatch(str(publications.get("policy", ""))):
        raise CrossAuthorityError("built Site provenance has no exact Policy revision")

    projection_path = site_root / "composition" / "playground" / "composition-playground-v1.json.gz"
    try:
        projection = json.loads(gzip.decompress(projection_path.read_bytes()))
    except (OSError, EOFError, gzip.BadGzipFile, json.JSONDecodeError) as exc:
        raise CrossAuthorityError(f"cannot decode assembled Playground projection: {exc}") from exc
    if projection.get("projection_id") != "composition-playground-v1" or projection.get("schema_version") != 1:
        raise CrossAuthorityError("assembled Playground projection identity is invalid")
    source = projection.get("source")
    if not isinstance(source, dict) or source.get("revision") != expected_semantic_revision:
        raise CrossAuthorityError("assembled Playground semantic revision is not the expected candidate semantic source")
    if expected_semantic_revision == expected_provider_revision:
        raise CrossAuthorityError(
            "cross-authority regression must cover the publication-only descendant provenance case"
        )


def serve(root: Path) -> tuple[ThreadingHTTPServer, threading.Thread, str]:
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, directory=str(root), **kwargs)

        def log_message(self, format: str, *args: Any) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    return server, thread, f"http://{host}:{port}"


def assert_no_horizontal_overflow(page: Any, expected_width: int = 360) -> None:
    metrics = page.evaluate(
        """() => ({
          innerWidth: window.innerWidth,
          clientWidth: document.documentElement.clientWidth,
          scrollWidth: document.documentElement.scrollWidth
        })"""
    )
    if metrics["innerWidth"] != expected_width or metrics["clientWidth"] != expected_width:
        raise CrossAuthorityError(f"unexpected narrow viewport metrics: {metrics}")
    if metrics["scrollWidth"] > metrics["clientWidth"] + 1:
        diagnostics = page.evaluate(
            """() => {
              const viewport = document.documentElement.clientWidth;
              const root = document.querySelector('#composition-playground');
              if (!root) return { offenders: [], ancestors: [] };
              const describe = (node) => {
                const rect = node.getBoundingClientRect();
                const style = getComputedStyle(node);
                return {
                  tag: node.tagName,
                  id: node.id || '',
                  className: typeof node.className === 'string' ? node.className : '',
                  left: Math.round(rect.left * 10) / 10,
                  right: Math.round(rect.right * 10) / 10,
                  width: Math.round(rect.width * 10) / 10,
                  clientWidth: node.clientWidth,
                  scrollWidth: node.scrollWidth,
                  display: style.display,
                  boxSizing: style.boxSizing,
                  cssWidth: style.width,
                  minWidth: style.minWidth,
                  maxWidth: style.maxWidth,
                  marginLeft: style.marginLeft,
                  marginRight: style.marginRight,
                  paddingLeft: style.paddingLeft,
                  paddingRight: style.paddingRight,
                  flex: style.flex,
                  overflowX: style.overflowX,
                  whiteSpace: style.whiteSpace,
                  overflowWrap: style.overflowWrap,
                  text: (node.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 120)
                };
              };
              const offenders = Array.from(root.querySelectorAll('*'))
                .map(describe)
                .filter((item) => item.right > viewport + 1 || item.left < -1 || item.scrollWidth > item.clientWidth + 1)
                .sort((left, right) => Math.max(right.right - viewport, right.scrollWidth - right.clientWidth) - Math.max(left.right - viewport, left.scrollWidth - left.clientWidth))
                .slice(0, 12);
              const ancestors = [];
              for (let node = root; node; node = node.parentElement) ancestors.push(describe(node));
              return { offenders, ancestors };
            }"""
        )
        raise CrossAuthorityError(
            f"Playground has horizontal overflow at {expected_width}px: "
            f"{metrics}; offenders={diagnostics['offenders']}; ancestors={diagnostics['ancestors']}"
        )


def assert_text_contains(page: Any, selector: str, expected: str) -> None:
    text = page.locator(selector).text_content() or ""
    if expected not in text:
        raise CrossAuthorityError(f"{selector} is missing {expected!r}: {text[:500]!r}")



def assert_desktop_reader_column(page: Any) -> None:
    metrics = page.evaluate(
        """() => ({
          innerWidth: window.innerWidth,
          clientWidth: document.documentElement.clientWidth,
          scrollWidth: document.documentElement.scrollWidth,
          readerWidth: document.querySelector('#composition-playground')?.getBoundingClientRect().width || 0
        })"""
    )
    if metrics["innerWidth"] != 1024 or metrics["clientWidth"] != 1024:
        raise CrossAuthorityError(f"unexpected desktop viewport metrics: {metrics}")
    if metrics["readerWidth"] >= 950 or metrics["scrollWidth"] > metrics["clientWidth"] + 1:
        raise CrossAuthorityError(f"built Site reader column overflows at desktop width: {metrics}")


def wait_for_initial_playground(page: Any) -> None:
    try:
        page.wait_for_selector("[data-playground-app]:not([hidden])", timeout=5000)
    except Exception as exc:
        diagnostics = page.evaluate(
            """() => ({
              url: location.href,
              siteRevisionMeta: document.querySelector('meta[name="templates-site-revision"]')?.getAttribute('content') || null,
              appHidden: document.querySelector('[data-playground-app]')?.hidden ?? null,
              explainHidden: document.querySelector('[data-playground-explain]')?.hidden ?? null,
              error: document.querySelector('#composition-playground')?.dataset.playgroundError || null,
              status: document.querySelector('[data-playground-status]')?.textContent || ''
            })"""
        )
        raise CrossAuthorityError(
            f"built Site initial mount did not become visible: {diagnostics}"
        ) from exc


def run_browser_check(
    site_root: Path,
    *,
    expected_provider_revision: str,
    expected_semantic_revision: str,
) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise CrossAuthorityError("Playwright is required; install requirements-visual.txt") from exc

    server, thread, base_url = serve(site_root)
    provenance_path = site_root / "build-provenance.json"
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="chrome")
            page = browser.new_page(viewport={"width": 360, "height": 800})
            page_errors: list[str] = []
            provider_requests: list[str] = []
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            page.on("request", lambda request: provider_requests.append(request.url) if request.url.endswith("/composition/playground/composition-playground-v1.json.gz") else None)
            page.goto(
                f"{base_url}/playground/#recipe=skill&include=capability.cli",
                wait_until="networkidle",
            )
            wait_for_initial_playground(page)
            page.wait_for_selector("[data-playground-explain]:not([hidden])")
            if len(provider_requests) != 1:
                raise CrossAuthorityError(f"expected one projection request for one real mount: {provider_requests}")

            if page.locator("[data-playground-semantic-revision]").text_content() != expected_semantic_revision:
                raise CrossAuthorityError("browser did not display the projection semantic source revision")
            if page.locator("[data-playground-provider-revision]").text_content() != expected_provider_revision:
                raise CrossAuthorityError("browser did not display the exact Site-selected provider revision")
            if page.locator("[data-playground-projection-id]").text_content() != "composition-playground-v1":
                raise CrossAuthorityError("browser did not display the Playground projection identity")
            if page.locator("[data-playground-recipe]").input_value() != "skill":
                raise CrossAuthorityError("shareable URL did not select the production skill recipe")
            if not page.locator('input[type="checkbox"][value="capability.cli"]').is_checked():
                raise CrossAuthorityError("shareable URL did not restore capability.cli")

            resolved = page.locator("[data-playground-resolved]").text_content() or ""
            for component in (
                "artifact.skill-core",
                "capability.cli",
                "capability.runtime",
                "lifecycle.implementation-evidence",
                "lifecycle.contract-evolution",
                "lifecycle.lifecycle-checkpoints",
            ):
                if component not in resolved:
                    raise CrossAuthorityError(f"real canonical Skill case is missing {component}")

            config = json.loads(page.locator("[data-playground-config]").text_content() or "{}")
            expected_config = {
                "schema_version": 1,
                "recipe": "skill",
                "components": {"include": ["capability.cli"], "exclude": []},
                "parameters": {},
            }
            if config != expected_config:
                raise CrossAuthorityError(f"generated composition.json configuration differs: {config}")

            explanation = page.locator("[data-playground-explain]").text_content() or ""
            for expected in (
                "Why selected?",
                "Required directly by capability.cli.",
                "cli_interface",
                "implementation_evidence",
                "contracts/cli-interface.json",
                "ownership: seed",
                "Canonical empty-target initial plan:",
            ):
                if expected not in explanation:
                    raise CrossAuthorityError(f"real explainability output is missing {expected!r}")
            assert_no_horizontal_overflow(page)
            page.set_viewport_size({"width": 1024, "height": 900})
            page.reload(wait_until="networkidle")
            page.wait_for_selector("[data-playground-app]:not([hidden])")
            page.wait_for_selector("[data-playground-explain]:not([hidden])")
            assert_no_horizontal_overflow(page, expected_width=1024)
            assert_desktop_reader_column(page)
            page.set_viewport_size({"width": 959, "height": 900})
            page.reload(wait_until="networkidle")
            page.wait_for_selector("[data-playground-app]:not([hidden])")
            assert_no_horizontal_overflow(page, expected_width=959)
            page.set_viewport_size({"width": 360, "height": 800})
            page.reload(wait_until="networkidle")
            page.wait_for_selector("[data-playground-app]:not([hidden])")

            cli = page.locator('input[type="checkbox"][value="capability.cli"]')
            cli.uncheck()
            page.wait_for_function("() => !location.hash.includes('include=capability.cli')")
            without_cli = page.locator("[data-playground-resolved]").text_content() or ""
            if "capability.cli" in without_cli:
                raise CrossAuthorityError("optional component change did not select a new canonical case")
            cli.check()
            page.wait_for_function("() => location.hash.includes('include=capability.cli')")
            page.reload(wait_until="networkidle")
            page.wait_for_selector("[data-playground-app]:not([hidden])")
            if not page.locator('input[type="checkbox"][value="capability.cli"]').is_checked():
                raise CrossAuthorityError("shareable URL/hash did not round-trip after case changes")
            assert_no_horizontal_overflow(page)

            page.wait_for_function("() => navigator.serviceWorker?.controller !== null")
            page.reload(wait_until="networkidle")
            page.wait_for_selector("[data-playground-app]:not([hidden])")
            page.wait_for_function(
                """async () => {
                  const url = new URL(location.href);
                  url.hash = "";
                  const cache = await caches.open("templates-portal-documents-v1");
                  return Boolean(await cache.match(url.href));
                }"""
            )
            if not page.evaluate(
                """async () => {
                  const url = new URL(location.href);
                  url.hash = "";
                  const cache = await caches.open("templates-portal-documents-v1");
                  const cached = await cache.match(url.href);
                  if (!cached) return false;
                  const headers = new Headers(cached.headers);
                  headers.delete("Content-Encoding");
                  headers.delete("Content-Length");
                  await cache.put(
                    url.href,
                    new Response(await cached.arrayBuffer(), {
                      status: cached.status,
                      statusText: cached.statusText,
                      headers,
                    })
                  );
                  return true;
                }"""
            ):
                raise CrossAuthorityError("Service Worker did not persist cached Playground HTML")
            page.context.set_offline(True)
            page.reload(wait_until="domcontentloaded")
            page.wait_for_function(
                "() => document.querySelector('[data-playground-status]')?.textContent !== "
                "'Loading the canonical Composition projection…'"
            )
            offline_metrics = page.evaluate(
                """() => {
                  const root = document.querySelector('#composition-playground');
                  const app = document.querySelector('[data-playground-app]');
                  const explain = document.querySelector('[data-playground-explain]');
                  const status = document.querySelector('[data-playground-status]');
                  return {
                    hasRoot: Boolean(root),
                    appHidden: app?.hidden ?? false,
                    explainHidden: explain?.hidden ?? false,
                    status: status?.textContent ?? ''
                  };
                }"""
            )
            page.context.set_offline(False)
            if (
                not offline_metrics["hasRoot"]
                or not offline_metrics["appHidden"]
                or not offline_metrics["explainHidden"]
                or "not available" not in offline_metrics["status"]
            ):
                raise CrossAuthorityError(
                    f"real built Site offline runtime did not fail closed: {offline_metrics}"
                )

            original_provenance = provenance_path.read_bytes()
            provenance_path.unlink()
            failed = browser.new_page(viewport={"width": 360, "height": 800})
            try:
                failed.goto(f"{base_url}/playground/", wait_until="networkidle")
                failed.wait_for_function(
                    "() => document.querySelector('#composition-playground')?.dataset.playgroundError === 'PROVENANCE_UNAVAILABLE'"
                )
                if not failed.locator("[data-playground-app]").is_hidden():
                    raise CrossAuthorityError("missing Site build provenance did not fail closed")
                assert_text_contains(failed, "[data-playground-status]", "provenance")
            finally:
                failed.close()
                provenance_path.write_bytes(original_provenance)

            if page_errors:
                raise CrossAuthorityError(f"browser page errors: {page_errors}")
            browser.close()
    finally:
        if not provenance_path.exists():
            raise CrossAuthorityError("browser failure left build provenance missing")
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-root", type=Path, required=True)
    parser.add_argument("--expected-site-revision", required=True)
    parser.add_argument("--expected-provider-revision", required=True)
    parser.add_argument("--expected-semantic-revision", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    for label, revision in (
        ("site", args.expected_site_revision),
        ("provider", args.expected_provider_revision),
        ("semantic", args.expected_semantic_revision),
    ):
        if not FULL_SHA.fullmatch(revision):
            raise SystemExit(f"expected {label} revision must be an exact lowercase full SHA")
    try:
        validate_built_inputs(
            args.site_root,
            expected_site_revision=args.expected_site_revision,
            expected_provider_revision=args.expected_provider_revision,
            expected_semantic_revision=args.expected_semantic_revision,
        )
        run_browser_check(
            args.site_root,
            expected_provider_revision=args.expected_provider_revision,
            expected_semantic_revision=args.expected_semantic_revision,
        )
    except (OSError, CrossAuthorityError) as exc:
        raise SystemExit(str(exc)) from exc
    print("Composition Playground cross-authority producer-to-consumer acceptance passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
