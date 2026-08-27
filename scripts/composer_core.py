#!/usr/bin/env python3
"""Composition core facade with an explicit source-context boundary.

The implementation remains in ``composer_core_impl`` while source identity and
tracked-authority services are wired here. This keeps the public module surface
stable while allowing normal consumers to move from Git checkouts to immutable
source snapshots without duplicating Composer semantics.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import composer_core_impl as _impl
import composer_source

# Preserve the historical module surface, including private helpers that are
# intentionally consumed by sibling Composer modules and regression tests.
for _name, _value in vars(_impl).items():
    if not _name.startswith("__"):
        globals()[_name] = _value


def _select_source_context() -> Any:
    # A real authority checkout must never be downgraded to caller-supplied snapshot
    # metadata through an inherited environment variable. Archive-backed normal
    # consumers have no .git directory and therefore require the runner-provided
    # immutable snapshot context.
    git_directory = _impl.SOURCE_ROOT / ".git"
    if git_directory.is_dir() and not git_directory.is_symlink():
        return composer_source.GitSourceContext(_impl.SOURCE_ROOT)
    return composer_source.context_from_environment(_impl.SOURCE_ROOT)


_SOURCE_CONTEXT: Any = _select_source_context()


def source_context() -> Any:
    """Return the active Composition source context.

    A reviewed Git checkout is the authority-maintainer default. Normal consumers
    provide immutable snapshot metadata through COMPOSITION_SOURCE_CONTEXT;
    Composer semantics remain independent of acquisition mechanics.
    """

    return _SOURCE_CONTEXT


def _translate_source_error(exc: composer_source.SourceContextError) -> None:
    raise _impl.CompositionError(exc.code, exc.message) from exc


def _run_git(
    *arguments: str,
    allow_failure: bool = False,
):
    """Compatibility bridge for maintainer tests and checkout-only helpers."""

    context = source_context()
    if not isinstance(context, composer_source.GitSourceContext):
        raise _impl.CompositionError(
            "GIT_SOURCE_CONTEXT_REQUIRED",
            "this operation requires a reviewed Git source context",
        )
    try:
        return context.run_git(*arguments, allow_failure=allow_failure)
    except composer_source.SourceContextError as exc:
        _translate_source_error(exc)


def source_revision() -> str:
    try:
        return source_context().revision()
    except composer_source.SourceContextError as exc:
        _translate_source_error(exc)
    raise AssertionError("unreachable")


def _assert_tracked_authority(path: Path) -> None:
    try:
        source_context().assert_authority(path)
    except composer_source.SourceContextError as exc:
        _translate_source_error(exc)


# Functions defined in composer_core_impl resolve globals in that implementation
# module. Rebind the source-sensitive names there so every existing call site,
# including nested helper calls, crosses the same context boundary.
_impl._run_git = _run_git
_impl.source_revision = source_revision
_impl._assert_tracked_authority = _assert_tracked_authority

# Re-export the rebound names after the initial implementation namespace copy.
globals()["_run_git"] = _run_git
globals()["source_revision"] = source_revision
globals()["_assert_tracked_authority"] = _assert_tracked_authority
