"""Authoritative inventory for Site-local validation.

The registry describes the cost and dependency boundary of each check.  The
local preflight runner is the executable consumer of this inventory; workflows
invoke that runner instead of maintaining their own test-file lists.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CheckSpec:
    """A named validation boundary and the environment it needs."""

    name: str
    execution_class: str
    description: str


EXECUTION_CLASSES = (
    "source/core",
    "node/source",
    "managed-validation",
    "rendered-artifact",
    "real-browser/PWA",
    "GitHub/API",
)

CHECKS = (
    CheckSpec("l0", "source/core", "changed-file hygiene and syntax checks"),
    CheckSpec("core", "source/core", "the classified Python core suite"),
    CheckSpec("node", "node/source", "all Composition Playground Node tests"),
    CheckSpec("site-contracts", "source/core", "Site-owned declaration and contract checks"),
    CheckSpec(
        "dependency-boundary",
        "source/core",
        "Python entrypoint imports versus environment requirements",
    ),
    CheckSpec(
        "composition-consumer",
        "managed-validation",
        "the managed Composition consumer validator (may provision a runtime)",
    ),
    CheckSpec("assembly", "rendered-artifact", "exact Bundle-to-Site assembly"),
    CheckSpec("bundle-reader", "rendered-artifact", "an explicit Bundle reader check"),
    CheckSpec("site-artifact", "rendered-artifact", "an explicit rendered Site check"),
)

CHECK_NAMES = tuple(spec.name for spec in CHECKS)

# Remote acceptance is listed for classification and review, but is not
# exposed as a runnable local ``--check``.  Keeping it beside the local
# inventory makes deliberate exclusion testable.
REMOTE_CHECKS = (
    CheckSpec("browser", "real-browser/PWA", "real Chromium acceptance"),
    CheckSpec("pwa", "real-browser/PWA", "PWA lifecycle acceptance"),
    CheckSpec(
        "cross-authority",
        "real-browser/PWA",
        "producer-to-browser acceptance",
    ),
    CheckSpec("github-api", "GitHub/API", "GitHub result aggregation"),
)
ALL_CHECK_SPECS = CHECKS + REMOTE_CHECKS
CHECK_SPECS = {spec.name: spec for spec in ALL_CHECK_SPECS}

# These are the only checks required before a Site change starts expensive CI.
# Keep this tuple ordered so the output is stable and the dependency boundary
# is visible in the command's execution order.
SOURCE_READY_CHECKS = (
    "l0",
    "core",
    "node",
    "site-contracts",
    "dependency-boundary",
)

# Composition owns the validator and its runtime provisioning.  Keep this
# check available through an explicit profile, but do not make it part of the
# advertised no-install source gate.
MANAGED_VALIDATION_CHECKS = ("composition-consumer",)

# Artifact-local validation is deliberately explicit and fail-closed.  It does
# not acquire a Bundle or render a Site; callers must supply both inputs.
ARTIFACT_LOCAL_CHECKS = ("bundle-reader", "site-artifact")

# These acceptance classes are intentionally not part of any local profile.
# They remain owned by the applicable GitHub workflows.
REMOTE_ACCEPTANCE_CLASSES = frozenset({"real-browser/PWA", "GitHub/API"})


def playground_node_tests(root: Path) -> tuple[str, ...]:
    """Return the complete, deterministic Playground Node test inventory."""

    return tuple(
        str(path.relative_to(root))
        for path in sorted((root / "tests").glob("composition-playground*.test.mjs"))
    )


def validate_registry() -> None:
    """Raise ``ValueError`` if the local profile inventory is inconsistent."""

    if len(CHECK_NAMES) != len(CHECKS):
        raise ValueError("Site check registry names are not unique")
    for profile, checks in {
        "source-ready": SOURCE_READY_CHECKS,
        "composition-validation": MANAGED_VALIDATION_CHECKS,
        "artifact-local": ARTIFACT_LOCAL_CHECKS,
    }.items():
        unknown = sorted(set(checks) - set(CHECK_NAMES))
        if unknown:
            raise ValueError(f"{profile} contains unknown Site checks: {unknown}")
    if len(CHECK_SPECS) != len(ALL_CHECK_SPECS):
        raise ValueError("Site check registry names are not unique")
    for spec in ALL_CHECK_SPECS:
        if spec.execution_class not in EXECUTION_CLASSES:
            raise ValueError(f"unknown execution class for {spec.name}: {spec.execution_class}")
    local_checks = set(SOURCE_READY_CHECKS) | set(ARTIFACT_LOCAL_CHECKS)
    if any(CHECK_SPECS[name].execution_class in REMOTE_ACCEPTANCE_CLASSES for name in local_checks):
        raise ValueError("a local Site profile contains remote acceptance")
    if any(
        CHECK_SPECS[name].execution_class not in {"source/core", "node/source"}
        for name in SOURCE_READY_CHECKS
    ):
        raise ValueError("source-ready contains a check that may need managed runtime or artifacts")
    if any(
        CHECK_SPECS[name].execution_class != "managed-validation"
        for name in MANAGED_VALIDATION_CHECKS
    ):
        raise ValueError("composition-validation contains a non-managed check")


validate_registry()
