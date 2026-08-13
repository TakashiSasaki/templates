"""Shared deterministic text-statistics operation for the browser fixture."""

from __future__ import annotations

import re

CONTRACT_VERSION = "1"
ASCII_NON_WHITESPACE = re.compile(r"[^ \t\r\n\f\v]+")


def analyze(text: str) -> dict[str, int]:
    raw = text.encode("utf-8")
    lines = 0 if not text else text.count("\n") + (0 if text.endswith("\n") else 1)
    return {
        "bytes": len(raw),
        "lines": lines,
        "words": len(ASCII_NON_WHITESPACE.findall(text)),
    }
