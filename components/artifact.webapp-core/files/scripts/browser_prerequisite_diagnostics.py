#!/usr/bin/env python3
"""Classify generic browser-proof prerequisites without weakening fail-closed semantics."""

from __future__ import annotations

import argparse
import json
from typing import Any

SCHEMA_VERSION = 1
BROWSER_STATES = ("available", "unavailable", "not-checked")
COMPATIBILITY_STATES = ("compatible", "incompatible", "not-checked")
LOCALHOST_STATES = ("allowed", "restricted", "not-checked")
BLOCKING_CODES = (
    "browser-binary-unavailable",
    "webdriver-unavailable",
    "incompatible-browser-driver",
    "localhost-browser-sandbox-restricted",
)

BLOCKING_BY_PREREQUISITE = {
    "browser_binary": "browser-binary-unavailable",
    "webdriver": "webdriver-unavailable",
    "compatibility": "incompatible-browser-driver",
    "localhost": "localhost-browser-sandbox-restricted",
}



def diagnose(
    *,
    browser_binary: str = "not-checked",
    webdriver: str = "not-checked",
    compatibility: str = "not-checked",
    localhost: str = "not-checked",
) -> dict[str, Any]:
    """Project recorded prerequisite observations into a deterministic report.

    This classifies observations supplied by a probe or evaluator. It does not
    probe a browser, WebDriver, or sandbox itself. An unavailable required
    prerequisite always makes release impact not-ready.
    """
    if browser_binary not in BROWSER_STATES:
        raise ValueError(f"unsupported browser binary state: {browser_binary!r}")
    if webdriver not in BROWSER_STATES:
        raise ValueError(f"unsupported WebDriver state: {webdriver!r}")
    if compatibility not in COMPATIBILITY_STATES:
        raise ValueError(f"unsupported compatibility state: {compatibility!r}")
    if localhost not in LOCALHOST_STATES:
        raise ValueError(f"unsupported localhost state: {localhost!r}")

    values = {
        "browser_binary": browser_binary,
        "webdriver": webdriver,
        "compatibility": compatibility,
        "localhost": localhost,
    }
    blocked = [
        BLOCKING_BY_PREREQUISITE[name]
        for name, value in values.items()
        if value in {"unavailable", "incompatible", "restricted"}
    ]

    observations = (browser_binary, webdriver, compatibility, localhost)
    if blocked:
        status = "unavailable"
        release_impact = "not-ready"
    elif all(state in {"available", "compatible", "allowed"} for state in observations):
        status = "available"
        release_impact = "none"
    else:
        status = "not-checked"
        release_impact = "not-evaluated"

    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "browser_binary": browser_binary,
        "webdriver": webdriver,
        "compatibility": compatibility,
        "localhost": localhost,
        "missing_or_blocked_prerequisites": blocked,
        "release_impact": release_impact,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser-binary", choices=BROWSER_STATES, default="not-checked")
    parser.add_argument("--webdriver", choices=BROWSER_STATES, default="not-checked")
    parser.add_argument(
        "--compatibility", choices=COMPATIBILITY_STATES, default="not-checked"
    )
    parser.add_argument("--localhost", choices=LOCALHOST_STATES, default="not-checked")
    parser.add_argument("--format", choices=("json",), default="json")
    args = parser.parse_args(argv)
    print(
        json.dumps(
            diagnose(
                browser_binary=args.browser_binary,
                webdriver=args.webdriver,
                compatibility=args.compatibility,
                localhost=args.localhost,
            ),
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
