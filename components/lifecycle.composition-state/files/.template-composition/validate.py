#!/usr/bin/env python3
"""Run Composition validation and add prerequisite-aware lifecycle projection."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
from pathlib import Path
from typing import Any


_IMPL_PATH = Path(__file__).with_name("validate_impl.py")
_SPEC = importlib.util.spec_from_file_location("composition_validation_impl", _IMPL_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError("cannot load Composition validation implementation")
_impl = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_impl)

WEBAPP_ACTION_REGISTRY_RELATIVE = ".template-composition/webapp-actions.json"
RELEASE_EXECUTION_ACTION_REGISTRY_RELATIVE = ".template-composition/release-execution-actions.json"
_PLACEHOLDER = re.compile(r"^\{[a-z_]+\}$")


def __getattr__(name: str) -> Any:
    """Preserve the implementation module's internal test/diagnostic surface."""
    return getattr(_impl, name)


def _component_selected(checks: list[dict[str, Any]], component: str) -> bool:
    return any(check.get("component") == component for check in checks)


def _deferred_proof_state(root: Path) -> tuple[list[str], list[str]]:
    """Return all deferred proofs and the subset requiring browser capability.

    This is a presentation projection over already-authoritative implementation
    evidence. It does not validate proof semantics; the selected implementation-
    evidence validator remains authoritative for that contract.
    """
    try:
        evidence = _impl._load_json(root / "contracts/implementation-evidence.json")
    except (OSError, UnicodeError, json.JSONDecodeError, _impl.StrictJsonError):
        return [], []
    if not isinstance(evidence, dict) or evidence.get("mode") != "product":
        return [], []

    commands = evidence.get("commands")
    if not isinstance(commands, list):
        return [], []
    command_capabilities: dict[str, set[str]] = {}
    for command in commands:
        if not isinstance(command, dict) or not isinstance(command.get("id"), str):
            continue
        execution = command.get("execution")
        capabilities = execution.get("capabilities") if isinstance(execution, dict) else None
        command_capabilities[command["id"]] = {
            item for item in capabilities if isinstance(item, str)
        } if isinstance(capabilities, list) else set()

    deferred: set[str] = set()
    browser: set[str] = set()
    records = evidence.get("records")
    if not isinstance(records, list):
        return [], []
    for record in records:
        if not isinstance(record, dict):
            continue
        for field in ("positiveEvidence", "negativeEvidence"):
            proofs = record.get(field)
            if not isinstance(proofs, list):
                continue
            for proof in proofs:
                if (
                    not isinstance(proof, dict)
                    or proof.get("status") != "deferred"
                    or not isinstance(proof.get("id"), str)
                ):
                    continue
                proof_id = proof["id"]
                deferred.add(proof_id)
                command_id = proof.get("commandId")
                if (
                    isinstance(command_id, str)
                    and "browser" in command_capabilities.get(command_id, set())
                ):
                    browser.add(proof_id)
    return sorted(deferred), sorted(browser)


def _load_action_command(
    root: Path,
    *,
    registry_relative: str,
    registry_schema: str,
    action: str,
) -> dict[str, Any] | None:
    try:
        registry = _impl._load_json(root / registry_relative)
    except (OSError, UnicodeError, json.JSONDecodeError, _impl.StrictJsonError):
        return None
    if (
        not isinstance(registry, dict)
        or set(registry) != {"$schema", "schemaVersion", "actions"}
        or registry.get("$schema") != registry_schema
        or registry.get("schemaVersion") != 1
    ):
        return None
    actions = registry.get("actions")
    if not isinstance(actions, dict) or set(actions) != {action}:
        return None
    entry = actions.get(action)
    if (
        not isinstance(entry, dict)
        or set(entry) != {"argv", "caller_inputs", "output_schema"}
    ):
        return None
    argv = entry.get("argv")
    caller_inputs = entry.get("caller_inputs")
    output_schema = entry.get("output_schema")
    if (
        not isinstance(argv, list)
        or not argv
        or any(not isinstance(token, str) or not token for token in argv)
        or not isinstance(caller_inputs, list)
        or len(caller_inputs) != len(set(caller_inputs))
        or any(
            not isinstance(token, str) or _PLACEHOLDER.fullmatch(token) is None
            for token in caller_inputs
        )
        or any(
            _PLACEHOLDER.fullmatch(token) is not None and token not in caller_inputs
            for token in argv
        )
        or any(token not in argv for token in caller_inputs)
    ):
        return None
    try:
        output_schema = _impl._portable_path(output_schema)
    except _impl.ValidationRegistryError:
        return None
    return {
        "action": action,
        "argv": list(argv),
        "caller_inputs": list(caller_inputs),
        "output_schema": output_schema,
    }


def _webapp_action_command(root: Path, checks: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not _component_selected(checks, "artifact.webapp-core"):
        return None
    return _load_action_command(
        root,
        registry_relative=WEBAPP_ACTION_REGISTRY_RELATIVE,
        registry_schema="./webapp-actions.schema.json",
        action="diagnose-browser-prerequisites",
    )


def _release_candidate_action_command(
    root: Path,
    checks: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not _component_selected(checks, "lifecycle.release-execution"):
        return None
    return _load_action_command(
        root,
        registry_relative=RELEASE_EXECUTION_ACTION_REGISTRY_RELATIVE,
        registry_schema="./release-execution-actions.schema.json",
        action="verify-release-candidate",
    )


def _projection_failure(
    mode: str,
    deferred_checks: list[str],
    deferred_proofs: list[str],
    blocker: str,
) -> dict[str, Any]:
    return {
        "schema_version": 3,
        "lifecycle_stage": "composition-invalid",
        "implementation_evidence_mode": mode,
        "release_readiness": "not-evaluated",
        "blocking_conditions": [blocker],
        "deferred_checks": deferred_checks,
        "deferred_proofs": deferred_proofs,
        "next_actions": ["inspect", "plan", "apply", "validate"],
        "conditional_prerequisite_commands": [],
    }


def _augment_lifecycle(
    root: Path,
    checks: list[dict[str, Any]],
    value: dict[str, Any],
) -> dict[str, Any]:
    projected = dict(value)
    projected["schema_version"] = 3
    deferred_proofs, browser_proofs = _deferred_proof_state(root)
    projected["deferred_proofs"] = deferred_proofs
    projected["conditional_prerequisite_commands"] = []

    if projected.get("lifecycle_stage") == "composition-invalid":
        return projected

    if (
        projected.get("implementation_evidence_mode") == "product"
        and _component_selected(checks, "lifecycle.release-execution")
    ):
        release_command = _release_candidate_action_command(root, checks)
        if release_command is None:
            return _projection_failure(
                str(projected.get("implementation_evidence_mode")),
                list(projected.get("deferred_checks", [])),
                deferred_proofs,
                "release-candidate-command-registry-invalid",
            )
        projected["conditional_prerequisite_commands"] = [
            {
                "condition": "before-release-production",
                **release_command,
            }
        ]

    if not deferred_proofs or projected.get("implementation_evidence_mode") != "product":
        return projected

    projected["lifecycle_stage"] = "implemented-product"
    projected["release_readiness"] = "not-ready"
    blockers = list(projected.get("blocking_conditions", []))
    if "release-readiness-not-evaluated" in blockers:
        blockers.remove("release-readiness-not-evaluated")
    if "deferred-proof" not in blockers:
        blockers.append("deferred-proof")
    projected["blocking_conditions"] = blockers

    # Checkpoint authority retains precedence over evidence-resolution actions.
    if projected.get("next_actions") == ["create-product-checkpoint"]:
        return projected

    projected["next_actions"] = [
        "resolve-deferred-proof",
        "run-product-verifier",
        "validate-product-state",
        "check-release-readiness",
    ]
    projected.pop("next_action_command", None)

    if browser_proofs and _component_selected(checks, "artifact.webapp-core"):
        command = _webapp_action_command(root, checks)
        if command is None:
            return _projection_failure(
                str(projected.get("implementation_evidence_mode")),
                list(projected.get("deferred_checks", [])),
                deferred_proofs,
                "browser-diagnostic-command-registry-invalid",
            )
        projected["next_action_command"] = command
    return projected


def _lifecycle_projection(
    root: Path,
    status: str,
    checks: list[dict[str, Any]],
) -> dict[str, Any]:
    return _augment_lifecycle(
        root,
        checks,
        _impl._lifecycle_projection(root, status, checks),
    )


def validate(root: Path) -> dict[str, Any]:
    result = _impl._validate_base(root)
    result["lifecycle"] = _lifecycle_projection(
        root,
        result["status"],
        result.get("checks", []),
    )
    return result


def _render_human(result: dict[str, Any]) -> None:
    _impl._render_human(result)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--format", choices=("human", "json"), default="human")
    args = parser.parse_args()
    root = Path(args.root).absolute()
    result = validate(root)
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _render_human(result)
    return 0 if result["status"] == "valid" else 1


if __name__ == "__main__":
    raise SystemExit(main())
