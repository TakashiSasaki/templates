from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Diagnostic:
    level: str
    code: str
    message: str
    path: str | None = None


def print_diagnostics(diagnostics: Iterable[Diagnostic], output_format: str) -> None:
    values = list(diagnostics)
    if output_format == "json":
        print(json.dumps([asdict(item) for item in values], ensure_ascii=False, indent=2))
        return
    if not values:
        print("OK")
        return
    for item in values:
        location = f" [{item.path}]" if item.path else ""
        print(f"{item.level.upper()} {item.code}{location}: {item.message}")
