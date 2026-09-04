from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
INSTALLER_DESCRIPTOR = "release/skill-installer.json"

DIRECT_SURFACES: dict[str, tuple[str, ...]] = {
    "T": (
        "release/toolchain.json",
        "skills/agent-policy/runtime-manifest.json",
    ),
    "S": (
        "scripts/install_agent_policy_skill.py",
        "scripts/smoke_test_agent_policy_installer_candidate.py",
        "tests/test_installer_candidate_smoke.py",
        "tests/test_remote_skill_installer.py",
        "tests/test_skill_installer_publication.py",
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
    "T-self-host-input": ("tests/test_policy_self_hosting.py",),
    "T-self-host-projection": (
        "tests/test_policy_self_hosting.py",
        "tests/test_repository_change_orchestration_skill.py",
    ),
    "T-promotion": (
        "tests/test_immutable_toolchain_identity.py",
        "tests/test_release_lifecycle.py",
        "scripts/verify-release-state.py",
        "skills/agent-policy/runtime-manifest.json",
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


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _require_full_sha(name: str, value: str) -> str:
    if FULL_SHA.fullmatch(value) is None:
        raise ValueError(
            f"{name} must be a lowercase full 40-character SHA: {value!r}"
        )
    return value


def _require_sha256(value: str) -> str:
    if SHA256.fullmatch(value) is None:
        raise ValueError(
            "runtime lock digest must be a lowercase 64-character SHA-256"
        )
    return value


def _current_runtime_lock_evidence(root: Path) -> dict[str, str | bool]:
    lock = root / "requirements-runtime.lock"
    if not lock.is_file():
        return {
            "available": False,
            "status": "runtime lock digest unavailable / awaiting",
        }
    return {
        "available": True,
        "sha256": hashlib.sha256(lock.read_bytes()).hexdigest(),
        "source": "current-repository-lock",
    }


def runtime_lock_evidence(
    root: Path = ROOT,
    *,
    toolchain_changed: bool = False,
    supplied_digest: str | None = None,
) -> dict[str, str | bool]:
    if toolchain_changed:
        if supplied_digest is None:
            return {
                "available": False,
                "status": "runtime lock digest unavailable / awaiting",
            }
        return {
            "available": True,
            "sha256": _require_sha256(supplied_digest),
            "source": "supplied-for-requested-toolchain",
        }
    if supplied_digest is not None:
        return {
            "available": True,
            "sha256": _require_sha256(supplied_digest),
            "source": "supplied-for-current-toolchain",
        }
    return _current_runtime_lock_evidence(root)


def current_identities(root: Path = ROOT) -> dict[str, str]:
    toolchain = _load_json(root / "release/toolchain.json")
    installer = _load_json(root / INSTALLER_DESCRIPTOR)
    t = str(toolchain["toolchain"]["revision"])
    s = str(installer["skill_source"]["revision"])
    i = str(installer["installer"]["revision"])
    return {
        "T": _require_full_sha("T", t),
        "S": _require_full_sha("S", s),
        "I": _require_full_sha("I", i),
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
        path = root / relative
        text = path.read_text(encoding="utf-8")
        occurrences = text.count(current)
        records.append(
            {
                "identity": identity,
                "path": relative,
                "current_identity_occurrences": occurrences,
                "expected_replacements": (
                    occurrences if requested != current else 0
                ),
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


def build_plan(
    root: Path = ROOT,
    *,
    toolchain_revision: str | None = None,
    skill_source_revision: str | None = None,
    installer_revision: str | None = None,
    runtime_lock_sha256: str | None = None,
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

    fresh = {
        "T": changed["T"],
        "S": changed["S"],
        "I": changed["I"] and (not changed["T"] or changed["S"]),
    }

    awaiting: list[str] = []
    if changed["T"] and not fresh["S"]:
        awaiting.extend(("S", "I"))
    elif (changed["T"] or changed["S"]) and not fresh["I"]:
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

    runtime_lock = runtime_lock_evidence(
        root,
        toolchain_changed=changed["T"],
        supplied_digest=runtime_lock_sha256,
    )
    awaiting_evidence: list[str] = []
    if changed["T"] and not runtime_lock["available"]:
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
            paths=(INSTALLER_DESCRIPTOR,),
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
                "regenerate projection from the frozen semantic/runtime "
                "candidate; do not predict a future commit SHA"
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
                "matching runtime-lock digest"
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
                "materialize a separately reviewable Skill-source identity, "
                "then propagate its full SHA through installer-candidate "
                "bindings"
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
                "after a new installer identity exists, publish immutable "
                "I/S together without self-reference"
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
                "after canonical Policy publication changes, refresh "
                "Site-owned integration without making Site a Policy "
                "super-authority"
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
                    f"{stage['name']}: current identity not found in "
                    f"declared surface {surface['path']}"
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
