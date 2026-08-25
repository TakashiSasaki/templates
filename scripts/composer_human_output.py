#!/usr/bin/env python3
"""Render Composer public payloads for human readers without changing payload semantics."""

from __future__ import annotations

from typing import Any


def _messages(payload: dict[str, Any]) -> list[str]:
    messages: list[str] = []
    error = payload.get("error")
    if isinstance(error, str) and error.strip():
        messages.append(error.strip())
    errors = payload.get("errors")
    if isinstance(errors, list):
        for entry in errors:
            if isinstance(entry, str) and entry.strip():
                messages.append(entry.strip())
    diagnostics = payload.get("diagnostics")
    if isinstance(diagnostics, list):
        for entry in diagnostics:
            if not isinstance(entry, dict):
                continue
            message = entry.get("message")
            if isinstance(message, str) and message.strip():
                messages.append(message.strip())
    return messages


def _ownership_lines(payload: dict[str, Any]) -> list[str]:
    ownership = payload.get("ownership")
    if not isinstance(ownership, dict):
        return []
    composition_owned = ownership.get("composition_owned")
    consumer_owned = ownership.get("consumer_owned")
    if not isinstance(composition_owned, dict) or not isinstance(consumer_owned, dict):
        return []

    managed = composition_owned.get("managed")
    generated = composition_owned.get("generated")
    seeds = consumer_owned.get("seeds")
    extras = consumer_owned.get("extras")
    managed_count = len(managed) if isinstance(managed, list) else 0
    generated_count = len(generated) if isinstance(generated, list) else 0
    seed_count = len(seeds) if isinstance(seeds, list) else 0
    extra_count = len(extras) if isinstance(extras, list) else 0
    lines = [
        "Ownership: "
        f"{managed_count} managed + {generated_count} generated Composition-owned paths; "
        f"{seed_count} active consumer-owned seeds + {extra_count} preserved consumer extras."
    ]
    if isinstance(seeds, list) and seeds:
        shown = ", ".join(str(path) for path in seeds[:5])
        suffix = ", ..." if len(seeds) > 5 else ""
        lines.append(f"Editable seeds: {shown}{suffix}")
    if isinstance(extras, list) and extras:
        shown = ", ".join(str(path) for path in extras[:5])
        suffix = ", ..." if len(extras) > 5 else ""
        lines.append(f"Preserved extras to review: {shown}{suffix}")
    return lines


def render_human(payload: dict[str, Any], command: str) -> str:
    """Render a public structured payload as concise status and next-action text."""

    messages = _messages(payload)
    lines = [f"Composition {command}"]
    target = payload.get("target")
    if isinstance(target, str):
        lines.append(f"Target: {target}")

    if command == "inspect":
        state = payload.get("state")
        if isinstance(state, str):
            lines.append(f"State: {state}")
        for message in messages:
            lines.append(f"Error: {message}")
        if state in {"absent", "unmanaged"}:
            lines.append("Next: create or select composition.json, then run plan.")
        elif state == "managed-valid":
            lines.append(
                "Next: continue ordinary consumer work and run validate after edits; "
                "use update/upgrade only when Composition source or intent changes."
            )
        elif state == "managed-interrupted":
            lines.append(
                "Next: recover the recorded transaction by rerunning the matching apply mode "
                "with the exact recorded Composition source revision."
            )
        elif state == "managed-invalid":
            lines.append("Next: repair the reported managed-state errors, then inspect again.")
        else:
            lines.append("Next: follow the reported state-specific guidance before mutation.")

    elif command == "plan":
        operation = payload.get("operation")
        if isinstance(operation, str):
            lines.append(f"Operation: {operation}")
        actions = payload.get("actions")
        conflicts = payload.get("conflicts")
        action_count = len(actions) if isinstance(actions, list) else 0
        conflict_count = len(conflicts) if isinstance(conflicts, list) else 0
        lines.append("Mutation: none; plan is read-only.")
        lines.append(f"Actions: {action_count}")
        lines.append(f"Conflicts: {conflict_count}")
        for message in messages:
            lines.append(f"Error: {message}")
        if conflict_count:
            lines.append("Next: resolve every conflict and run plan again. Do not apply this plan.")
        elif messages:
            lines.append("Next: resolve the reported issue and run plan again.")
        else:
            lines.append(
                "Next: review the actions. If they are correct, run apply with the same "
                "mode, config, and target."
            )

    elif command == "apply":
        status = payload.get("status")
        if isinstance(status, str):
            lines.append(f"Status: {status}")
        operation = payload.get("operation")
        if isinstance(operation, str):
            lines.append(f"Operation: {operation}")
        lines.extend(_ownership_lines(payload))
        for message in messages:
            lines.append(f"Error: {message}")
        next_steps = payload.get("next_steps")
        if isinstance(next_steps, list) and next_steps:
            lines.append("Next steps:")
            for entry in next_steps:
                if not isinstance(entry, dict):
                    continue
                message = entry.get("message")
                if isinstance(message, str) and message.strip():
                    lines.append(f"- {message.strip()}")
        elif messages:
            lines.append("Next: resolve the reported issue, then rerun the appropriate lifecycle step.")
        else:
            lines.append("Next: run validate before relying on the repository as managed-valid.")

    elif command == "validate":
        status = payload.get("status")
        if isinstance(status, str):
            lines.append(f"Status: {status}")
        checks = payload.get("checks")
        if isinstance(checks, list):
            failed = sum(
                1
                for check in checks
                if isinstance(check, dict) and check.get("status") == "failed"
            )
            lines.append(f"Checks: {len(checks)} total, {failed} failed.")
        for message in messages:
            lines.append(f"Error: {message}")
        if status == "valid" and not messages:
            lines.append(
                "Next: continue consumer/product work and rerun validate after relevant edits."
            )
        else:
            lines.append("Next: fix the reported errors or failed checks, then run validate again.")

    else:
        status = payload.get("status")
        if isinstance(status, str):
            lines.append(f"Status: {status}")
        for message in messages:
            lines.append(f"Error: {message}")

    return "\n".join(lines) + "\n"
