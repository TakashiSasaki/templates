#!/usr/bin/env python3
"""Consumer-facing remediation for the public Composer CLI."""

from __future__ import annotations

import copy
from typing import Any


def _value(entry: dict[str, Any], key: str, fallback: str) -> str:
    value = entry.get(key)
    return str(value) if value not in (None, "") else fallback


def consumer_message(entry: dict[str, Any]) -> str:
    """Return an actionable public message while preserving the diagnostic code."""

    code = str(entry.get("code", ""))
    message = entry.get("message", "")
    raw_message = message if isinstance(message, str) else str(message)
    original = raw_message.strip()
    destination = _value(entry, "destination", "the affected destination")
    component = _value(entry, "component", "the affected component")

    if code == "NOT_A_MANAGED_CONSUMER_ENTRYPOINT":
        return (
            "Composition material exists without a managed consumer lock. "
            "Do not run materialized .template-composition files directly; use the "
            "installed Composition skill runner for initial composition, for example "
            "`python scripts/run.py --repository <root> plan --config composition.json`."
        )

    if code == "MANAGED_LOCK_REQUIRED":
        return (
            "This managed operation requires .template-composition/lock.json. "
            "Run `inspect` on the target first; use initial mode only when the target is unmanaged "
            "and no Composition lock exists."
        )
    if code == "RECOVERY_REQUIRED":
        return (
            "An interrupted managed transaction is present. Rerun the matching "
            "`apply --mode update` or `apply --mode upgrade` at the exact Composition source revision "
            "recorded in .template-composition/transaction.json; do not start a new plan or delete "
            "the transaction marker manually."
        )
    if code == "RECOVERY_OPERATION_MISMATCH":
        return (
            f"{original}. Rerun `apply` with the operation recorded in "
            ".template-composition/transaction.json instead of changing or deleting the marker."
        )
    if code == "RECOVERY_SOURCE_MISMATCH":
        return (
            f"{original}. Check out that exact Composition revision and rerun the matching `apply`; "
            "if the recorded operation is upgrade, recovery must omit --config."
        )
    if code == "OLD_SOURCE_REVISION_UNAVAILABLE":
        return (
            f"{original}. Make that locked revision available in the local Composition Git history "
            "before retrying the managed plan or apply; do not bypass the ancestry check."
        )
    if code == "SOURCE_REVISION_NOT_DESCENDANT":
        return (
            f"{original}. Use the locked source revision itself or a descendant of it, then rerun the "
            "managed operation; do not advance the consumer from an unrelated source history."
        )
    if code == "COMPONENT_VERSION_UPGRADE_REQUIRED":
        return (
            f"Component version changed for {component}. Ordinary update will not cross this "
            "compatibility boundary; use `--mode upgrade` with an explicit --config describing the "
            "desired consumer intent."
        )
    if code == "LOCAL_MODIFICATION":
        ownership = _value(entry, "ownership", "managed/generated")
        return (
            f"Local {ownership} material differs from the locked digest at {destination}. Composer "
            "will not merge, overwrite, or delete it; restore the locked bytes if Composition should "
            "remain authoritative, or redesign ownership/source authority, then rerun `plan`."
        )
    if code == "OLD_STATE_INVALID":
        return (
            f"The locked materialized state is invalid at {destination}: {original}. Repair the target "
            "to a regular, safe path matching the managed state, then rerun `plan`; Composer will not "
            "repair it by overwriting an unexpected state."
        )
    if code == "DESTINATION_CONFLICT":
        return (
            f"The planned destination conflicts with existing repository structure at {destination}: "
            f"{original}. Reconcile the ordinary repository path deliberately, then rerun `plan`."
        )
    if code == "FILE_OWNER_TRANSITION_UPGRADE_REQUIRED":
        return (
            f"The component owner would change at {destination}. Update treats this as an explicit "
            "compatibility boundary, but current upgrade also does not infer owner migration; provide "
            "an explicit source-side migration design before retrying."
        )
    if code == "OWNERSHIP_TRANSITION_UPGRADE_REQUIRED":
        return (
            f"The ownership mode would change at {destination}. Update treats this as an explicit "
            "compatibility boundary, but current upgrade also does not infer ownership migration; "
            "provide an explicit source-side migration design before retrying."
        )
    if code == "FILE_OWNER_TRANSITION_NOT_SUPPORTED":
        return (
            f"Explicit upgrade cannot infer the required component-owner migration at {destination}. "
            "Provide a source-side migration design rather than editing lock metadata or retrying the "
            "same upgrade unchanged."
        )
    if code == "OWNERSHIP_TRANSITION_NOT_SUPPORTED":
        return (
            f"Explicit upgrade cannot infer the required ownership-mode migration at {destination}. "
            "Provide a source-side migration design rather than editing lock metadata or retrying the "
            "same upgrade unchanged."
        )
    if code == "UPDATE_CONFIG_NOT_ALLOWED":
        return (
            "Update preserves normalized lock-v2 intent and therefore forbids --config. Remove --config "
            "for an ordinary update, or use `--mode upgrade` when you intend to change recipe, component "
            "selection, parameters, or a compatibility boundary."
        )
    if code == "UPGRADE_CONFIG_REQUIRED":
        return (
            "A new upgrade requires --config with the explicitly desired consumer intent. Supply the "
            "configuration for a new plan/apply; only interrupted upgrade recovery omits --config."
        )
    if code == "RECOVERY_CONFIG_NOT_ALLOWED":
        return (
            "Interrupted upgrade recovery is already bound to the intent recorded in the transaction. "
            "Remove --config and rerun `apply --mode upgrade` at the exact recorded Composition revision."
        )
    if code == "PRECONDITION_CHANGED":
        return (
            f"{original}. Inspect the unexpected target change and preserve the transaction marker if "
            "one exists; Composer will not force an overwrite when a recorded precondition no longer matches."
        )
    return raw_message


def remediate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Copy a Composer JSON payload and improve messages for known consumer diagnostics."""

    result = copy.deepcopy(payload)

    if "code" in result and "message" in result:
        result["message"] = consumer_message(result)

    conflicts = result.get("conflicts")
    if isinstance(conflicts, list):
        for entry in conflicts:
            if isinstance(entry, dict) and "code" in entry and "message" in entry:
                entry["message"] = consumer_message(entry)

    files = result.get("files")
    if isinstance(files, dict):
        file_conflicts = files.get("conflict")
        if isinstance(file_conflicts, list):
            for entry in file_conflicts:
                if isinstance(entry, dict) and "code" in entry and "message" in entry:
                    entry["message"] = consumer_message(entry)

    return result
