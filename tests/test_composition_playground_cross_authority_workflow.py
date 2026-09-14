#!/usr/bin/env python3
"""Static contract checks for Composition Playground cross-authority CI triggers."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "site-composition-playground-cross-authority.yml"
EXPECTED_BASES = {
    "codex/site-composition-playground-v1-shell",
    "site",
    "feat/site-*",
    "site-composition-audience-publication-staging",
    "site-*",
    "perf/site-*",
}


def pull_request_bases(text: str) -> set[str]:
    pull_request = text.index("  pull_request:")
    branches = text.index("    branches:", pull_request)
    types = text.index("    types:", branches)
    values: set[str] = set()
    for raw_line in text[branches:types].splitlines()[1:]:
        line = raw_line.strip()
        if line.startswith("- "):
            values.add(line[2:].strip().strip("\"'"))
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
    if (
        "composition_ref: ${{ needs.resolve_candidate.outputs.composition_revision }}" not in text
        and "composition_ref: ${{ needs.classify.outputs.composition_revision }}" not in text
    ):
        raise AssertionError("cross-authority candidate must resolve the declared exact provider pin")
    if "python scripts/resolve_publication_sources.py" not in text:
        raise AssertionError("cross-authority candidate must use the canonical publication resolver")
    if "python scripts/run_site_preflight.py cross" not in text or "--check candidate-projection" not in text:
        raise AssertionError("cross-authority classification must use canonical candidate validation")
    if (
        "EXPECTED_PROVIDER_REVISION: ${{ needs.resolve_candidate.outputs.composition_revision }}" not in text
        and "EXPECTED_PROVIDER_REVISION: ${{ needs.classify.outputs.composition_revision }}" not in text
    ):
        raise AssertionError("browser acceptance must verify the same resolved provider revision")
    if "EXPECTED_SEMANTIC_REVISION: ${{ needs.resolve_candidate.outputs.semantic_revision }}" not in text:
        raise AssertionError("browser acceptance must verify the resolved semantic revision")
    if "composition-source/generated/composition-playground-publication.json" not in text:
        raise AssertionError("semantic identity must come from the provider's tracked publication manifest")
    if "composition-source/generated/publication-descriptor.json" in text:
        raise AssertionError("candidate classification must not depend on an untracked generated descriptor")
    if "6b7d764c963f957c6bee43c0c1d42eb03970ec8f" in text:
        raise AssertionError("cross-authority workflow retains an obsolete provider literal")
    print("Composition Playground cross-authority trigger contract passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
