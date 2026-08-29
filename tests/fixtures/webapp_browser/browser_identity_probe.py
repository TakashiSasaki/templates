from __future__ import annotations

from typing import Any

from browser_probe import BrowserProbeError, _open_webdriver_session


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise BrowserProbeError(message)


def run_browser_identity_probe(url: str, contract: dict[str, Any]) -> None:
    favicon = contract.get("favicon")
    if not isinstance(favicon, dict):
        raise BrowserProbeError("browser identity contract favicon must be an object")
    expected_href = favicon.get("href")
    expected_media_type = favicon.get("mediaType")
    expected_sizes = favicon.get("sizes")
    _require(favicon.get("relation") == "icon", "favicon relation must be icon")
    _require(isinstance(expected_href, str) and expected_href, "favicon href is invalid")
    _require(
        isinstance(expected_media_type, str) and expected_media_type,
        "favicon mediaType is invalid",
    )
    _require(
        isinstance(expected_sizes, list)
        and all(isinstance(item, str) and item for item in expected_sizes),
        "favicon sizes are invalid",
    )

    with _open_webdriver_session() as browser:
        browser.navigate(url)
        observed = browser.execute(
            """
            const links = Array.from(document.querySelectorAll('link[rel]')).map((link) => {
              const relTokens = link.getAttribute('rel').trim().toLowerCase().split(/\s+/);
              return {
                relTokens,
                rawHref: link.getAttribute('href'),
                resolvedHref: link.href,
                mediaType: link.getAttribute('type') || '',
                sizes: link.sizes ? Array.from(link.sizes) : [],
              };
            });
            return {
              shortcutCount: links.filter((item) => item.relTokens.includes('shortcut')).length,
              iconLinks: links.filter((item) => item.relTokens.includes('icon')),
            };
            """
        )
        _require(isinstance(observed, dict), "browser identity probe returned invalid data")
        _require(
            observed.get("shortcutCount") == 0,
            "browser identity uses obsolete shortcut icon relation",
        )
        icon_links = observed.get("iconLinks")
        _require(isinstance(icon_links, list), "browser icon link inventory is invalid")
        primary = next(
            (
                item
                for item in icon_links
                if isinstance(item, dict) and item.get("rawHref") == expected_href
            ),
            None,
        )
        _require(primary is not None, f"browser favicon link {expected_href!r} is missing")
        assert isinstance(primary, dict)
        _require(
            primary.get("relTokens") == ["icon"],
            "favicon must use the standard rel=icon relationship",
        )
        _require(
            primary.get("mediaType") == expected_media_type,
            "favicon link media type does not match the browser identity contract",
        )
        _require(
            sorted(primary.get("sizes", [])) == sorted(expected_sizes),
            "favicon link sizes do not match the browser identity contract",
        )
        resolved_href = primary.get("resolvedHref")
        _require(
            isinstance(resolved_href, str) and resolved_href,
            "browser did not resolve the favicon asset URL",
        )

        browser.navigate(resolved_href)
        asset = browser.execute(
            """
            return {
              contentType: document.contentType,
              rootName: document.documentElement ? document.documentElement.localName : null,
            };
            """
        )
        _require(isinstance(asset, dict), "favicon asset probe returned invalid data")
        _require(
            asset.get("contentType") == expected_media_type,
            "browser did not retrieve the favicon with the declared media type",
        )
        if expected_media_type == "image/svg+xml":
            _require(
                asset.get("rootName") == "svg",
                "browser did not parse the declared SVG favicon as an SVG document",
            )

    print("Browser identity proof: standard favicon linkage and primary asset retrieval passed")
