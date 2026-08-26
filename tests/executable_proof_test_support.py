from __future__ import annotations

from pathlib import Path
from typing import Any


PROOF_KIND_CAPABILITY = {
    "unit-test": "unit",
    "integration-test": "integration",
    "end-to-end-test": "end-to-end",
    "accessibility-test": "accessibility",
    "migration-test": "migration",
    "inspection": "inspection",
    "other": "other",
}


def upgrade_product_evidence_v6(
    evidence: dict[str, Any],
    *,
    browser_command_ids: set[str] | None = None,
    harness_by_command: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Upgrade an in-memory product fixture to v6 without weakening its proof claims.

    Capabilities are derived from the proof kinds that already reference each command.
    Browser capability is never inferred from ``end-to-end-test``; callers must opt in
    for command IDs whose harness actually represents browser execution.
    """

    evidence["schemaVersion"] = 6
    browser_command_ids = browser_command_ids or set()
    harness_by_command = harness_by_command or {}

    proof_kinds: dict[str, set[str]] = {}
    negative_commands: set[str] = set()
    proof_locators: dict[str, list[str]] = {}
    for record in evidence.get("records", []):
        if not isinstance(record, dict):
            continue
        for field in ("positiveEvidence", "negativeEvidence"):
            proofs = record.get(field, [])
            if not isinstance(proofs, list):
                continue
            for proof in proofs:
                if not isinstance(proof, dict):
                    continue
                command_id = proof.get("commandId")
                if not isinstance(command_id, str):
                    continue
                kind = proof.get("kind")
                capability = PROOF_KIND_CAPABILITY.get(kind)
                if capability is not None:
                    proof_kinds.setdefault(command_id, set()).add(capability)
                locator = proof.get("locator")
                if isinstance(locator, str) and locator:
                    proof_locators.setdefault(command_id, []).append(locator)
                if field == "negativeEvidence":
                    negative_commands.add(command_id)

    for command in evidence.get("commands", []):
        if not isinstance(command, dict):
            continue
        command_id = command.get("id")
        if not isinstance(command_id, str):
            continue
        capabilities = set(proof_kinds.get(command_id, set()))
        if command_id in browser_command_ids:
            capabilities.add("browser")
        if not capabilities:
            capabilities.add("other")
        locator = harness_by_command.get(command_id)
        if locator is None:
            candidates = proof_locators.get(command_id, [])
            locator = candidates[0] if candidates else f"tests/{command_id}.py"
        command["execution"] = {
            "capabilities": sorted(capabilities),
            "harness": {"kind": "repository-file", "locator": locator},
            "supportsNegativePath": command_id in negative_commands,
        }
    return evidence


def materialize_declared_harnesses(root: Path, evidence: dict[str, Any]) -> None:
    """Create inert fixture harness files for synthetic consumer-root tests."""

    for command in evidence.get("commands", []):
        if not isinstance(command, dict):
            continue
        execution = command.get("execution")
        if not isinstance(execution, dict):
            continue
        harness = execution.get("harness")
        if not isinstance(harness, dict):
            continue
        locator = harness.get("locator")
        if not isinstance(locator, str) or not locator:
            continue
        path = root / locator
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text("# synthetic executable proof harness\n", encoding="utf-8")
