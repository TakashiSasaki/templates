from __future__ import annotations

import re
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
_PYTHON_MODULE_SEGMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _python_module(locator: str) -> str | None:
    if not locator.endswith(".py"):
        return None
    parts = locator[:-3].split("/")
    if not parts or not all(_PYTHON_MODULE_SEGMENT.fullmatch(part) for part in parts):
        return None
    return ".".join(parts)


def _invocation_for(command: str, locator: str) -> str:
    if command == f"python {locator}":
        return "python-script"
    module = _python_module(locator)
    if module is not None and command == f"python -m unittest {module}":
        return "python-unittest"
    if command == f"./{locator}":
        return "direct"
    raise AssertionError(
        f"fixture command {command!r} does not exactly invoke declared harness {locator!r}; "
        "use python-script, python-unittest, or direct invocation"
    )


def upgrade_product_evidence_v6(
    evidence: dict[str, Any],
    *,
    browser_command_ids: set[str] | None = None,
    harness_by_command: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Upgrade an in-memory product fixture to v6 without weakening its proof claims.

    Capabilities are derived from the proof kinds that already reference each command.
    Browser capability is never inferred from ``end-to-end-test``; callers must opt in
    for command IDs whose harness actually represents browser execution. The helper also
    requires the legacy human command text to exactly identify a supported invocation of
    the declared repository harness instead of manufacturing invocation authority.
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
        command_text = command.get("command")
        if not isinstance(command_text, str):
            raise AssertionError(f"fixture command {command_id!r} requires command text")
        invocation = _invocation_for(command_text, locator)
        command["execution"] = {
            "capabilities": sorted(capabilities),
            "harness": {
                "kind": "repository-file",
                "locator": locator,
                "invocation": invocation,
            },
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