#!/usr/bin/env python3
"""Build, verify, and protect Actions-native trusted-review freeze objects."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from scripts.prepare_trusted_review_handoff import (
        FreezeBoundaryType,
        FreezeEvidence,
        closed_git_environment,
        expected_freeze_role_identity,
        extract_immutable_installer,
        git_run,
        load_and_verify_state,
        portable_run_identity,
        require_full_sha,
        resolve_base_tree,
        save_state,
        verify_handoff,
    )
    from scripts.trusted_review_actions import (
        OWNER_ID,
        ActionsRunIdentity,
        GitHubActionsObservationVerifier,
        provider_identity,
        validate_observation,
    )
    from scripts.trusted_review_freeze import (
        GH_EXECUTABLE,
        OCI_REPOSITORY,
        ROLE_TO_SECTION,
        GitHubActionsOciFreezeVerifier,
        GitHubActionsRoleFreezeVerifier,
        TrustedFreezeError,
        _inventory_digest,
        _verify_subject_attestation,
        load_freeze_evidence,
        load_role_freeze_evidence,
        require_protected_view,
    )
except ImportError:
    from prepare_trusted_review_handoff import (
        FreezeBoundaryType,
        FreezeEvidence,
        closed_git_environment,
        expected_freeze_role_identity,
        extract_immutable_installer,
        git_run,
        load_and_verify_state,
        portable_run_identity,
        require_full_sha,
        resolve_base_tree,
        save_state,
        verify_handoff,
    )
    from trusted_review_actions import (
        OWNER_ID,
        ActionsRunIdentity,
        GitHubActionsObservationVerifier,
        provider_identity,
        validate_observation,
    )
    from trusted_review_freeze import (
        GH_EXECUTABLE,
        OCI_REPOSITORY,
        ROLE_TO_SECTION,
        GitHubActionsOciFreezeVerifier,
        GitHubActionsRoleFreezeVerifier,
        TrustedFreezeError,
        _inventory_digest,
        _verify_subject_attestation,
        load_freeze_evidence,
        load_role_freeze_evidence,
        require_protected_view,
    )

ROLE_NAMES = tuple(ROLE_TO_SECTION)
IMAGE_MEDIA_TYPE = "application/vnd.oci.image.manifest.v1+json"
REPOSITORY_URL = "https://github.com/TakashiSasaki/templates.git"
OCI_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise TrustedFreezeError("duplicate JSON key in portable handoff input")
        result[key] = value
    return result


def _read_json_object(path: Path, label: str) -> tuple[dict[str, Any], bytes]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw, object_pairs_hook=_reject_duplicate_keys)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TrustedFreezeError(f"{label} is unavailable or malformed") from exc
    if not isinstance(value, dict):
        raise TrustedFreezeError(f"{label} must be a JSON object")
    return value, raw


def _portable_local_view(
    *,
    handoff: dict[str, Any],
    handoff_sha256: str,
    freeze_evidence: dict[str, Any],
    locators: dict[str, str],
    backing_locators: dict[str, str],
    installed_skill_root: str,
) -> dict[str, Any]:
    roles = []
    for role in ROLE_NAMES:
        entry = next(item for item in freeze_evidence["roles"] if item["role"] == role)
        identity_bytes = json.dumps(
            entry["identity"], sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        roles.append(
            {
                "role": role,
                "inventory_sha256": entry["inventory_sha256"],
                "identity_sha256": hashlib.sha256(identity_bytes).hexdigest(),
            }
        )
    return {
        "schema_version": 1,
        "handoff_sha256": handoff_sha256,
        "provider_observation_sha256": handoff["provider_observation"]["observation_sha256"],
        "freeze_evidence_sha256": handoff["freeze_evidence"]["sha256"],
        "object": freeze_evidence["object"],
        "roles": roles,
        "locators": locators,
        "backing_locators": backing_locators,
        "installed_skill_root": installed_skill_root,
    }


def _docker_login(token: str, *, actor: str, runner: Any) -> None:
    if not token:
        raise TrustedFreezeError("a GHCR read token is required to hydrate portable authority")
    if not re.fullmatch(r"[A-Za-z0-9-]{1,39}", actor):
        raise TrustedFreezeError("GHCR login actor is invalid")
    try:
        runner(
            ["docker", "login", "ghcr.io", "--username", actor, "--password-stdin"],
            input=f"{token}\n",
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise TrustedFreezeError("GHCR authentication failed for immutable authority pull") from exc


def _mountinfo_path(value: str) -> str:
    return (
        value.replace("\\040", " ")
        .replace("\\011", "\t")
        .replace("\\012", "\n")
        .replace("\\134", "\\")
    )


def _is_mountpoint(path: Path) -> bool:
    try:
        lines = Path("/proc/self/mountinfo").read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise TrustedFreezeError("cannot inspect producer mount table for cleanup") from exc
    expected = str(path.expanduser().absolute())
    return any(
        len(fields := line.split()) >= 6 and _mountinfo_path(fields[4]) == expected
        for line in lines
    )


def cleanup_producer_views(
    role_protected_root: Path,
    aggregate_protected_root: Path,
    *,
    runner: Any | None = None,
) -> None:
    """Remove producer mount aliases before proving the portable handoff path."""
    runner = runner or subprocess.run
    role_root = role_protected_root.expanduser().absolute()
    aggregate_root = aggregate_protected_root.expanduser().absolute()
    if role_root.name != "role-protected" or aggregate_root.name != "aggregate-protected":
        raise TrustedFreezeError(
            "producer cleanup roots do not match the trusted workflow layout"
        )
    aggregate_materialized = aggregate_root.parent / f".{aggregate_root.name}.materialized"
    roots = (role_root, aggregate_root, aggregate_materialized)
    if any(root.is_symlink() or not root.is_dir() for root in roots):
        raise TrustedFreezeError("producer protected-view roots are missing or unsafe")

    mountpoints: list[Path] = []
    for root, materialized in (
        (role_root, role_root / ".materialized"),
        (aggregate_root, aggregate_materialized),
    ):
        for role in reversed(ROLE_NAMES):
            mountpoints.extend((root / "roles" / role, materialized / role))
    for mountpoint in mountpoints:
        if mountpoint.is_symlink() or not mountpoint.is_dir() or not _is_mountpoint(mountpoint):
            raise TrustedFreezeError(f"producer protected-view mount is missing: {mountpoint}")

    for mountpoint in mountpoints:
        try:
            runner(
                ["sudo", "umount", str(mountpoint)],
                check=True,
                capture_output=True,
                text=True,
                timeout=60,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise TrustedFreezeError(
                "cannot remove producer-local protected authority mounts"
            ) from exc

    if any(_is_mountpoint(mountpoint) for mountpoint in mountpoints):
        raise TrustedFreezeError("producer protected-view mounts remain after cleanup")
    shutil.rmtree(role_root)
    shutil.rmtree(aggregate_root)
    shutil.rmtree(aggregate_materialized)
    if any(root.exists() for root in roots):
        raise TrustedFreezeError("producer protected-view paths remain after cleanup")


def hydrate_handoff(
    handoff_path: Path,
    observation_path: Path,
    freeze_evidence_path: Path,
    output_root: Path,
    output_local_view: Path,
    *,
    runner: Any | None = None,
) -> None:
    """Verify a portable handoff and materialize its digest-bound local views."""
    runner = runner or subprocess.run
    handoff, handoff_raw = _read_json_object(handoff_path, "durable handoff")
    observation, observation_raw = _read_json_object(observation_path, "provider observation")
    freeze_evidence, freeze_raw = _read_json_object(freeze_evidence_path, "freeze evidence")
    if "locators" in handoff or "backing_locators" in handoff:
        raise TrustedFreezeError("durable handoff contains producer-local filesystem paths")
    validate_observation(observation)
    document, evidence_raw, evidence_sha256 = load_freeze_evidence(freeze_evidence_path)
    if evidence_raw != freeze_raw:
        raise TrustedFreezeError("freeze evidence changed while it was being loaded")
    if document != freeze_evidence:
        raise TrustedFreezeError("freeze evidence parse is inconsistent")
    if hashlib.sha256(observation_raw).hexdigest() != handoff.get("provider_observation", {}).get(
        "observation_sha256"
    ):
        raise TrustedFreezeError("provider observation bytes do not match durable handoff")
    handoff_sha256 = hashlib.sha256(handoff_raw).hexdigest()
    run = portable_run_identity(observation, freeze_evidence)
    api_token = os.environ.get("GITHUB_TOKEN", "")
    gh_token = os.environ.get("GH_TOKEN", "")
    if not api_token or not gh_token:
        raise TrustedFreezeError("GITHUB_TOKEN and GH_TOKEN are required for portable verification")

    handoff_digest = handoff_sha256
    _verify_subject_attestation(
        str(handoff_path.expanduser().resolve()),
        handoff_digest,
        run_identity=run,
        owner_id=str(OWNER_ID),
        gh_executable=GH_EXECUTABLE,
        runner=runner,
        use_oci_bundle=False,
    )
    provider_adapter = GitHubActionsObservationVerifier(
        observation_path,
        token=api_token,
        run_identity=run,
        runner=runner,
    )
    provider_adapter.verify_target(handoff["target"], handoff["provider_observation"])
    freeze_adapter = GitHubActionsOciFreezeVerifier(
        freeze_evidence_path,
        token=gh_token,
        run_identity=run,
        runner=runner,
    )
    if freeze_adapter.sha256 != evidence_sha256:
        raise TrustedFreezeError("freeze-evidence digest changed during portable verification")
    freeze_adapter.verify_document_digest(handoff)
    for section in ROLE_TO_SECTION.values():
        freeze_adapter.verify(section, handoff[section])

    object_record = freeze_evidence.get("object")
    if not isinstance(object_record, dict):
        raise TrustedFreezeError("freeze evidence does not identify an OCI object")
    manifest_digest = object_record.get("manifest_digest")
    if (
        object_record.get("repository") != OCI_REPOSITORY
        or not isinstance(manifest_digest, str)
        or not OCI_DIGEST.fullmatch(manifest_digest)
    ):
        raise TrustedFreezeError("portable handoff must identify one exact OCI manifest digest")
    object_ref = f"{OCI_REPOSITORY}@{manifest_digest}"
    ghcr_actor = os.environ.get("GHCR_USERNAME") or os.environ.get("GITHUB_ACTOR", "")
    _docker_login(gh_token, actor=ghcr_actor, runner=runner)
    _verify_image_manifest(manifest_digest, runner=runner)

    root = output_root.expanduser().absolute()
    if root.exists() or root.is_symlink():
        raise TrustedFreezeError("reviewer hydration root already exists")
    for parent in reversed(root.parents):
        if parent.is_symlink():
            raise TrustedFreezeError("reviewer hydration root traverses a symbolic link")
    local_path = output_local_view.expanduser().absolute()
    if local_path.exists() or local_path.is_symlink():
        raise TrustedFreezeError("reviewer local-view output already exists")
    root.mkdir(parents=True)
    materialized_root = root / ".materialized"
    protected_root = root / "protected"
    materialized_root.mkdir()
    protected_roles_root = protected_root / "roles"
    protected_roles_root.mkdir(parents=True)
    container = ""
    mounts: list[Path] = []
    complete = False
    locators: dict[str, str] = {}
    backing_locators: dict[str, str] = {}
    try:
        runner(["docker", "pull", object_ref], check=True, capture_output=True, text=True)
        container = runner(
            ["docker", "create", object_ref], check=True, capture_output=True, text=True
        ).stdout.strip()
        if not container:
            raise TrustedFreezeError("Docker did not return the attested OCI container identity")
        for role, section in ROLE_TO_SECTION.items():
            record = freeze_adapter._role_record(role)
            if record.get("path") != f"roles/{role}":
                raise TrustedFreezeError(f"OCI role path does not match its identity: {role}")
            backing = materialized_root / role
            backing.mkdir()
            target = protected_roles_root / role
            target.mkdir()
            runner(
                ["docker", "cp", f"{container}:/roles/{role}/.", str(backing)],
                check=True,
                capture_output=True,
                text=True,
            )
            expected_digest = handoff[section]["inventory_digest"]
            if record["inventory_sha256"] != expected_digest:
                raise TrustedFreezeError(f"OCI role inventory differs from durable handoff: {role}")
            if _inventory_digest(backing) != expected_digest:
                raise TrustedFreezeError(
                    f"pulled OCI role bytes differ from frozen inventory: {role}"
                )
            runner(
                ["sudo", "mount", "--bind", str(backing), str(backing)],
                check=True,
                capture_output=True,
                text=True,
            )
            mounts.append(backing)
            runner(
                ["sudo", "mount", "-o", "remount,bind,ro", str(backing)],
                check=True,
                capture_output=True,
                text=True,
            )
            require_protected_view(backing)
            runner(
                ["sudo", "mount", "--bind", str(backing), str(target)],
                check=True,
                capture_output=True,
                text=True,
            )
            mounts.append(target)
            runner(
                ["sudo", "mount", "-o", "remount,bind,ro", str(target)],
                check=True,
                capture_output=True,
                text=True,
            )
            require_protected_view(target, backing_path=backing)
            if _inventory_digest(target) != expected_digest:
                raise TrustedFreezeError(
                    f"protected OCI role view changed during hydration: {role}"
                )
            locators[role] = str(target)
            backing_locators[role] = str(backing)

        local_view = _portable_local_view(
            handoff=handoff,
            handoff_sha256=handoff_sha256,
            freeze_evidence=freeze_evidence,
            locators=locators,
            backing_locators=backing_locators,
            installed_skill_root=locators["bootstrap_run_image"],
        )
        verify_handoff(
            handoff,
            check_locators=True,
            require_authenticated_provider=True,
            provider_adapter=provider_adapter,
            freeze_adapter=freeze_adapter,
            local_view=local_view,
            handoff_sha256=handoff_sha256,
        )
        if (
            handoff_path.read_bytes() != handoff_raw
            or observation_path.read_bytes() != observation_raw
        ):
            raise TrustedFreezeError(
                "portable handoff inputs changed during reviewer hydration"
            )
        if freeze_evidence_path.read_bytes() != freeze_raw:
            raise TrustedFreezeError("freeze evidence changed during reviewer hydration")
        _write_exclusive(local_path, local_view)
        complete = True
    finally:
        if container:
            runner(["docker", "rm", "--force", container], check=False, capture_output=True)
        if not complete:
            for mount in reversed(mounts):
                runner(["sudo", "umount", str(mount)], check=False, capture_output=True)
            shutil.rmtree(root, ignore_errors=True)


def _verified_observation(
    observation_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], ActionsRunIdentity]:
    try:
        raw = observation_path.read_bytes()
        document = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TrustedFreezeError(
            "authenticated provider observation is missing or malformed"
        ) from exc
    validate_observation(document)
    provider = provider_identity(document, raw)
    verifier = GitHubActionsObservationVerifier(observation_path)
    if not verifier.production_capable:
        raise TrustedFreezeError("provider observation verifier is not production-capable")
    verifier.verify(provider)
    return document, provider, ActionsRunIdentity.from_env()


def _append_github_output(path: Path, values: dict[str, str]) -> None:
    path = path.expanduser().absolute()
    if path.is_symlink() or not path.is_file():
        raise TrustedFreezeError("GitHub output file is missing or unsafe")
    for name, value in values.items():
        if not name.isascii() or not name.replace("_", "").isalnum():
            raise TrustedFreezeError("GitHub output key is invalid")
        if not value or "\n" in value or "\r" in value:
            raise TrustedFreezeError("GitHub output value is invalid")
    raw = "".join(f"{name}={value}\n" for name, value in values.items()).encode()
    descriptor = os.open(path, os.O_WRONLY | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(descriptor, "ab") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def _initialize_from_observation(
    observation_path: Path,
    output_root: Path,
    github_output: Path,
) -> None:
    document, _provider, _run = _verified_observation(observation_path)
    base_sha = require_full_sha(document["pull_request"]["base"]["sha"], "observed base SHA")
    head_sha = require_full_sha(document["pull_request"]["head"]["sha"], "observed head SHA")
    number = document["pull_request"]["number"]
    if not isinstance(number, int) or isinstance(number, bool) or number < 1:
        raise TrustedFreezeError("authenticated PR number is invalid")

    output_root = output_root.expanduser().absolute()
    if output_root.exists() or output_root.is_symlink():
        raise TrustedFreezeError("bootstrap workspace already exists")
    for parent in reversed(output_root.parents):
        if parent.is_symlink():
            raise TrustedFreezeError("bootstrap workspace traverses a symbolic link")
    output_root.mkdir(parents=True)
    object_repository = output_root / "objects.git"
    work_dir = output_root / "work"
    work_dir.mkdir()
    installed_skill = output_root / "installed" / "agent-policy"
    installation_attestation = output_root / "installation-attestation.json"

    env = closed_git_environment()
    subprocess.run(
        ["git", "init", "--bare", "--template=", str(object_repository)],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    subprocess.run(
        [
            "git",
            "--no-replace-objects",
            "-C",
            str(object_repository),
            "fetch",
            "--no-tags",
            "--no-recurse-submodules",
            REPOSITORY_URL,
            base_sha,
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    if (
        resolve_base_tree(Path(shutil.which("git") or "git"), object_repository, base_sha)
        != (document["pull_request"]["base"]["tree"])
    ):
        raise TrustedFreezeError("fetched base tree does not match authenticated GitHub API")

    descriptor_raw = git_run(
        Path(shutil.which("git") or "git"),
        object_repository,
        ["cat-file", "-p", f"{base_sha}:release/skill-installer.json"],
    ).stdout
    try:
        descriptor = json.loads(descriptor_raw)
        installer_spec = descriptor["installer"]
        installer_repository = installer_spec["repository"]
        installer_revision = require_full_sha(installer_spec["revision"], "installer revision")
        installer_path = installer_spec["path"]
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise TrustedFreezeError("trusted base installer authority is malformed") from exc
    if (
        installer_repository != "TakashiSasaki/templates"
        or installer_path != "scripts/install_agent_policy_skill.py"
    ):
        raise TrustedFreezeError("trusted base names an unapproved installer authority")
    subprocess.run(
        [
            "git",
            "--no-replace-objects",
            "-C",
            str(object_repository),
            "fetch",
            "--no-tags",
            "--no-recurse-submodules",
            REPOSITORY_URL,
            installer_revision,
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    installer_path, installer = extract_immutable_installer(
        Path(shutil.which("git") or "git"),
        object_repository,
        base_sha,
        work_dir,
    )
    if installer["revision"] != installer_revision:
        raise TrustedFreezeError("materialized installer revision changed after base validation")
    installed_skill.parent.mkdir(parents=True)
    subprocess.run(
        [
            sys.executable,
            "-I",
            str(installer_path),
            str(installed_skill),
            "--attestation",
            str(installation_attestation),
            "--installer-revision",
            installer_revision,
        ],
        check=True,
        capture_output=True,
        text=True,
        env={
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(output_root),
            "TMPDIR": os.environ.get("RUNNER_TEMP", "/tmp"),
            "PYTHONNOUSERSITE": "1",
        },
    )
    _append_github_output(
        github_output,
        {"target_base": base_sha, "target_head": head_sha, "target_pr": str(number)},
    )


def _protect_aggregate(
    state_path: Path,
    observation_path: Path,
    installation_attestation_path: Path,
    role_evidence_dir: Path,
    manifest_digest: str,
) -> None:
    state, provider, run, _observation = _load_target(
        state_path, observation_path, installation_attestation_path
    )
    _verify_protected_role_evidence(
        state, provider, installation_attestation_path, role_evidence_dir
    )
    _verify_image_manifest(manifest_digest)
    _verify_subject_attestation(
        f"oci://{OCI_REPOSITORY}@{manifest_digest}",
        manifest_digest.removeprefix("sha256:"),
        run_identity=run,
        owner_id=OWNER_ID,
        gh_executable=GH_EXECUTABLE,
        runner=subprocess.run,
        use_oci_bundle=True,
    )

    aggregate_root_raw = os.environ.get("TRUSTED_REVIEW_AGGREGATE_ROOT", "")
    if not aggregate_root_raw:
        raise TrustedFreezeError("TRUSTED_REVIEW_AGGREGATE_ROOT is required")
    aggregate_root = Path(aggregate_root_raw).expanduser().absolute()
    if aggregate_root.exists() or aggregate_root.is_symlink():
        raise TrustedFreezeError("aggregate protected-view destination already exists")
    if aggregate_root.parent.is_symlink():
        raise TrustedFreezeError("aggregate protected-view parent cannot be a symbolic link")
    aggregate_root.mkdir(parents=True)
    source_root = aggregate_root.parent / f".{aggregate_root.name}.materialized"
    if source_root.exists() or source_root.is_symlink():
        raise TrustedFreezeError("aggregate materialization source already exists")
    source_root.mkdir()
    object_ref = f"{OCI_REPOSITORY}@{manifest_digest}"
    container = ""
    mounted: list[Path] = []
    complete = False
    try:
        subprocess.run(["docker", "pull", object_ref], check=True, capture_output=True, text=True)
        container = subprocess.run(
            ["docker", "create", object_ref], check=True, capture_output=True, text=True
        ).stdout.strip()
        if not container:
            raise TrustedFreezeError("Docker did not return the aggregate container identity")
        for role in ROLE_NAMES:
            state_entry = state.get("artifacts", {}).get(role)
            if not isinstance(state_entry, dict):
                raise TrustedFreezeError(f"aggregate role is missing from trusted state: {role}")
            source = source_root / role
            source.mkdir()
            subprocess.run(
                ["docker", "cp", f"{container}:/roles/{role}/.", str(source)],
                check=True,
                capture_output=True,
                text=True,
            )
            if _inventory_digest(source) != state_entry["materialized_digest"]:
                raise TrustedFreezeError(f"pulled aggregate OCI bytes do not match role {role}")
            subprocess.run(
                ["sudo", "mount", "--bind", str(source), str(source)],
                check=True,
                capture_output=True,
                text=True,
            )
            mounted.append(source)
            subprocess.run(
                ["sudo", "mount", "-o", "remount,bind,ro", str(source)],
                check=True,
                capture_output=True,
                text=True,
            )
            require_protected_view(source)
            target = aggregate_root / "roles" / role
            target.parent.mkdir(parents=True, exist_ok=True)
            target.mkdir()
            subprocess.run(
                ["sudo", "mount", "--bind", str(source), str(target)],
                check=True,
                capture_output=True,
                text=True,
            )
            mounted.append(target)
            subprocess.run(
                ["sudo", "mount", "-o", "remount,bind,ro", str(target)],
                check=True,
                capture_output=True,
                text=True,
            )
            require_protected_view(target, backing_path=source)
            if _inventory_digest(target) != state_entry["materialized_digest"]:
                raise TrustedFreezeError(f"aggregate protected role changed: {role}")
            state_entry["locator"] = str(target)
            state_entry["backing_locator"] = str(source)
        save_state(state, state_path)
        complete = True
    finally:
        if container:
            subprocess.run(["docker", "rm", "--force", container], check=False, capture_output=True)
        if not complete:
            for mount in reversed(mounted):
                subprocess.run(["sudo", "umount", str(mount)], check=False, capture_output=True)
            shutil.rmtree(aggregate_root, ignore_errors=True)
            shutil.rmtree(source_root, ignore_errors=True)


def _metadata_digest(metadata_path: Path, github_output: Path) -> None:
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        digest = metadata["containerimage.digest"]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise TrustedFreezeError("BuildKit did not produce an OCI manifest digest") from exc
    if (
        not isinstance(digest, str)
        or not digest.startswith("sha256:")
        or len(digest) != 71
        or any(ch not in "0123456789abcdef" for ch in digest.removeprefix("sha256:"))
    ):
        raise TrustedFreezeError("BuildKit returned a malformed OCI manifest digest")
    _append_github_output(github_output, {"digest": digest})


def _verify_image_manifest(manifest_digest: str, *, runner: Any | None = None) -> None:
    runner = runner or subprocess.run
    if (
        not manifest_digest.startswith("sha256:")
        or len(manifest_digest) != 71
        or any(ch not in "0123456789abcdef" for ch in manifest_digest.removeprefix("sha256:"))
    ):
        raise TrustedFreezeError("OCI manifest digest is missing or malformed")
    result = runner(
        [
            "docker",
            "buildx",
            "imagetools",
            "inspect",
            "--raw",
            f"{OCI_REPOSITORY}@{manifest_digest}",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    try:
        manifest = json.loads(result.stdout)
    except (TypeError, json.JSONDecodeError) as exc:
        raise TrustedFreezeError("GHCR returned a malformed OCI manifest") from exc
    if not isinstance(manifest, dict) or manifest.get("mediaType") != IMAGE_MEDIA_TYPE:
        raise TrustedFreezeError(
            "GHCR object is not the expected single-platform OCI image manifest"
        )


def _verify_attested_file(path: Path) -> None:
    path = path.expanduser().resolve()
    if not path.is_file():
        raise TrustedFreezeError("attested output file is missing")
    run = ActionsRunIdentity.from_env()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    _verify_subject_attestation(
        str(path),
        digest,
        run_identity=run,
        owner_id=OWNER_ID,
        gh_executable=GH_EXECUTABLE,
        runner=subprocess.run,
        use_oci_bundle=False,
    )


def _run_prepare_stage(
    *,
    expected_role: str | None,
    object_repository: Path,
    base_sha: str,
    head_sha: str,
    observation: Path,
    installed_skill: Path,
    installation_attestation: Path,
    work_dir: Path,
    state_file: Path,
    role_freeze_evidence: Path | None,
    freeze_evidence: Path | None,
    output_handoff: Path | None,
    output_packet: Path | None,
) -> None:
    if expected_role is not None and expected_role not in ROLE_NAMES:
        raise TrustedFreezeError("unsupported expected freeze stage")
    command = [
        sys.executable,
        "-I",
        str(Path(__file__).with_name("prepare_trusted_review_handoff.py")),
        "prepare",
        "--object-repository",
        str(object_repository),
        "--base",
        require_full_sha(base_sha, "expected base SHA"),
        "--head",
        require_full_sha(head_sha, "expected head SHA"),
        "--provider-observation",
        str(observation),
        "--installed-skill",
        str(installed_skill),
        "--installation-attestation",
        str(installation_attestation),
        "--work-dir",
        str(work_dir),
        "--state-file",
        str(state_file),
        "--require-authenticated-provider",
    ]
    if role_freeze_evidence is not None:
        command.extend(["--role-freeze-evidence", str(role_freeze_evidence)])
    if freeze_evidence is not None:
        command.extend(["--freeze-evidence", str(freeze_evidence)])
    if output_handoff is not None:
        command.extend(["--output-handoff", str(output_handoff)])
    if output_packet is not None:
        command.extend(["--output-packet", str(output_packet)])
    result = subprocess.run(command, capture_output=True, text=True)
    if expected_role is None:
        if result.returncode != 0 or "AUTHENTICATED_BOOTSTRAP_HANDOFF_READY" not in result.stdout:
            raise TrustedFreezeError(
                "trusted bootstrap did not reach AUTHENTICATED_BOOTSTRAP_HANDOFF_READY\n"
                f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            )
        return
    if result.returncode != 2 or "BOOTSTRAP_FREEZE_CAPABILITY_BLOCKED" not in result.stdout:
        raise TrustedFreezeError(
            f"bootstrap did not stop at the expected {expected_role} freeze boundary\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    try:
        payload = result.stdout[result.stdout.index("{") :]
        blocked = json.loads(payload)
        actual = blocked["pending_artifact"]["target"]
    except (ValueError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise TrustedFreezeError("bootstrap freeze-blocked result is malformed") from exc
    if actual != expected_role:
        raise TrustedFreezeError(f"bootstrap blocked on {actual!r}; expected {expected_role!r}")


def _load_target(
    state_path: Path,
    observation_path: Path,
    installation_attestation_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], ActionsRunIdentity, dict[str, Any]]:
    state = load_and_verify_state(state_path)
    try:
        observation_raw = observation_path.read_bytes()
        observation = json.loads(observation_raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TrustedFreezeError(
            "authenticated provider observation is missing or malformed"
        ) from exc
    validate_observation(observation)
    observed_provider = provider_identity(observation, observation_raw)
    verifier = GitHubActionsObservationVerifier(observation_path)
    provider = state.get("provider")
    if not isinstance(provider, dict):
        raise TrustedFreezeError("bootstrap state has no provider identity")
    verifier.verify(provider)
    if _target_record(provider) != _target_record(observed_provider):
        raise TrustedFreezeError("bootstrap state does not match the authenticated observation")
    if not installation_attestation_path.is_file():
        raise TrustedFreezeError("installation attestation is unavailable")
    return state, provider, ActionsRunIdentity.from_env(), observation


def _target_record(provider: dict[str, Any]) -> dict[str, Any]:
    repo = provider["repository"]
    pull = provider["pull_request"]
    observation = provider["provider_observation"]
    return {
        "repository_id": repo["id"],
        "repository_name": repo["name_with_owner"],
        "pull_request_id": pull["id"],
        "pull_request_node_id": pull["node_id"],
        "pull_request_number": pull["number"],
        "base_ref_name": pull["base_ref_name"],
        "base_sha": pull["base_ref_oid"],
        "base_tree": pull["base_tree"],
        "head_sha": pull["head_ref_oid"],
        "head_tree": pull["head_tree"],
        "observation_sha256": observation["observation_sha256"],
    }


def _attestation_record(run: ActionsRunIdentity) -> dict[str, Any]:
    try:
        from scripts.trusted_review_actions import OIDC_ISSUER, OWNER_ID
    except ImportError:
        from trusted_review_actions import OIDC_ISSUER, OWNER_ID

    return {
        "issuer": OIDC_ISSUER,
        "repository_id": run.repository_id,
        "owner_id": OWNER_ID,
        "workflow_ref": run.workflow_ref,
        "workflow_sha": run.workflow_sha,
        "source_sha": run.source_sha,
        "run_id": run.run_id,
        "run_attempt": run.run_attempt,
        "event": run.event,
        "actor_id": run.actor_id,
        "actor_login": run.actor,
        "job": run.job,
    }


def _write_exclusive(path: Path, value: dict[str, Any]) -> None:
    path = path.expanduser().absolute()
    if path.exists() or path.is_symlink():
        raise TrustedFreezeError(f"freeze evidence output already exists: {path}")
    for parent in reversed(path.parents):
        if parent.is_symlink():
            raise TrustedFreezeError("freeze evidence output traverses a symbolic link")
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    ).encode()
    descriptor = os.open(
        path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600
    )
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def _role_evidence(
    state: dict[str, Any],
    provider: dict[str, Any],
    run: ActionsRunIdentity,
    role: str,
    manifest_digest: str,
    installation_attestation_path: Path,
) -> dict[str, Any]:
    if role not in ROLE_NAMES:
        raise TrustedFreezeError("unsupported role freeze target")
    if not manifest_digest.startswith("sha256:") or len(manifest_digest) != 71:
        raise TrustedFreezeError("OCI manifest digest is missing or malformed")
    role_state = state.get("artifacts", {}).get(role)
    if not isinstance(role_state, dict):
        raise TrustedFreezeError("requested role has not been materialized")
    path = Path(role_state["locator"])
    inventory = _inventory_digest(path)
    if inventory != role_state.get("materialized_digest"):
        raise TrustedFreezeError("materialized role changed before image publication")
    identity = expected_freeze_role_identity(
        role,
        state,
        installation_attestation_path=installation_attestation_path,
    )
    return {
        "schema_version": 1,
        "provider": "github-actions-ghcr-role",
        "object": {
            "repository": OCI_REPOSITORY,
            "manifest_digest": manifest_digest,
            "media_type": IMAGE_MEDIA_TYPE,
        },
        "attestation": _attestation_record(run),
        "target": _target_record(provider),
        "role": {
            "name": role,
            "path": f"roles/{role}",
            "inventory_sha256": inventory,
            "identity": identity,
        },
    }


def _stage_role_context(state: dict[str, Any], role: str, output: Path) -> None:
    if role not in ROLE_NAMES:
        raise TrustedFreezeError("unsupported role image target")
    entry = state.get("artifacts", {}).get(role)
    if not isinstance(entry, dict):
        raise TrustedFreezeError("requested role has not been materialized")
    source = Path(entry["locator"])
    if _inventory_digest(source) != entry["materialized_digest"]:
        raise TrustedFreezeError("role source changed before OCI context creation")
    output = output.expanduser().absolute()
    if output.exists() or output.is_symlink():
        raise TrustedFreezeError("OCI context destination already exists")
    payload = output / "payload"
    payload.mkdir(parents=True)
    shutil.copytree(source, payload / "role", dirs_exist_ok=True, symlinks=True)
    if _inventory_digest(payload / "role") != entry["materialized_digest"]:
        raise TrustedFreezeError("OCI context bytes differ from the materialized role")
    (output / "Dockerfile").write_text(
        f"FROM scratch\nCOPY payload/role/ /roles/{role}/\n",
        encoding="utf-8",
    )


def _stage_aggregate_context(
    state: dict[str, Any],
    provider: dict[str, Any],
    installation_attestation_path: Path,
    role_evidence_dir: Path,
    output: Path,
) -> None:
    _verify_protected_role_evidence(
        state,
        provider,
        installation_attestation_path,
        role_evidence_dir,
    )
    output = output.expanduser().absolute()
    if output.exists() or output.is_symlink():
        raise TrustedFreezeError("aggregate OCI context destination already exists")
    payload = output / "payload" / "roles"
    payload.mkdir(parents=True)
    protected_root_raw = os.environ.get("TRUSTED_REVIEW_PROTECTED_ROOT", "")
    if not protected_root_raw:
        raise TrustedFreezeError("TRUSTED_REVIEW_PROTECTED_ROOT is required")
    protected_root = Path(protected_root_raw).expanduser().absolute()
    docker_lines = ["FROM scratch"]
    for role in ROLE_NAMES:
        entry = state.get("artifacts", {}).get(role)
        if not isinstance(entry, dict):
            raise TrustedFreezeError("aggregate freeze requires all four materialized roles")
        source = protected_root / "roles" / role
        require_protected_view(
            source,
            backing_path=protected_root / ".materialized" / role,
        )
        if _inventory_digest(source) != entry["materialized_digest"]:
            raise TrustedFreezeError(f"protected role inventory changed: {role}")
        shutil.copytree(source, payload / role, symlinks=True)
        if _inventory_digest(payload / role) != entry["materialized_digest"]:
            raise TrustedFreezeError(f"aggregate OCI context changed the role bytes: {role}")
        docker_lines.append(f"COPY payload/roles/{role}/ /roles/{role}/")
    (output / "Dockerfile").write_text("\n".join(docker_lines) + "\n", encoding="utf-8")


def _verify_protected_role_evidence(
    state: dict[str, Any],
    provider: dict[str, Any],
    installation_attestation_path: Path,
    role_evidence_dir: Path,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    protected_root_raw = os.environ.get("TRUSTED_REVIEW_PROTECTED_ROOT", "")
    if not protected_root_raw:
        raise TrustedFreezeError("TRUSTED_REVIEW_PROTECTED_ROOT is required")
    protected_root = Path(protected_root_raw).expanduser()
    for role in ROLE_NAMES:
        entry = state.get("artifacts", {}).get(role)
        if not isinstance(entry, dict):
            raise TrustedFreezeError("role evidence requires all four materialized artifacts")
        evidence_path = role_evidence_dir / f"{role}.json"
        adapter = GitHubActionsRoleFreezeVerifier(evidence_path, provider)
        mechanism = f"{adapter.name}:{adapter.document['object']['manifest_digest']}"
        freeze_evidence = FreezeEvidence(
            boundary_type=FreezeBoundaryType.DEPLOYMENT_ESTABLISHED,
            mechanism=mechanism,
            evidence_status="authenticated",
            attestation_sha256=adapter.sha256,
        )
        protected = adapter.verify_freeze(
            role,
            Path(entry["locator"]),
            freeze_evidence,
            expected_inventory_sha256=entry["materialized_digest"],
            backing_path=protected_root / ".materialized" / role,
            expected_identity=expected_freeze_role_identity(
                role,
                state,
                installation_attestation_path=installation_attestation_path,
            ),
        )
        if protected != (protected_root / "roles" / role).resolve():
            raise TrustedFreezeError("role evidence did not resolve to its protected mount")
        records.append(
            {
                "role": role,
                "path": f"roles/{role}",
                "inventory_sha256": entry["materialized_digest"],
                "identity": expected_freeze_role_identity(
                    role,
                    state,
                    installation_attestation_path=installation_attestation_path,
                ),
            }
        )
    return records


def _aggregate_evidence(
    state: dict[str, Any],
    provider: dict[str, Any],
    run: ActionsRunIdentity,
    manifest_digest: str,
    installation_attestation_path: Path,
    role_evidence_dir: Path,
) -> dict[str, Any]:
    roles = _verify_protected_role_evidence(
        state,
        provider,
        installation_attestation_path,
        role_evidence_dir,
    )
    return {
        "schema_version": 1,
        "provider": "github-actions-ghcr",
        "object": {
            "registry": "ghcr.io",
            "repository": OCI_REPOSITORY,
            "manifest_digest": manifest_digest,
            "media_type": IMAGE_MEDIA_TYPE,
        },
        "attestation": {
            "digest": manifest_digest,
            **_attestation_record(run),
        },
        "target": _target_record(provider),
        "roles": roles,
        "post_freeze_verification": {
            "result": "PASS",
            "before_use": "PASS",
            "after_use": "PASS",
            "verifier": "github-actions-ghcr-oci-v1",
        },
    }


def _protect_role(
    state_path: Path,
    observation_path: Path,
    installation_attestation_path: Path,
    evidence_path: Path,
) -> None:
    state, provider, _run, _observation = _load_target(
        state_path, observation_path, installation_attestation_path
    )
    document, _raw_evidence, _evidence_sha = load_role_freeze_evidence(evidence_path)
    role = document["role"]["name"]
    entry = state.get("artifacts", {}).get(role)
    if not isinstance(entry, dict):
        raise TrustedFreezeError("role evidence does not match a materialized state artifact")
    object_ref = f"{OCI_REPOSITORY}@{document['object']['manifest_digest']}"
    protected_root_raw = os.environ.get("TRUSTED_REVIEW_PROTECTED_ROOT", "")
    if not protected_root_raw:
        raise TrustedFreezeError("TRUSTED_REVIEW_PROTECTED_ROOT is required")
    protected = Path(protected_root_raw).expanduser().absolute() / "roles" / role
    protected_root = Path(protected_root_raw).expanduser().absolute()
    if protected_root.is_symlink():
        raise TrustedFreezeError("protected role root cannot be a symbolic link")
    protected_root.mkdir(parents=True, exist_ok=True)
    source_root = protected_root / ".materialized"
    if source_root.is_symlink():
        raise TrustedFreezeError("role source root cannot be a symbolic link")
    source_root.mkdir(parents=True, exist_ok=True)
    source = source_root / role
    if source.exists() or source.is_symlink():
        raise TrustedFreezeError("role materialization source already exists")
    source.mkdir()
    created = ""
    mounted: list[Path] = []
    complete = False
    try:
        subprocess.run(["docker", "pull", object_ref], check=True, capture_output=True, text=True)
        created = subprocess.run(
            ["docker", "create", object_ref], check=True, capture_output=True, text=True
        ).stdout.strip()
        if not created:
            raise TrustedFreezeError("Docker did not return a container identity")
        subprocess.run(
            ["docker", "cp", f"{created}:/roles/{role}/.", str(source)],
            check=True,
            capture_output=True,
            text=True,
        )
        expected_inventory = entry["materialized_digest"]
        if _inventory_digest(source) != expected_inventory:
            raise TrustedFreezeError("pulled immutable role bytes do not match staged state")
        if protected.exists() or protected.is_symlink():
            raise TrustedFreezeError("protected role mount destination already exists")
        if protected.parent.is_symlink():
            raise TrustedFreezeError("protected role mount parent cannot be a symbolic link")
        protected.parent.mkdir(parents=True, exist_ok=True)
        protected.mkdir()
        subprocess.run(
            ["sudo", "mount", "--bind", str(source), str(source)],
            check=True,
            capture_output=True,
            text=True,
        )
        mounted.append(source)
        subprocess.run(
            ["sudo", "mount", "-o", "remount,bind,ro", str(source)],
            check=True,
            capture_output=True,
            text=True,
        )
        require_protected_view(source)
        subprocess.run(
            ["sudo", "mount", "--bind", str(source), str(protected)],
            check=True,
            capture_output=True,
            text=True,
        )
        mounted.append(protected)
        subprocess.run(
            ["sudo", "mount", "-o", "remount,bind,ro", str(protected)],
            check=True,
            capture_output=True,
            text=True,
        )
        adapter = GitHubActionsRoleFreezeVerifier(evidence_path, provider)
        if not adapter.production_capable:
            raise TrustedFreezeError("role freeze verifier is not production-capable")
        evidence = FreezeEvidence(
            boundary_type=FreezeBoundaryType.DEPLOYMENT_ESTABLISHED,
            mechanism=f"{adapter.name}:{document['object']['manifest_digest']}",
            evidence_status="authenticated",
            attestation_sha256=adapter.sha256,
        )
        adapter.verify_freeze(
            role,
            Path(entry["locator"]),
            evidence,
            expected_inventory_sha256=expected_inventory,
            backing_path=source,
            expected_identity=expected_freeze_role_identity(
                role,
                state,
                installation_attestation_path=installation_attestation_path,
            ),
        )
        complete = True
    finally:
        if created:
            subprocess.run(["docker", "rm", "--force", created], check=False, capture_output=True)
        if not complete:
            for mount in reversed(mounted):
                subprocess.run(["sudo", "umount", str(mount)], check=False, capture_output=True)
            if protected.exists() and not protected.is_mount():
                protected.rmdir()
        if not complete:
            shutil.rmtree(source, ignore_errors=True)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    initialize = sub.add_parser(
        "initialize", help="Verify the observation and bootstrap from its exact base."
    )
    initialize.add_argument("--observation", type=Path, required=True)
    initialize.add_argument("--output-root", type=Path, required=True)
    initialize.add_argument("--github-output", type=Path, required=True)
    sub.add_parser("login-ghcr", help="Authenticate Docker to GHCR without exposing the token.")
    metadata = sub.add_parser(
        "metadata-digest", help="Validate BuildKit metadata and emit its digest."
    )
    metadata.add_argument("--metadata", type=Path, required=True)
    metadata.add_argument("--github-output", type=Path, required=True)
    manifest = sub.add_parser("verify-manifest", help="Require an OCI image manifest by digest.")
    manifest.add_argument("--manifest-digest", required=True)
    verify_file = sub.add_parser(
        "verify-attested-file", help="Verify one run-attested output file."
    )
    verify_file.add_argument("--path", type=Path, required=True)
    prepare_stage = sub.add_parser(
        "prepare-stage", help="Run one authenticated bootstrap state transition."
    )
    prepare_stage.add_argument("--expect-role", choices=ROLE_NAMES)
    prepare_stage.add_argument("--object-repository", type=Path, required=True)
    prepare_stage.add_argument("--base", required=True)
    prepare_stage.add_argument("--head", required=True)
    prepare_stage.add_argument("--observation", type=Path, required=True)
    prepare_stage.add_argument("--installed-skill", type=Path, required=True)
    prepare_stage.add_argument("--installation-attestation", type=Path, required=True)
    prepare_stage.add_argument("--work-dir", type=Path, required=True)
    prepare_stage.add_argument("--state-file", type=Path, required=True)
    prepare_stage.add_argument("--role-freeze-evidence", type=Path)
    prepare_stage.add_argument("--freeze-evidence", type=Path)
    prepare_stage.add_argument("--output-handoff", type=Path)
    prepare_stage.add_argument("--output-packet", type=Path)
    role_context = sub.add_parser("stage-role-context")
    role_context.add_argument("--state", type=Path, required=True)
    role_context.add_argument("--role", choices=ROLE_NAMES, required=True)
    role_context.add_argument("--output", type=Path, required=True)
    role_evidence = sub.add_parser("write-role-evidence")
    role_evidence.add_argument("--state", type=Path, required=True)
    role_evidence.add_argument("--observation", type=Path, required=True)
    role_evidence.add_argument("--installation-attestation", type=Path, required=True)
    role_evidence.add_argument("--role", choices=ROLE_NAMES, required=True)
    role_evidence.add_argument("--manifest-digest", required=True)
    role_evidence.add_argument("--output", type=Path, required=True)
    protect = sub.add_parser("protect-role")
    protect.add_argument("--state", type=Path, required=True)
    protect.add_argument("--observation", type=Path, required=True)
    protect.add_argument("--installation-attestation", type=Path, required=True)
    protect.add_argument("--evidence", type=Path, required=True)
    protect_aggregate = sub.add_parser("protect-aggregate")
    protect_aggregate.add_argument("--state", type=Path, required=True)
    protect_aggregate.add_argument("--observation", type=Path, required=True)
    protect_aggregate.add_argument("--installation-attestation", type=Path, required=True)
    protect_aggregate.add_argument("--role-evidence-dir", type=Path, required=True)
    protect_aggregate.add_argument("--manifest-digest", required=True)
    aggregate_context = sub.add_parser("stage-aggregate-context")
    aggregate_context.add_argument("--state", type=Path, required=True)
    aggregate_context.add_argument("--observation", type=Path, required=True)
    aggregate_context.add_argument("--installation-attestation", type=Path, required=True)
    aggregate_context.add_argument("--role-evidence-dir", type=Path, required=True)
    aggregate_context.add_argument("--output", type=Path, required=True)
    aggregate_evidence = sub.add_parser("write-aggregate-evidence")
    aggregate_evidence.add_argument("--state", type=Path, required=True)
    aggregate_evidence.add_argument("--observation", type=Path, required=True)
    aggregate_evidence.add_argument("--installation-attestation", type=Path, required=True)
    aggregate_evidence.add_argument("--role-evidence-dir", type=Path, required=True)
    aggregate_evidence.add_argument("--manifest-digest", required=True)
    aggregate_evidence.add_argument("--output", type=Path, required=True)
    cleanup = sub.add_parser(
        "cleanup-producer-views",
        help="Unmount and remove producer-local paths before portable handoff hydration.",
    )
    cleanup.add_argument("--role-protected-root", type=Path, required=True)
    cleanup.add_argument("--aggregate-protected-root", type=Path, required=True)
    hydrate = sub.add_parser(
        "hydrate-handoff",
        help="Verify a durable handoff and hydrate fresh read-only reviewer role views.",
    )
    hydrate.add_argument("--handoff", type=Path, required=True)
    hydrate.add_argument("--provider-observation", type=Path, required=True)
    hydrate.add_argument("--freeze-evidence", type=Path, required=True)
    hydrate.add_argument("--output-root", type=Path, required=True)
    hydrate.add_argument("--output-local-view", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    try:
        args = parse_args(argv)
        if args.command == "initialize":
            _initialize_from_observation(args.observation, args.output_root, args.github_output)
        elif args.command == "login-ghcr":
            token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
            actor = os.environ.get("GHCR_USERNAME") or os.environ.get("GITHUB_ACTOR", "")
            _docker_login(token, actor=actor, runner=subprocess.run)
        elif args.command == "cleanup-producer-views":
            cleanup_producer_views(args.role_protected_root, args.aggregate_protected_root)
        elif args.command == "metadata-digest":
            _metadata_digest(args.metadata, args.github_output)
        elif args.command == "verify-manifest":
            _verify_image_manifest(args.manifest_digest)
        elif args.command == "verify-attested-file":
            _verify_attested_file(args.path)
        elif args.command == "prepare-stage":
            _run_prepare_stage(
                expected_role=args.expect_role,
                object_repository=args.object_repository,
                base_sha=args.base,
                head_sha=args.head,
                observation=args.observation,
                installed_skill=args.installed_skill,
                installation_attestation=args.installation_attestation,
                work_dir=args.work_dir,
                state_file=args.state_file,
                role_freeze_evidence=args.role_freeze_evidence,
                freeze_evidence=args.freeze_evidence,
                output_handoff=args.output_handoff,
                output_packet=args.output_packet,
            )
        elif args.command == "stage-role-context":
            _stage_role_context(load_and_verify_state(args.state), args.role, args.output)
        elif args.command == "write-role-evidence":
            state, provider, run, _ = _load_target(
                args.state, args.observation, args.installation_attestation
            )
            _write_exclusive(
                args.output,
                _role_evidence(
                    state,
                    provider,
                    run,
                    args.role,
                    args.manifest_digest,
                    args.installation_attestation,
                ),
            )
        elif args.command == "protect-role":
            _protect_role(
                args.state,
                args.observation,
                args.installation_attestation,
                args.evidence,
            )
        elif args.command == "protect-aggregate":
            _protect_aggregate(
                args.state,
                args.observation,
                args.installation_attestation,
                args.role_evidence_dir,
                args.manifest_digest,
            )
        elif args.command == "stage-aggregate-context":
            state, provider, _run, _observation = _load_target(
                args.state, args.observation, args.installation_attestation
            )
            _stage_aggregate_context(
                state,
                provider,
                args.installation_attestation,
                args.role_evidence_dir,
                args.output,
            )
        elif args.command == "write-aggregate-evidence":
            state, provider, run, _ = _load_target(
                args.state, args.observation, args.installation_attestation
            )
            evidence = _aggregate_evidence(
                state,
                provider,
                run,
                args.manifest_digest,
                args.installation_attestation,
                args.role_evidence_dir,
            )
            _write_exclusive(args.output, evidence)
        elif args.command == "hydrate-handoff":
            hydrate_handoff(
                args.handoff,
                args.provider_observation,
                args.freeze_evidence,
                args.output_root,
                args.output_local_view,
            )
        print("TRUSTED_REVIEW_FREEZE_PROVIDER_OK")
        return 0
    except (OSError, ValueError, subprocess.SubprocessError, KeyError) as exc:
        print(f"trusted review freeze provider error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
