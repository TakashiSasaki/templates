#!/usr/bin/env python3
"""Advance one reviewed Site provider lock and its machine projections."""

from __future__ import annotations

import argparse
import os
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.generate_agent_bootstrap import (
    AgentBootstrapError,
    build_manifest,
    render_manifest,
    verify_projection,
)
from scripts.resolve_publication_sources import (
    FULL_COMMIT_PATTERN,
    PUBLICATION_NAMES,
    SourceLockError,
    render_source_lock,
    resolve_sources,
)

COMPOSITION_RELEASE_PATH = "release/composition-installer.json"


class PublicationAdvanceError(RuntimeError):
    """Raised when a publication advance cannot be proven safe."""


@dataclass(frozen=True)
class AdvancePlan:
    provider: str
    current_revision: str
    target_revision: str
    revisions: dict[str, str]
    source_lock_bytes: bytes
    agent_manifest_bytes: bytes


def require_full_sha(value: str, label: str) -> str:
    if FULL_COMMIT_PATTERN.fullmatch(value) is None:
        raise PublicationAdvanceError(
            f"{label} must be a full lowercase 40-character commit SHA"
        )
    return value


def require_regular_file(path: Path, label: str) -> Path:
    if path.is_symlink() or not path.is_file():
        raise PublicationAdvanceError(f"{label} must be a regular file: {path}")
    return path


def git_output(root: Path, *args: str) -> bytes:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), *args],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = ""
        if isinstance(exc, subprocess.CalledProcessError):
            detail = exc.stderr.decode("utf-8", errors="replace").strip()
        suffix = f": {detail}" if detail else ""
        raise PublicationAdvanceError(
            f"unable to inspect exact provider checkout {root}{suffix}"
        ) from exc
    return completed.stdout


def git_head(root: Path, label: str) -> str:
    raw = git_output(root, "rev-parse", "--verify", "HEAD^{commit}")
    try:
        revision = raw.decode("ascii").strip()
    except UnicodeDecodeError as exc:
        raise PublicationAdvanceError(f"{label} HEAD must be an ASCII commit SHA") from exc
    return require_full_sha(revision, f"{label} HEAD")


def git_file(root: Path, revision: str, path: str, label: str) -> bytes:
    try:
        return git_output(root, "show", f"{revision}:{path}")
    except PublicationAdvanceError as exc:
        raise PublicationAdvanceError(
            f"unable to read {label} from exact revision {revision}: {path}"
        ) from exc


def plan_advance(
    *,
    site_root: Path,
    provider: str,
    provider_root: Path,
    composition_root: Path,
    target_revision: str,
    expected_current: str,
) -> AdvancePlan:
    if provider not in PUBLICATION_NAMES:
        raise PublicationAdvanceError(
            "provider must be exactly one of: " + ", ".join(PUBLICATION_NAMES)
        )
    target_revision = require_full_sha(target_revision, "target revision")
    expected_current = require_full_sha(expected_current, "expected current revision")

    try:
        site_root = site_root.resolve(strict=True)
        provider_root = provider_root.resolve(strict=True)
        composition_root = composition_root.resolve(strict=True)
    except OSError as exc:
        raise PublicationAdvanceError(f"unable to resolve cutover input: {exc}") from exc

    source_lock = require_regular_file(
        site_root / "publication-sources.json",
        "publication source lock",
    )
    require_regular_file(site_root / "agent.json", "repository agent manifest")
    require_regular_file(site_root / "assets/agent.json", "published agent manifest")

    try:
        current = resolve_sources(source_lock, {})
    except SourceLockError as exc:
        raise PublicationAdvanceError(str(exc)) from exc
    if current[provider] != expected_current:
        raise PublicationAdvanceError(
            f"expected current {provider} revision {expected_current}, "
            f"but the source lock contains {current[provider]}"
        )

    provider_head = git_head(provider_root, f"{provider} provider checkout")
    if provider_head != target_revision:
        raise PublicationAdvanceError(
            f"{provider} provider checkout HEAD {provider_head} does not match "
            f"target revision {target_revision}"
        )

    revisions = dict(current)
    revisions[provider] = target_revision
    composition_revision = revisions["composition"]
    composition_head = git_head(composition_root, "Composition checkout")
    if composition_head != composition_revision:
        raise PublicationAdvanceError(
            f"Composition checkout HEAD {composition_head} does not match prospective "
            f"publication revision {composition_revision}"
        )

    try:
        lock_bytes = render_source_lock(revisions)
    except SourceLockError as exc:
        raise PublicationAdvanceError(str(exc)) from exc
    release_bytes = git_file(
        composition_root,
        composition_revision,
        COMPOSITION_RELEASE_PATH,
        "Composition installer release descriptor",
    )

    try:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prospective_lock = root / "publication-sources.json"
            prospective_release = root / "composition-installer.json"
            prospective_lock.write_bytes(lock_bytes)
            prospective_release.write_bytes(release_bytes)
            if resolve_sources(prospective_lock, {}) != revisions:
                raise PublicationAdvanceError(
                    "prospective publication source lock did not round-trip deterministically"
                )
            manifest_bytes = render_manifest(
                build_manifest(prospective_lock, prospective_release)
            )
    except (OSError, SourceLockError, AgentBootstrapError) as exc:
        raise PublicationAdvanceError(f"unable to preflight publication advance: {exc}") from exc

    return AdvancePlan(
        provider=provider,
        current_revision=current[provider],
        target_revision=target_revision,
        revisions=revisions,
        source_lock_bytes=lock_bytes,
        agent_manifest_bytes=manifest_bytes,
    )


def replace_regular_file(path: Path, data: bytes, label: str) -> None:
    require_regular_file(path, label)
    mode = stat.S_IMODE(path.stat().st_mode)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=path.parent,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary_path, mode)
        os.replace(temporary_path, path)
    except OSError as exc:
        raise PublicationAdvanceError(f"unable to replace {label} {path}: {exc}") from exc
    finally:
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass


def apply_plan(site_root: Path, plan: AdvancePlan) -> None:
    """Apply projections first and the authoritative source lock last."""
    site_root = site_root.resolve(strict=True)
    replace_regular_file(
        site_root / "agent.json",
        plan.agent_manifest_bytes,
        "repository agent manifest",
    )
    replace_regular_file(
        site_root / "assets/agent.json",
        plan.agent_manifest_bytes,
        "published agent manifest",
    )
    replace_regular_file(
        site_root / "publication-sources.json",
        plan.source_lock_bytes,
        "publication source lock",
    )


def verify_applied_plan(site_root: Path, plan: AdvancePlan) -> None:
    site_root = site_root.resolve(strict=True)
    try:
        actual = resolve_sources(site_root / "publication-sources.json", {})
    except SourceLockError as exc:
        raise PublicationAdvanceError(str(exc)) from exc
    if actual != plan.revisions:
        raise PublicationAdvanceError(
            "publication source lock does not match the planned provider revisions"
        )
    try:
        verify_projection(
            site_root / "agent.json",
            plan.agent_manifest_bytes,
            "repository agent manifest",
        )
        verify_projection(
            site_root / "assets/agent.json",
            plan.agent_manifest_bytes,
            "published agent manifest",
        )
    except AgentBootstrapError as exc:
        raise PublicationAdvanceError(str(exc)) from exc


def advance_publication(
    *,
    site_root: Path,
    provider: str,
    provider_root: Path,
    composition_root: Path,
    target_revision: str,
    expected_current: str,
) -> AdvancePlan:
    plan = plan_advance(
        site_root=site_root,
        provider=provider,
        provider_root=provider_root,
        composition_root=composition_root,
        target_revision=target_revision,
        expected_current=expected_current,
    )
    apply_plan(site_root, plan)
    verify_applied_plan(site_root, plan)
    return plan


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-root", type=Path, default=Path("."))
    parser.add_argument("--provider", choices=PUBLICATION_NAMES, required=True)
    parser.add_argument("--provider-root", type=Path, required=True)
    parser.add_argument("--composition-root", type=Path, required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--expected-current", required=True)
    args = parser.parse_args()

    try:
        plan = advance_publication(
            site_root=args.site_root,
            provider=args.provider,
            provider_root=args.provider_root,
            composition_root=args.composition_root,
            target_revision=args.target,
            expected_current=args.expected_current,
        )
    except (OSError, PublicationAdvanceError) as exc:
        print(f"publication advance failed: {exc}", file=sys.stderr)
        return 1

    print(
        f"Advanced {plan.provider} publication: "
        f"{plan.current_revision} -> {plan.target_revision}"
    )
    print("Publication source lock and agent projections are synchronized.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
