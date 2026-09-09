#!/usr/bin/env python3
"""Unified Site CI applicability classifier.

Classifies changed paths in a pull request or push event to determine which
validation stages are applicable according to the canonical Policy staged CI model:
- L0 Preflight & L1 Construction (fast unit tests & contract validation)
- L2 Conditional Integration (site assembly, browser, PWA, cross-authority)
- L3 Full Qualification (complete integration suite)

Conforms to the Policy CI applicability classifier contract:
- Base-authoritative (or immutable toolchain)
- Deterministic and changed-path based
- Fail-closed on ambiguity, unknown paths, or malformed input
- Prohibits self-exemption (workflow or classifier changes force full qualification)
- Supports explicit escalation (force-full via label or input)
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

# Paths whose changes govern CI execution or classification authority (fail-closed to full).
CI_CONTROL_EXACT_PATHS = frozenset(
    {
        "scripts/classify_site_ci.py",
        "scripts/classify_site_browser_acceptance.py",
        "scripts/classify_provider_coexistence.py",
        "scripts/classify_publication_freshness.py",
        "scripts/verify_site_full_qualification.py",
    }
)
CI_CONTROL_PREFIXES = (
    ".github/workflows/",
    "tests/test_site_ci_classifier",
    "tests/test_site_browser_acceptance_classifier",
    "tests/test_pages_workflow_boundary",
    "tests/test_verify_site_full_qualification",
)

# CI Observability surfaces that do not alter the generated Site or browser runtime.
OBSERVABILITY_EXACT_PATHS = frozenset(
    {
        ".github/workflows/ci-performance-report.yml",
        ".github/workflows/composition-unittest-timing-report.yml",
        "scripts/report_composition_unittest_timing.py",
    }
)
OBSERVABILITY_PREFIXES = ("tests/test_composition_unittest_timing_",)

# Documentation-only paths that alter only markdown content and navigation links.
DOC_EXACT_PATHS = frozenset(
    {
        "README.md",
        "MAINTENANCE.md",
        "CONTRIBUTING.md",
        "PUBLISHING.md",
        "GLOSSARY_INVENTORY.md",
        "FRESHNESS.md",
        "AGENTS.md",
        "PUBLICATION_FRESHNESS.md",
        "PUBLICATION_STAGING.md",
        "translations/README.md",
        "translations/manifest.json",
    }
)
DOC_PREFIXES = (
    "docs/",
    "translations/",
)

# PWA-sensitive surfaces.
PWA_EXACT_PATHS = frozenset(
    {
        "service-worker.js",
        "scripts/check_pwa_freshness.py",
        "scripts/check_pwa_capabilities.py",
        "scripts/check_pwa_commit_regressions.py",
        "scripts/check_pwa_locale_chrome.py",
        "scripts/check_pwa_slow_convergence.py",
        "scripts/pwa_evidence_targets.py",
        "contracts/pwa-manifest.json",
        "contracts/pwa-offline.json",
        "contracts/pwa-update.json",
    }
)
PWA_PREFIXES = ("tests/test_pwa_",)

# Browser, visual layout, CSS, JS, and search-sensitive surfaces.
BROWSER_EXACT_PATHS = frozenset(
    {
        "zensical.template.toml",
        "scripts/check_mobile_layout.py",
        "scripts/check_mobile_layout_core.py",
        "scripts/check_glossary_locale_chrome.py",
        "scripts/check_search_history.py",
        "scripts/check_search_history_review_regressions.py",
    }
)
BROWSER_PREFIXES = (
    "stylesheets/",
    "javascripts/",
    "tests/test_mobile_",
    "tests/test_search_",
    "tests/test_system_chrome_",
)

# Publication, schema, and cross-authority integration surfaces.
CROSS_AUTHORITY_EXACT_PATHS = frozenset(
    {
        "publication-sources.json",
        "publication-staging.json",
        "composition.json",
        "scripts/advance_publication_source.py",
        "scripts/resolve_publication_sources.py",
        "scripts/prepare_repository_tree_publication.py",
        "scripts/materialize_publication_assets.py",
        "scripts/materialize_publication_staging.py",
        "scripts/validate_provider_coexistence.py",
        "scripts/classify_publication_freshness.py",
        "scripts/write_publication_provenance.py",
        "scripts/publication_contract.py",
        "scripts/publication_contract_v4.py",
        "scripts/publication_link_rewriter.py",
    }
)
CROSS_AUTHORITY_PREFIXES = (
    ".template-composition/",
    "tests/test_provider_coexistence_",
    "tests/test_publication_",
    "tests/test_coexistence_",
    "tests/test_assembly_materialization_",
    "tests/test_composer_",
)

# Publication materialization, freshness, and staging surfaces.
PUBLICATION_EXACT_PATHS = frozenset(
    {
        "publication-sources.json",
        "publication-staging.json",
        "composition.json",
        "site-manifest.json",
        "PUBLICATION_FRESHNESS.md",
        "PUBLICATION_STAGING.md",
        "scripts/advance_publication_source.py",
        "scripts/resolve_publication_sources.py",
        "scripts/prepare_repository_tree_publication.py",
        "scripts/materialize_publication_assets.py",
        "scripts/materialize_publication_staging.py",
        "scripts/validate_provider_coexistence.py",
        "scripts/classify_publication_freshness.py",
        "scripts/write_publication_provenance.py",
        "scripts/publication_contract.py",
        "scripts/publication_contract_v4.py",
        "scripts/publication_link_rewriter.py",
        "scripts/assemble_publications_v3.py",
        "scripts/publish_provider_translations.py",
        "scripts/generate_repository_trees_composition.py",
    }
)
PUBLICATION_PREFIXES = (
    ".template-composition/",
    "tests/test_provider_coexistence_",
    "tests/test_publication_",
    "tests/test_coexistence_",
    "tests/test_assembly_materialization_",
    "tests/test_composer_",
    "tests/test_materialize_publication_",
)

# Reference consumer surfaces.
REFERENCE_CONSUMER_EXACT_PATHS = frozenset(
    {
        "assets/reference-consumer.json",
        "scripts/render_reference_consumer.py",
        "scripts/check_reference_website.py",
        "scripts/check_reference_pwa.py",
        "scripts/site_website_contract.py",
    }
)
REFERENCE_CONSUMER_PREFIXES = ("tests/test_reference_",)


class ClassificationError(ValueError):
    """Raised when changed paths cannot be safely classified."""


@dataclass(frozen=True)
class ClassificationDecision:
    core_required: bool
    build_required: bool
    browser_required: bool
    pwa_required: bool
    reference_consumer_required: bool
    cross_authority_required: bool
    publication_required: bool
    full_required: bool
    risk_class: str
    reason: str
    changed_count: int
    requiring_paths: tuple[str, ...]

    @property
    def required(self) -> bool:
        """Alias for browser_required for backward compatibility."""
        return self.browser_required


def normalize_path(value: str) -> str:
    path = value.strip().replace("\\", "/")
    if not path:
        raise ClassificationError("changed path must not be empty")
    parts = path.split("/")
    if path.startswith("/") or any(part in {"", ".", ".."} for part in parts):
        raise ClassificationError(
            f"changed path is not repository-relative: {value!r}"
        )
    return path


def is_ci_control_path(path: str) -> bool:
    if is_observability_path(path):
        return False
    return path in CI_CONTROL_EXACT_PATHS or any(
        path.startswith(prefix) for prefix in CI_CONTROL_PREFIXES
    )


def is_observability_path(path: str) -> bool:
    return path in OBSERVABILITY_EXACT_PATHS or any(
        path.startswith(prefix) for prefix in OBSERVABILITY_PREFIXES
    )


def is_doc_path(path: str) -> bool:
    return path in DOC_EXACT_PATHS or (
        any(path.startswith(prefix) for prefix in DOC_PREFIXES)
        and path.endswith(".md")
    )


def is_pwa_path(path: str) -> bool:
    return path in PWA_EXACT_PATHS or any(
        path.startswith(prefix) for prefix in PWA_PREFIXES
    )


def is_browser_path(path: str) -> bool:
    return path in BROWSER_EXACT_PATHS or any(
        path.startswith(prefix) for prefix in BROWSER_PREFIXES
    ) or path.endswith(".test.mjs")


def is_cross_authority_path(path: str) -> bool:
    return path in CROSS_AUTHORITY_EXACT_PATHS or any(
        path.startswith(prefix) for prefix in CROSS_AUTHORITY_PREFIXES
    )


def is_publication_path(path: str) -> bool:
    return path in PUBLICATION_EXACT_PATHS or any(
        path.startswith(prefix) for prefix in PUBLICATION_PREFIXES
    )


def is_reference_consumer_path(path: str) -> bool:
    return path in REFERENCE_CONSUMER_EXACT_PATHS or any(
        path.startswith(prefix) for prefix in REFERENCE_CONSUMER_PREFIXES
    )


def is_known_runtime_path(path: str) -> bool:
    return (
        path.startswith("scripts/")
        or path.startswith("tests/")
        or path.startswith("contracts/")
        or path.startswith("components/")
        or path == "requirements.txt"
        or path.startswith("requirements-")
        or path == "site-manifest.json"
    )


def classify_paths(
    paths: Iterable[str],
    *,
    force_full: bool = False,
) -> ClassificationDecision:
    normalized = tuple(normalize_path(p) for p in paths)
    if not normalized:
        raise ClassificationError("at least one changed path is required")

    changed_count = len(normalized)

    # Escalation: force full qualification
    if force_full:
        return ClassificationDecision(
            core_required=True,
            build_required=True,
            browser_required=True,
            pwa_required=True,
            reference_consumer_required=True,
            cross_authority_required=True,
            publication_required=True,
            full_required=True,
            risk_class="ci-authority-sensitive",
            reason="explicit full qualification requested",
            changed_count=changed_count,
            requiring_paths=normalized,
        )

    # 1. CI Control / Workflow changes -> full qualification (no self-exemption)
    control_paths = tuple(sorted(p for p in normalized if is_ci_control_path(p)))
    if control_paths:
        return ClassificationDecision(
            core_required=True,
            build_required=True,
            browser_required=True,
            pwa_required=True,
            reference_consumer_required=True,
            cross_authority_required=True,
            publication_required=True,
            full_required=True,
            risk_class="ci-authority-sensitive",
            reason="CI workflow or classification controls changed",
            changed_count=changed_count,
            requiring_paths=control_paths,
        )

    # 2. Check for unknown paths -> fail closed
    def is_known(p: str) -> bool:
        return (
            is_observability_path(p)
            or is_doc_path(p)
            or is_pwa_path(p)
            or is_browser_path(p)
            or is_cross_authority_path(p)
            or is_publication_path(p)
            or is_reference_consumer_path(p)
            or is_known_runtime_path(p)
        )

    unknown_paths = tuple(sorted(p for p in normalized if not is_known(p)))
    if unknown_paths:
        return ClassificationDecision(
            core_required=True,
            build_required=True,
            browser_required=True,
            pwa_required=True,
            reference_consumer_required=True,
            cross_authority_required=True,
            publication_required=True,
            full_required=True,
            risk_class="unknown",
            reason=f"unknown changed paths: {','.join(unknown_paths)}",
            changed_count=changed_count,
            requiring_paths=unknown_paths,
        )

    # 3. Observability-only paths
    if all(is_observability_path(p) for p in normalized):
        return ClassificationDecision(
            core_required=True,
            build_required=False,
            browser_required=False,
            pwa_required=False,
            reference_consumer_required=False,
            cross_authority_required=False,
            publication_required=False,
            full_required=False,
            risk_class="observability-only",
            reason="all changed paths are CI-observability-only",
            changed_count=changed_count,
            requiring_paths=(),
        )

    # 4. Documentation-only paths
    if all(is_doc_path(p) for p in normalized):
        return ClassificationDecision(
            core_required=True,
            build_required=False,
            browser_required=False,
            pwa_required=False,
            reference_consumer_required=False,
            cross_authority_required=False,
            publication_required=False,
            full_required=False,
            risk_class="documentation-only",
            reason="all changed paths are documentation-only",
            changed_count=changed_count,
            requiring_paths=(),
        )

    # 5. Mixed / Specific capability matching
    has_pwa = any(is_pwa_path(p) for p in normalized)
    has_browser = has_pwa or any(is_browser_path(p) for p in normalized)
    has_cross_auth = any(is_cross_authority_path(p) for p in normalized)
    has_publication = has_cross_auth or any(is_publication_path(p) for p in normalized)
    has_ref_consumer = (
        has_pwa
        or has_browser
        or any(is_reference_consumer_path(p) for p in normalized)
        or any(
            p in {
                "zensical.template.toml",
                "site-manifest.json",
                "publication-sources.json",
                "composition.json",
                "scripts/site_website_contract.py",
            }
            for p in normalized
        )
        or any(p.startswith(".template-composition/") for p in normalized)
    )
    has_runtime = (
        has_browser
        or has_cross_auth
        or has_publication
        or has_ref_consumer
        or any(is_known_runtime_path(p) for p in normalized)
    )

    requiring = tuple(sorted(p for p in normalized if not is_observability_path(p) and not is_doc_path(p)))

    risk_class = "runtime-sensitive"
    if has_cross_auth:
        risk_class = "cross-authority-sensitive"
    elif has_publication:
        risk_class = "publication-sensitive"
    elif has_pwa:
        risk_class = "pwa-sensitive"
    elif has_browser:
        risk_class = "browser-sensitive"

    return ClassificationDecision(
        core_required=True,
        build_required=has_runtime,
        browser_required=has_browser,
        pwa_required=has_pwa,
        reference_consumer_required=has_ref_consumer,
        cross_authority_required=has_cross_auth,
        publication_required=has_publication,
        full_required=False,
        risk_class=risk_class,
        reason=f"capabilities required: {risk_class}",
        changed_count=changed_count,
        requiring_paths=requiring,
    )


def write_outputs(output: TextIO, decision: ClassificationDecision) -> None:
    def b2s(val: bool) -> str:
        return "true" if val else "false"

    output.write(f"core_required={b2s(decision.core_required)}\n")
    output.write(f"build_required={b2s(decision.build_required)}\n")
    output.write(f"browser_required={b2s(decision.browser_required)}\n")
    output.write(f"pwa_required={b2s(decision.pwa_required)}\n")
    output.write(f"reference_consumer_required={b2s(decision.reference_consumer_required)}\n")
    output.write(f"cross_authority_required={b2s(decision.cross_authority_required)}\n")
    output.write(f"publication_required={b2s(decision.publication_required)}\n")
    output.write(f"full_required={b2s(decision.full_required)}\n")
    output.write(f"required={b2s(decision.required)}\n")
    output.write(f"risk_class={decision.risk_class}\n")
    output.write(f"reason={decision.reason}\n")
    output.write(f"changed_count={decision.changed_count}\n")
    output.write(f"requiring_count={len(decision.requiring_paths)}\n")
    if decision.requiring_paths:
        output.write("requiring_paths=" + ",".join(decision.requiring_paths) + "\n")
    else:
        output.write("requiring_paths=none\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--changed-paths", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--force-full",
        type=lambda v: str(v).lower() in {"true", "1", "yes"},
        default=False,
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        paths = args.changed_paths.read_text(encoding="utf-8").splitlines()
        decision = classify_paths(paths, force_full=args.force_full)
        with args.output.open("a", encoding="utf-8") as output:
            write_outputs(output, decision)
    except (OSError, UnicodeError, ClassificationError) as exc:
        print(f"Site CI classification failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
