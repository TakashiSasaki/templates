#!/usr/bin/env python3
"""Managed Composition facade wired to the active source context."""

from __future__ import annotations

import composer_core as core
import composer_managed_impl as _impl
import composer_source

for _name, _value in vars(_impl).items():
    if not _name.startswith("__"):
        globals()[_name] = _value


def _verify_source_transition(old_revision: str, new_revision: str) -> None:
    try:
        core.source_context().verify_descendant(old_revision, new_revision)
    except composer_source.SourceContextError as exc:
        raise _impl.ManagedPlanError(exc.code, exc.message) from exc


_impl._verify_source_transition = _verify_source_transition
globals()["_verify_source_transition"] = _verify_source_transition
