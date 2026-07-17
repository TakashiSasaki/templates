from __future__ import annotations

from dataclasses import dataclass, asdict
import json
from typing import Iterable


@dataclass(frozen=True)
class Diagnostic:
    level: str
    code: str
    message: str
    path: str | None = None

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def print_diagnostics(items: Iterable[Diagnostic], output_format: str = "text") -> None:
    values = list(items)
    if output_format == "json":
        print(json.dumps([item.as_dict() for item in values], indent=2, ensure_ascii=False))
        return
    if not values:
        print("No diagnostics.")
        return
    for item in values:
        location = f" [{item.path}]" if item.path else ""
        print(f"{item.level.upper()} {item.code}{location}: {item.message}")
