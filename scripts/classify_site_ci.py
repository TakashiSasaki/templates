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
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TextIO

# Paths whose changes govern CI execution or classification authority (fail-closed to full).
CI_CONTROL_EXACT_PATHS = frozenset(
    {
        "scripts/site_build_artifact.py",
        "scripts/consume_site_build_artifact.py",
        "scripts/run_site_preflight.py",
        "scripts/site_check_registry.py",
        "scripts/validate_site_declarations.py",
        "scripts/validate_website_contracts.py",
        "scripts/classify_site_ci.py",
        "scripts/collect_site_changed_paths.py",
        "scripts/classify_site_browser_acceptance.py",
        "scripts/classify_provider_coexistence.py",
        "scripts/classify_publication_freshness.py",
        "scripts/verify_site_full_qualification.py",
        "scripts/run_core_tests.py",
        "scripts/qualify_integration.py",
        "integration/qualification.py",
        "scripts/publication_bundle_artifact.py",
    }
)
CI_CONTROL_PREFIXES = (
    ".github/workflows/",
    "ci_artifacts/",
    "tests/test_site_build_artifact",
    "tests/test_site_ci_classifier",
    "tests/test_pages_workflow_boundary",
    "tests/test_verify_site_full_qualification",
    "tests/test_run_core_tests",
)

# The reusable workflow uses the same immutable base snapshot to decide whether
# a pull request belongs to the Site authority. Branch names are deliberately
# not part of this predicate so arbitrary stacked Site branches remain covered.
SITE_AUTHORITY_MARKERS = frozenset(
    {".github/workflows/build-pages.yml", "scripts/classify_site_ci.py"}
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
        "translations/README.md",
    }
)
DOC_PREFIXES = (
    "docs/",
    "translations/",
)

# PWA-sensitive surfaces.
PWA_EXACT_PATHS = frozenset(
    {
        "scripts/check_reference_pwa.py",
        "assets/service-worker.js",
        "assets/javascripts/pwa.js",
        "assets/app.webmanifest",
        "assets/icon-180.png",
        "assets/icon-192.png",
        "assets/icon-512.png",
        "assets/icon.svg",
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

# Core-only surfaces that only affect fast L1 unit/contract test execution.
CORE_ONLY_EXACT_PATHS: frozenset[str] = frozenset()
CORE_ONLY_PREFIXES = (
    "tests/test_audience_",
    "tests/test_check_audience_",
)

# Browser, visual layout, CSS, JS, and search-sensitive surfaces.
BROWSER_EXACT_PATHS = frozenset(
    {
        "assets/audience-runtime.json",
        "docs/composition-playground.md",
        "scripts/audience_context.py",
        "scripts/audience_presentation.py",
        "scripts/check_reference_website.py",
        "zensical.template.toml",
        "requirements-build.lock",
        "requirements-visual.txt",
        "assets/site-chrome-locales.json",
        "scripts/check_glossary_locale_chrome.py",
        "scripts/check_search_history.py",
        "scripts/check_search_history_review_regressions.py",
        "contracts/browser-identity.json",
        "contracts/viewports.json",
        "contracts/routes.json",
        "contracts/site-structure.json",
        "contracts/document-metadata.json",
        "contracts/site-discovery.json",
        "contracts/manifest.json",
        # These render user-visible source/provenance destinations. A change can
        # alter generated HTML even when no browser JavaScript changes.
        "site_renderer/github.py",
        "site_renderer/guided.py",
        "site_renderer/guided_locales.py",
        "site_renderer/local_content.py",
    }
)
BROWSER_PREFIXES = (
    "assets/javascripts/",
    "assets/stylesheets/",
    "assets/images/",
    "stylesheets/",
    "javascripts/",
    "scripts/check_audience_",
    "scripts/check_composition_playground_",
    "tests/test_mobile_",
    "tests/test_search_",
    "tests/test_system_chrome_",
)

# Known site build and generator surfaces.
BUILD_EXACT_PATHS = frozenset(
    {
        "integration-source.json",
        "requirements.txt",
        "site-manifest.json",
        "reader-navigation-locales.json",
        "reference-consumer.json",
        "assets/agent.json",
        "assets/schemas/agent-bootstrap.schema.json",
        "scripts/assemble_publications.py",
        "scripts/check_public_url_boundary.py",
        "scripts/finalize_glossary_annotations.py",
        "scripts/finalize_guided_locales.py",
        "scripts/finalize_site_metadata.py",
        "scripts/finalize_translation_reader.py",
        "scripts/generate_agent_bootstrap.py",
        "scripts/generate_freshness_metadata.py",
        "scripts/generate_glossary.py",
        "scripts/generate_glossary_viewer.py",
        "scripts/generate_index_navigation.py",
        "scripts/generate_index_navigation_base.py",
        "scripts/generate_index_navigation_locale_viewer.py",
        "scripts/generate_index_navigation_locales.py",
        "scripts/generate_index_navigation_viewer.py",
        "scripts/glossary.py",
        "scripts/glossary_annotation.py",
        "scripts/prepare_site_metadata.py",
        "scripts/publish_translations.py",
        "scripts/reader_navigation_locales.py",
        "scripts/render_website_metadata.py",
        "scripts/run_composition_navigation.py",
        "scripts/site_build_profile.py",
        "scripts/site_chrome_locales.py",
        "scripts/translation_coverage.py",
        "scripts/translation_fragment_reconciliation.py",
        "scripts/translation_link_identity.py",
        "scripts/translation_link_selection.py",
        "scripts/translation_manifest.py",
        "scripts/translation_reader_metadata.py",
        "scripts/validate_site_links.py",
        "scripts/validate_translation_pairs.py",
        "scripts/validate_website_contracts.py",
        "scripts/validate_website_evidence.py",
        "scripts/website_evidence_targets.py",
        "scripts/acquire_integration_bundle.py",
        "scripts/check_bundle_reader.py",
        "scripts/check_site_artifact.py",
        "scripts/render_publication_bundle.py",
    }
)

# Site consumes these versioned semantic Bundle models and their contract
# definition. They require an exact Bundle-to-Site build, but do not by
# themselves imply browser/PWA acceptance.
BUNDLE_PUBLICATION_PREFIXES = (
    "publication_bundle/",
    "contracts/publication-bundle/",
)

# Publication, schema, and cross-authority integration surfaces.
CROSS_AUTHORITY_EXACT_PATHS = frozenset(
    {
        "publication-sources.json",
        "publication-staging.json",
        "composition.json",
        "scripts/advance_publication_source.py",
        "scripts/resolve_publication_sources.py",
        "scripts/materialize_publication_assets.py",
        "scripts/materialize_publication_staging.py",
        "scripts/validate_provider_coexistence.py",
        "scripts/classify_publication_freshness.py",
        "scripts/write_publication_provenance.py",
        "scripts/publication_contract.py",
        "scripts/publication_contract_v4.py",
        "scripts/publication_link_rewriter.py",
        "scripts/check_composition_playground_cross_authority.py",
        "scripts/check_composition_playground_webmcp_browser.py",
        "scripts/check_composition_playground_latest_five_browser.py",
        "scripts/check_composition_playground_final_browser.py",
        "scripts/check_composition_playground_final_grid_browser.py",
    }
)
CROSS_AUTHORITY_PREFIXES = (
    ".template-composition/",
    "tests/test_provider_coexistence_",
    "tests/test_publication_",
    "tests/test_coexistence_",
    "tests/test_assembly_materialization_",
    "tests/test_composer_",
    "tests/test_composition_playground_cross_authority",
)

# Publication materialization, freshness, and staging surfaces.
PUBLICATION_EXACT_PATHS = frozenset(
    {
        "integration-source.json",
        "publication-sources.json",
        "publication-staging.json",
        "composition.json",
        "site-manifest.json",
        "PUBLICATION_FRESHNESS.md",
        "PUBLICATION_STAGING.md",
        "translations/manifest.json",
        "scripts/advance_publication_source.py",
        "scripts/resolve_publication_sources.py",
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
    *BUNDLE_PUBLICATION_PREFIXES,
)

# Reference consumer surfaces.
REFERENCE_CONSUMER_EXACT_PATHS = frozenset(
    {
        "assets/reference-consumer.json",
        "scripts/render_reference_consumer.py",
        "scripts/check_reference_website.py",
        "scripts/check_reference_pwa.py",
        "scripts/site_website_contract.py",
        "contracts/browser-identity.json",
        "contracts/viewports.json",
        "contracts/routes.json",
        "contracts/site-structure.json",
        "contracts/document-metadata.json",
        "contracts/site-discovery.json",
        "contracts/manifest.json",
        "contracts/implementation-evidence.json",
        "contracts/lifecycle-checkpoints.json",
    }
)
REFERENCE_CONSUMER_PREFIXES = ("tests/test_reference_",)


class ClassificationError(ValueError):
    """Raised when changed paths cannot be safely classified."""


def is_site_authority_snapshot(paths: Iterable[str]) -> bool:
    """Return whether a repository tree contains the Site CI authority markers."""
    return SITE_AUTHORITY_MARKERS <= set(paths)


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
    freshness_candidate_required: bool = True
    coexistence_required: bool = False
    playground_required: bool = False
    browser_priority: str = "none"
    integration_required: bool = False

    @property
    def freshness_required(self) -> bool:
        """Alias for freshness_candidate_required."""
        return self.freshness_candidate_required


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
    if is_publication_path(path) or is_cross_authority_path(path) or is_browser_path(path):
        return False
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
    )


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


def is_core_only_path(path: str) -> bool:
    return path.endswith(".test.mjs") or path in CORE_ONLY_EXACT_PATHS or any(
        path.startswith(prefix) for prefix in CORE_ONLY_PREFIXES
    )


def is_known_runtime_path(path: str) -> bool:
    return (
        path in BUILD_EXACT_PATHS
        or path.startswith("site_renderer/")
        or path.startswith(BUNDLE_PUBLICATION_PREFIXES)
        or (path.startswith("schemas/") and path.endswith(".json"))
        or (path.startswith("tests/test_") and path.endswith(".py"))
        or path.startswith("tests/fixtures/")
    )


def is_coexistence_path(path: str) -> bool:
    return (
        path == ".github/workflows/provider-coexistence.yml"
        or path == "publication-sources.json"
        or path.endswith(".py")
    )


def classify_paths(paths: Iterable[str], *, force_full: bool = False,
                   force_browser: bool = False) -> ClassificationDecision:
    paths = tuple(paths)
    decision = _classify_paths(paths, force_full=force_full)
    playground = decision.browser_required or decision.cross_authority_required or any(
        normalize_path(p).startswith(("tests/composition-playground", "tests/fixtures/composition-playground"))
        for p in paths
    )
    priority = "none"
    for capability, markers in (
        ("audience", ("audience", "site-manifest.json")),
        ("search", ("search",)),
        ("pwa", ("pwa", "service-worker")),
        ("layout", ("mobile", "stylesheets/")),
    ):
        if any(any(marker in path for marker in markers) for path in paths):
            priority = capability
            break
    decision = replace(decision, playground_required=playground, browser_priority=priority,
                       integration_required=False)  # Site never qualifies providers.
    if force_browser and not decision.full_required:
        decision = replace(
            decision, build_required=True, browser_required=True, pwa_required=True,
            reference_consumer_required=True, playground_required=True,
            reason="explicit browser qualification requested",
        )
    return decision


def _classify_paths(
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
            coexistence_required=True,
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
            coexistence_required=True,
            risk_class="ci-authority-sensitive",
            reason="CI workflow or classification controls changed",
            changed_count=changed_count,
            requiring_paths=control_paths,
        )

    # 2. Check for unknown paths -> fail closed
    def is_known(p: str) -> bool:
        return (
            is_ci_control_path(p)
            or is_observability_path(p)
            or is_doc_path(p)
            or is_core_only_path(p)
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
            coexistence_required=True,
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
            coexistence_required=False,
            risk_class="observability-only",
            reason="all changed paths are CI-observability-only",
            changed_count=changed_count,
            requiring_paths=(),
            freshness_candidate_required=False,
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
            coexistence_required=False,
            risk_class="documentation-only",
            reason="all changed paths are documentation-only",
            changed_count=changed_count,
            requiring_paths=(),
            freshness_candidate_required=False,
        )

    # 4b. Core-only validation paths
    if all(is_core_only_path(p) or is_observability_path(p) or is_doc_path(p) for p in normalized) and any(is_core_only_path(p) for p in normalized):
        return ClassificationDecision(
            core_required=True,
            build_required=False,
            browser_required=False,
            pwa_required=False,
            reference_consumer_required=False,
            cross_authority_required=False,
            publication_required=False,
            full_required=False,
            coexistence_required=False,
            risk_class="core-only",
            reason="all changed paths are core-validation-only",
            changed_count=changed_count,
            requiring_paths=tuple(sorted(p for p in normalized if is_core_only_path(p))),
            freshness_candidate_required=False,
        )

    # 5. Mixed / Specific capability matching
    has_pwa = any(is_pwa_path(p) for p in normalized)
    has_browser = has_pwa or any(is_browser_path(p) for p in normalized)
    has_cross_auth = any(is_cross_authority_path(p) for p in normalized)
    has_publication = has_cross_auth or any(is_publication_path(p) for p in normalized)
    has_coex = has_cross_auth or any(is_coexistence_path(p) for p in normalized)
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

    requiring = tuple(
        sorted(
            p
            for p in normalized
            if not is_observability_path(p)
            and not is_doc_path(p)
            and not is_core_only_path(p)
        )
    )

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
        coexistence_required=has_coex,
        risk_class=risk_class,
        reason=f"capabilities required: {risk_class}",
        changed_count=changed_count,
        requiring_paths=requiring,
    )


def write_outputs(output: TextIO, decision: ClassificationDecision) -> None:
    def b2s(val: bool) -> str:
        return "true" if val else "false"

    output.write(f"browser_priority={decision.browser_priority}\n")
    output.write(f"playground_required={b2s(decision.playground_required)}\n")
    output.write(f"core_required={b2s(decision.core_required)}\n")
    output.write(f"integration_required={b2s(decision.integration_required)}\n")
    output.write(f"build_required={b2s(decision.build_required)}\n")
    output.write(f"browser_required={b2s(decision.browser_required)}\n")
    output.write(f"pwa_required={b2s(decision.pwa_required)}\n")
    output.write(f"reference_consumer_required={b2s(decision.reference_consumer_required)}\n")
    output.write(f"cross_authority_required={b2s(decision.cross_authority_required)}\n")
    output.write(f"publication_required={b2s(decision.publication_required)}\n")
    output.write(f"full_required={b2s(decision.full_required)}\n")
    output.write(f"coexistence_required={b2s(decision.coexistence_required)}\n")
    output.write(f"freshness_candidate_required={b2s(decision.freshness_candidate_required)}\n")
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
    parser.add_argument("--force-browser", type=lambda v: str(v).lower() in {"true", "1", "yes"}, default=False)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        paths = args.changed_paths.read_text(encoding="utf-8").splitlines()
        decision = classify_paths(paths, force_full=args.force_full, force_browser=args.force_browser)
        with args.output.open("a", encoding="utf-8") as output:
            write_outputs(output, decision)
    except (OSError, UnicodeError, ClassificationError) as exc:
        print(f"Site CI classification failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
