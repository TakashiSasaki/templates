"""Source-maintainer package bridge to canonical downstream validators."""

from __future__ import annotations

from pathlib import Path

_TEMPLATE_SCRIPTS = Path(__file__).resolve().parents[1] / "template" / "scripts"
if _TEMPLATE_SCRIPTS.is_dir():
    __path__.append(str(_TEMPLATE_SCRIPTS))
