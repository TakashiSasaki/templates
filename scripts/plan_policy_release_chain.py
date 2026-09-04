from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, ValidationError

ROOT = Path(__file__).resolve().parents[1]
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
REPOSITORY = "TakashiSasaki/templates"
INSTALLER_DESCRIPTOR = "release/skill-installer.json"
TOOLCHAIN_DESCRIPTOR = "release/toolchain.json"
RUNTIME_LOCK = "requirements-runtime.lock"
TOOLCHAIN_SCHEMA = "schemas/toolchain-release.schema.json"
INSTALLER_SCHEMA = "schemas/skill-installer-release.schema.json"
SKILL_RUNTIME_MANIFEST = "skills/agent-policy/runtime-manifest.json"
INSTALLER_SCRIPT = "scripts/install_agent_policy_skill.py"
RevisionReader = Callable[[str, str], bytes | None]

DIRECT_SURFACES: dict[str, tuple[str, ...]] = {
    "T": (
        TOOLCHAIN_DESCRIPTOR,
        SKILL_RUNTIME_MANIFEST,
    ),
    "S": (
        INSTALLER_SCRIPT,
        "scripts/smoke_test_agent_policy_installer_candidate.py",
        "tests/test_installer_candidate_smoke.py",
        "tests/test_remote_skill_installer.py",
    ),
    "I": (
        INSTALLER_DESCRIPTOR,
        "README.md",
        "docs/bootstrap.md",
        "docs/getting-started.md",
        "tests/test_skill_installer_publication.py",
        "translations/ja/docs/bootstrap.md",
        "translations/ja/docs/getting-started.md",
    ),
}

S_PUBLICATION_SURFACES = DIRECT_SURFACES["I"]

REGENERATION_SURFACES: dict[str, tuple[str, ...]] = {
    "T-self-host-projection": (
        ".agent-policy.lock",
        ".agents/skills/orchestrate-repository-change/",
        ".agents/skills/pr-review/",
        ".github/workflows/check-agent-policy.yml",
        ".review-authority/review-policy.md",
        "AGENTS.md",
    ),
    "I-policy-publication": ("translations/manifest.json",),
    "policy-to-site-projection": (
        "publication-sources.json",
        "agent.json",
        "assets/agent.json",
        "tests/test_policy_concepts_promotion.py",
    ),
}

VALIDATION_BY_STAGE: dict[str, tuple[str, ...]] = {
    "T-self-host-input": (
        "validate .agent-policy.yml syntax/schema and full-SHA toolchain pin",
    ),
    "T-self-host-projection": (
        "tests/test_policy_self_hosting.py",
        "tests/test_repository_change_orchestration_skill.py",
    ),
    "T-promotion": (
        "tests/test_immutable_toolchain_identity.py",
        "tests/test_release_lifecycle.py",
        "scripts/verify-release-state.py",
        SKILL_RUNTIME_MANIFEST,
    ),
    "S-installer-candidate": (
        "tests/test_installer_candidate_smoke.py",
        "tests/test_remote_skill_installer.py",
        "scripts/smoke_test_agent_policy_installer_candidate.py",
    ),
    "I-policy-publication": (
        "tests/test_skill_installer_publication.py",
        "scripts/verify_skill_installer_release.py",
    ),
    "policy-to-site-projection": (
        "Site-owned compatibility/publication validation on the site authority",
    ),
}


def _repository_relative(relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise ValueError(f"unsafe repository-relative path: {relative!r}")
    return path


def _repository_file(root: Path, relative: str) -> Path:
    root = root.resolve()
    relative_path = _repository_relative(relative)
    current = root
    for part in relative_path.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"repository input path must not contain symlinks: {relative}")
    resolved = current.resolve(strict=True)
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"repository input escaped repository root: {relative}")
    if not resolved.is_file():
        raise ValueError(f"expected regular repository file: {relative}")
    return resolved


def _load_json(root: Path, relative: str) -> dict[str, Any]:
    path = _repository_file(root, relative)
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {relative}")
    return value


def _load_validated_json(
    root: Path,
    relative: str,
    schema_relative: str,
) -> dict[str, Any]:
    value = _load_json(root, relative)
    schema = _load_json(root, schema_relative)
    try:
        Draft202012Validator(schema).validate(value)
    except ValidationError as exc:
        location = ".".join(str(part) for part in exc.absolute_path) or "<root>"
        raise ValueError(
            f"{relative} failed schema validation at {location}: {exc.message}"
        ) from exc
    return value


def _require_full_sha(name: str, value: object) -> str:
    if not isinstance(value, str) or FULL_SHA.fullmatch(value) is None:
        raise ValueError(
            f"{name} must be a lowercase full 40-character SHA string: {value!r}"
        )
    return value


def _require_sha256(value: object) -> str:
    if not isinstance(value, str) or SHA256.fullmatch(value) is None:
        raise ValueError("runtime lock digest must be a lowercase 64-character SHA-256 string")
    return value


def _git_revision_reader(root: Path) -> RevisionReader:
    repository_root = root.resolve()

    def read(revision: str, relative: str) -> bytes | None:
        _require_full_sha("revision", revision)
        relative_path = _repository_relative(relative).as_posix()
        object_type = subprocess.run(
            ["git", "-C", str(repository_root), "cat-file", "-t", revision],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if object_type.returncode != 0 or object_type.stdout.strip() != b"commit":
            return None
        result = subprocess.run(
            ["git", "-C", str(repository_root), "show", f"{revision}:{relative_path}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return result.stdout if result.returncode == 0 else None

    return read


def _current_runtime_lock_evidence(root: Path) -> dict[str, Any]:
    lock = _repository_file(root, RUNTIME_LOCK)
    return {
        "available": True,
        "verified": True,
        "sha256": hashlib.sha256(lock.read_bytes()).hexdigest(),
        "source": "current-repository-lock",
    }


def runtime_lock_evidence(
    root: Path,
    *,
    current_toolchain: str,
    requested_toolchain: str,
    supplied_digest: str | None,
    revision_reader: RevisionReader,
) -> dict[str, Any]:
    if requested_toolchain == current_toolchain:
        current = _current_runtime_lock_evidence(root)
        if supplied_digest is not None:
            supplied = _require_sha256(supplied_digest)
            if supplied != current["sha256"]:
                raise ValueError(
                    "supplied runtime lock digest does not match the current "
                    "toolchain lock"
                )
        return current

    candidate_lock = revision_reader(requested_toolchain, RUNTIME_LOCK)
    if candidate_lock is None:
        result: dict[str, Any] = {
            "available": False,
            "verified": False,
            "status": "requested toolchain runtime lock unavailable / awaiting verification",
            "revision": requested_toolchain,
        }
        if supplied_digest is not None:
            result["supplied_sha256"] = _require_sha256(supplied_digest)
        return result

    actual = hashlib.sha256(candidate_lock).hexdigest()
    if supplied_digest is not None and _require_sha256(supplied_digest) != actual:
        raise ValueError(
            "supplied runtime lock digest does not match the requested "
            "toolchain revision"
        )
    return {
        "available": True,
        "verified": True,
        "sha256": actual,
        "source": "verified-requested-toolchain-git-object",
        "revision": requested_toolchain,
        "path": RUNTIME_LOCK,
    }


def current_identities(root: Path = ROOT) -> dict[str, str]:
    toolchain = _load_validated_json(root, TOOLCHAIN_DESCRIPTOR, TOOLCHAIN_SCHEMA)
    installer = _load_validated_json(root, INSTALLER_DESCRIPTOR, INSTALLER_SCHEMA)
    return {
        "T": _require_full_sha("T", toolchain["toolchain"]["revision"]),
        "S": _require_full_sha("S", installer["skill_source"]["revision"]),
        "I": _require_full_sha("I", installer["installer"]["revision"]),
    }


def _surface_inventory(
    root: Path,
    identity: str,
    current: str,
    requested: str,
    *,
    paths: tuple[str, ...] | None = None,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for relative in paths or DIRECT_SURFACES[identity]:
        text = _repository_file(root, relative).read_text(encoding="utf-8")
        occurrences = text.count(current)
        records.append(
            {
                "identity": identity,
                "path": relative,
                "current_identity_occurrences": occurrences,
                "expected_replacements": occurrences if requested != current else 0,
                "requires_change": requested != current and occurrences > 0,
            }
        )
    return records


def _requested_identity(
    name: str,
    supplied: str | None,
    current: dict[str, str],
) -> str:
    if supplied is None:
        return current[name]
    return _require_full_sha(name, supplied)


def _verify_skill_source(
    revision_reader: RevisionReader,
    *,
    revision: str,
    toolchain_revision: str,
    runtime_lock: dict[str, Any],
) -> dict[str, Any]:
    raw = revision_reader(revision, SKILL_RUNTIME_MANIFEST)
    if raw is None:
        return {"verified": False, "reason": "skill-source commit/manifest unavailable"}
    try:
        manifest = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {"verified": False, "reason": "skill-source runtime manifest is invalid"}
    expected_toolchain = {"repository": REPOSITORY, "revision": toolchain_revision}
    if not isinstance(manifest, dict) or manifest.get("toolchain") != expected_toolchain:
        return {
            "verified": False,
            "reason": "skill-source manifest is not bound to requested T",
        }
    lock_record = manifest.get("runtime_lock")
    if runtime_lock.get("verified"):
        expected_lock = {"path": RUNTIME_LOCK, "sha256": runtime_lock["sha256"]}
        if lock_record != expected_lock:
            return {
                "verified": False,
                "reason": "skill-source manifest runtime lock does not match T",
            }
    return {
        "verified": True,
        "revision": revision,
        "path": SKILL_RUNTIME_MANIFEST,
        "toolchain_revision": toolchain_revision,
    }


def _extract_assignment(text: str, name: str) -> str | None:
    match = re.search(
        rf'^\s*{re.escape(name)}\s*=\s*"([^"]+)"\s*$',
        text,
        re.MULTILINE,
    )
    return match.group(1) if match else None


def _verify_installer(
    revision_reader: RevisionReader,
    *,
    revision: str,
    skill_source_revision: str,
) -> dict[str, Any]:
    raw = revision_reader(revision, INSTALLER_SCRIPT)
    if raw is None:
        return {"verified": False, "reason": "installer commit/script unavailable"}
    try:
        script = raw.decode("utf-8")
    except UnicodeDecodeError:
        return {"verified": False, "reason": "installer script is not UTF-8"}
    expected = {
        "TOOLCHAIN_REPOSITORY": REPOSITORY,
        "INSTALLER_PATH": INSTALLER_SCRIPT,
        "SKILL_SOURCE_REVISION": skill_source_revision,
        "SKILL_SOURCE_PATH": "skills/agent-policy",
    }
    actual = {name: _extract_assignment(script, name) for name in expected}
    if actual != expected:
        return {
            "verified": False,
            "reason": "installer script is not bound to requested S",
        }
    return {
        "verified": True,
        "revision": revision,
        "path": INSTALLER_SCRIPT,
        "skill_source_revision": skill_source_revision,
    }


def build_plan(
    root: Path = ROOT,
    *,
    toolchain_revision: str | None = None,
    skill_source_revision: str | None = None,
    installer_revision: str | None = None,
    runtime_lock_sha256: str | None = None,
    revision_reader: RevisionReader | None = None,
) -> dict[str, Any]:
    current = current_identities(root)
    requested = {
        "T": _requested_identity("T", toolchain_revision, current),
        "S": _requested_identity("S", skill_source_revision, current),
        "I": _requested_identity("I", installer_revision, current),
    }
    changed = {
        name: requested[name] != current[name]
        for name in ("T", "S", "I")
    }
    reader = revision_reader or _git_revision_reader(root)

    runtime_lock = runtime_lock_evidence(
        root,
        current_toolchain=current["T"],
        requested_toolchain=requested["T"],
        supplied_digest=runtime_lock_sha256,
        revision_reader=reader,
    )
    verification: dict[str, dict[str, Any]] = {
        "T": (
            {
                "verified": bool(runtime_lock.get("verified")),
                "revision": requested["T"],
                "evidence": "runtime-lock-at-requested-revision",
            }
            if changed["T"]
            else {
                "verified": True,
                "revision": current["T"],
                "evidence": "published-current",
            }
        ),
        "S": {
            "verified": True,
            "revision": current["S"],
            "evidence": "published-current",
        },
        "I": {
            "verified": True,
            "revision": current["I"],
            "evidence": "published-current",
        },
    }
    if changed["S"]:
        verification["S"] = _verify_skill_source(
            reader,
            revision=requested["S"],
            toolchain_revision=requested["T"],
            runtime_lock=runtime_lock,
        )
    if changed["I"]:
        verification["I"] = _verify_installer(
            reader,
            revision=requested["I"],
            skill_source_revision=requested["S"],
        )

    fresh = {
        "T": changed["T"] and bool(verification["T"].get("verified")),
        "S": changed["S"] and bool(verification["S"].get("verified")),
        "I": (
            changed["I"]
            and bool(verification["I"].get("verified"))
            and (not changed["S"] or bool(verification["S"].get("verified")))
            and not (changed["T"] and not changed["S"])
        ),
    }

    awaiting: list[str] = []
    if changed["T"] and not fresh["T"]:
        awaiting.append("T")
    if (changed["T"] or changed["S"]) and not fresh["S"]:
        awaiting.append("S")
    if (changed["T"] or changed["S"] or changed["I"]) and not fresh["I"]:
        awaiting.append("I")

    stale: list[str] = []
    if changed["T"]:
        stale.extend(
            (
                "T-self-host-input",
                "T-self-host-projection",
                "T-promotion",
                "S-installer-candidate",
                "I-policy-publication",
                "policy-to-site-projection",
            )
        )
    elif changed["S"]:
        stale.extend(
            (
                "S-installer-candidate",
                "I-policy-publication",
                "policy-to-site-projection",
            )
        )
    elif changed["I"]:
        stale.extend(("I-policy-publication", "policy-to-site-projection"))

    awaiting_evidence: list[str] = []
    if changed["T"] and not runtime_lock.get("verified"):
        awaiting_evidence.append("runtime-lock-sha256")

    publication_surfaces = _surface_inventory(
        root,
        "I",
        current["I"],
        requested["I"],
    )
    publication_surfaces.extend(
        _surface_inventory(
            root,
            "S",
            current["S"],
            requested["S"],
            paths=S_PUBLICATION_SURFACES,
        )
    )

    stages = [
        {
            "name": "T-self-host-input",
            "identity": "T",
            "action": (
                "mutate the human-owned .agent-policy.yml input pin; "
                "it is not generated output"
            ),
            "input_mutations": [".agent-policy.yml"],
            "generated_surfaces": [],
            "validation": list(VALIDATION_BY_STAGE["T-self-host-input"]),
        },
        {
            "name": "T-self-host-projection",
            "identity": "T",
            "action": (
                "regenerate projection from the frozen semantic/runtime candidate; "
                "do not predict a future commit SHA"
            ),
            "generated_surfaces": list(
                REGENERATION_SURFACES["T-self-host-projection"]
            ),
            "validation": list(
                VALIDATION_BY_STAGE["T-self-host-projection"]
            ),
        },
        {
            "name": "T-promotion",
            "identity": "T",
            "action": (
                "bind the reviewed stable runtime with its full SHA and "
                "verified runtime-lock digest"
            ),
            "direct_surfaces": _surface_inventory(
                root,
                "T",
                current["T"],
                requested["T"],
            ),
            "runtime_lock": runtime_lock,
            "validation": list(VALIDATION_BY_STAGE["T-promotion"]),
        },
        {
            "name": "S-installer-candidate",
            "identity": "S",
            "action": (
                "materialize and verify a separately reviewable Skill-source identity, "
                "then update only installer-candidate bindings"
            ),
            "direct_surfaces": _surface_inventory(
                root,
                "S",
                current["S"],
                requested["S"],
            ),
            "validation": list(
                VALIDATION_BY_STAGE["S-installer-candidate"]
            ),
        },
        {
            "name": "I-policy-publication",
            "identity": "I",
            "action": (
                "after a verified installer identity exists, publish immutable "
                "I/S together"
            ),
            "direct_surfaces": publication_surfaces,
            "generated_surfaces": list(
                REGENERATION_SURFACES["I-policy-publication"]
            ),
            "validation": list(
                VALIDATION_BY_STAGE["I-policy-publication"]
            ),
        },
        {
            "name": "policy-to-site-projection",
            "identity": "policy-publication",
            "action": (
                "after canonical Policy publication changes, refresh Site-owned "
                "integration without making Site a Policy super-authority"
            ),
            "external_authority": "site",
            "generated_surfaces": list(
                REGENERATION_SURFACES["policy-to-site-projection"]
            ),
            "validation": list(
                VALIDATION_BY_STAGE["policy-to-site-projection"]
            ),
        },
    ]

    return {
        "schema_version": 1,
        "current": current,
        "requested": requested,
        "changed": changed,
        "verification": verification,
        "fresh_materialized": fresh,
        "runtime_lock": runtime_lock,
        "stale_stages": stale,
        "awaiting_immutable_identity_materialization": awaiting,
        "awaiting_release_evidence": awaiting_evidence,
        "stages": stages,
        "invariants": {
            "full_sha_only": True,
            "predict_future_commit_sha": False,
            "self_referential_release": False,
            "site_is_policy_super_authority": False,
            "runtime_lock_digest_required": True,
        },
    }


def check_current_inventory(plan: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for stage in plan["stages"]:
        for surface in stage.get("direct_surfaces", []):
            if surface["current_identity_occurrences"] < 1:
                errors.append(
                    f"{stage['name']}: current identity not found in declared "
                    f"surface {surface['path']}"
                )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Plan immutable Policy release identity propagation without "
            "mutating repository state."
        )
    )
    parser.add_argument("--toolchain-revision")
    parser.add_argument("--skill-source-revision")
    parser.add_argument("--installer-revision")
    parser.add_argument("--runtime-lock-sha256")
    parser.add_argument(
        "--check-current",
        action="store_true",
        help=(
            "fail when a declared direct identity surface no longer contains "
            "its current published identity"
        ),
    )
    args = parser.parse_args()

    try:
        plan = build_plan(
            toolchain_revision=args.toolchain_revision,
            skill_source_revision=args.skill_source_revision,
            installer_revision=args.installer_revision,
            runtime_lock_sha256=args.runtime_lock_sha256,
        )
        errors = check_current_inventory(plan) if args.check_current else []
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(
            json.dumps(
                {"ok": False, "error": str(exc)},
                indent=2,
                sort_keys=True,
            )
        )
        return 2

    print(
        json.dumps(
            {"ok": not errors, "errors": errors, "plan": plan},
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
