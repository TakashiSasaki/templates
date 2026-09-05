#!/usr/bin/env python3
"""Static contract checks for Composition Playground cross-authority CI triggers."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "site-composition-playground-cross-authority.yml"
EXPECTED_BASES = {
    "codex/site-composition-playground-v1-shell",
    "site",
}


def pull_request_bases(text: str) -> set[str]:
    pull_request = text.index("  pull_request:")
    branches = text.index("    branches:", pull_request)
    types = text.index("    types:", branches)
    values: set[str] = set()
    for raw_line in text[branches:types].splitlines()[1:]:
        line = raw_line.strip()
        if line.startswith("- "):
            values.add(line[2:].strip())
    return values


def main() -> int:
    text = WORKFLOW.read_text(encoding="utf-8")
    bases = pull_request_bases(text)
    if bases != EXPECTED_BASES:
        raise AssertionError(
            f"cross-authority PR bases must be exactly {sorted(EXPECTED_BASES)}, got {sorted(bases)}"
        )
    if "site_ref: ${{ github.event.pull_request.head.sha }}" not in text:
        raise AssertionError("cross-authority build no longer binds to the exact PR head")
    if "ref: ${{ github.event.pull_request.head.sha }}" not in text:
        raise AssertionError("cross-authority consumer checkout no longer binds to the exact PR head")
    if "composition_ref: 95a91a9f0a2258a7611c77f32a571164c065ece3" not in text:
        raise AssertionError("cross-authority candidate provider binding changed unexpectedly")
    print("Composition Playground cross-authority trigger contract passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
