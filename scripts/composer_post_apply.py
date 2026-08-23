#!/usr/bin/env python3
"""Build deterministic consumer guidance from Composition lock transitions."""

from __future__ import annotations

from typing import Any


def _active_paths(lock: dict[str, Any], ownership: str) -> list[str]:
    return sorted(
        entry["destination"]
        for entry in lock["files"]
        if entry["ownership"] == ownership
    )


def _consumer_owned_extras(
    lock: dict[str, Any],
    previous_lock: dict[str, Any] | None,
) -> list[str]:
    if previous_lock is None:
        return []
    active = {entry["destination"] for entry in lock["files"]}
    return sorted(
        entry["destination"]
        for entry in previous_lock["files"]
        if entry["ownership"] == "seed" and entry["destination"] not in active
    )


def build_post_apply_guidance(
    lock: dict[str, Any],
    *,
    previous_lock: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Describe active ownership and actionable post-apply steps.

    Active ownership is derived only from the final validated lock. Consumer-owned
    extras are derived only from seed entries in the authoritative previous lock that
    are absent from the final lock; arbitrary filesystem contents are never treated as
    ownership authority.
    """

    managed = _active_paths(lock, "managed")
    generated = _active_paths(lock, "generated")
    seeds = _active_paths(lock, "seed")
    extras = _consumer_owned_extras(lock, previous_lock)

    next_steps: list[dict[str, str]] = []
    if managed or generated:
        next_steps.append(
            {
                "id": "respect-composition-ownership",
                "message": (
                    "Treat Composition-owned managed/generated files as authoritative "
                    "Composition output; do not edit them directly."
                ),
            }
        )
    if seeds:
        next_steps.append(
            {
                "id": "edit-consumer-owned-seeds",
                "message": (
                    "Edit consumer-owned seed files as needed; later managed operations "
                    "preserve their current consumer bytes."
                ),
            }
        )
    if extras:
        next_steps.append(
            {
                "id": "review-consumer-owned-extras",
                "message": (
                    "Review preserved consumer-owned files no longer tracked by Composition; "
                    "archive or delete them when they should not remain in active locations."
                ),
            }
        )
    next_steps.append(
        {
            "id": "validate",
            "message": (
                "Run `validate` after consumer edits or cleanup before relying on the "
                "repository as managed-valid."
            ),
        }
    )

    return {
        "ownership": {
            "composition_owned": {
                "managed": managed,
                "generated": generated,
            },
            "consumer_owned": {
                "seeds": seeds,
                "extras": extras,
            },
        },
        "next_steps": next_steps,
    }
