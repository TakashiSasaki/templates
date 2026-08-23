from __future__ import annotations

import json
import re
import subprocess
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path

TOOLCHAIN_REPOSITORY = "TakashiSasaki/templates"
TOOLCHAIN_BRANCH = "policy"
TOOLCHAIN_DISTRIBUTION = "takashisasaki-agent-policy"
FULL_COMMIT_SHA = re.compile(r"^[0-9a-f]{40}$")


def immutable_toolchain_reference(revision: str) -> dict[str, str]:
    if FULL_COMMIT_SHA.fullmatch(revision) is None:
        raise ValueError("Toolchain revision must be a full lowercase commit SHA")
    return {
        "repository": TOOLCHAIN_REPOSITORY,
        "revision": revision,
    }


def toolchain_reference(revision: str) -> dict[str, str]:
    return immutable_toolchain_reference(revision)


def installed_vcs_revision() -> str | None:
    try:
        installed = distribution(TOOLCHAIN_DISTRIBUTION)
    except PackageNotFoundError:
        return None
    raw = installed.read_text("direct_url.json")
    if raw is None:
        return None
    try:
        direct_url = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("Installed toolchain direct_url.json is invalid") from exc
    if not isinstance(direct_url, dict):
        raise ValueError("Installed toolchain direct_url.json must be an object")
    vcs_info = direct_url.get("vcs_info")
    if vcs_info is None:
        return None
    if not isinstance(vcs_info, dict) or vcs_info.get("vcs") != "git":
        raise ValueError("Installed toolchain VCS provenance is unsupported")
    requested = vcs_info.get("requested_revision")
    commit_id = vcs_info.get("commit_id")
    if not isinstance(requested, str) or FULL_COMMIT_SHA.fullmatch(requested) is None:
        raise ValueError("Installed toolchain was not requested by full commit SHA")
    if not isinstance(commit_id, str) or FULL_COMMIT_SHA.fullmatch(commit_id) is None:
        raise ValueError("Installed toolchain commit identity is not a full commit SHA")
    if requested != commit_id:
        raise ValueError("Installed toolchain requested revision does not match commit identity")
    return commit_id


def checkout_revision(source_root: Path | None = None) -> str | None:
    root = (source_root or Path(__file__).resolve().parents[2]).resolve()
    try:
        revision = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "--verify", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    if FULL_COMMIT_SHA.fullmatch(revision) is None:
        raise ValueError("Source checkout revision is not a full lowercase commit SHA")
    return revision


def resolve_toolchain_revision(explicit: str | None = None) -> str:
    if explicit is not None:
        return immutable_toolchain_reference(explicit)["revision"]

    installed = installed_vcs_revision()
    if installed is not None:
        return installed
    checkout = checkout_revision()
    if checkout is not None:
        return checkout
    raise ValueError(
        "Unable to determine an immutable toolchain revision; "
        "supply --toolchain-revision with the exact full commit SHA"
    )
