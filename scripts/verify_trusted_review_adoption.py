#!/usr/bin/env python3
"""Verify Site's executable trusted-review projection against exact Policy Git objects."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import stat
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE_REVISION = "71fad184a072c9335af793ac1efb7e6332c449b0"
SOURCE_TREE = "78d19c3683d9b4cb2d15deaec021021b3b43014d"
MANIFEST_PATH = ROOT / "trusted-review-adoption.json"
SCHEMA_PATH = ROOT / "schemas/trusted-review-adoption.schema.json"
RUNTIME_INPUTS = (
    {
        "authority": "policy",
        "path": "release/skill-installer.json",
        "revision": SOURCE_REVISION,
        "object_type": "blob",
        "object_id": "87116bb061d79b54dc0e2e2ea66566799d25a1ad",
        "resolution": "authenticated-target-base-must-be-policy",
    },
    {
        "authority": "policy",
        "path": ".agent-policy.yml",
        "revision": SOURCE_REVISION,
        "object_type": "blob",
        "object_id": "5f118905e4732c31934885fcc4b86620ab28ecac",
        "resolution": "semantic-configuration-from-authenticated-target-base",
    },
    {
        "authority": "policy",
        "path": ".agent-policy.lock",
        "revision": SOURCE_REVISION,
        "object_type": "blob",
        "object_id": "6d75b407b20089c7de9343dae57ecc527ce0bbbc",
        "resolution": "semantic-input-and-generated-output-lock-from-authenticated-target-base",
    },
    {
        "authority": "policy",
        "path": "AGENTS.md",
        "revision": SOURCE_REVISION,
        "object_type": "blob",
        "object_id": "e2c54e9979ca361fbce48f91a0c864943c14d77e",
        "resolution": "generated-policy-output-from-authenticated-target-base",
    },
    {
        "authority": "policy",
        "path": ".review-authority/review-policy.md",
        "revision": SOURCE_REVISION,
        "object_type": "blob",
        "object_id": "dde2a48868029769dbeef50fa049bbf433058b63",
        "resolution": "provider-neutral-semantic-output-from-authenticated-target-base",
    },
    {
        "authority": "policy",
        "path": "scripts/install_agent_policy_skill.py",
        "revision": "f4457c90854db34c3ce8e1c381f67a4d7d5ea523",
        "object_type": "blob",
        "object_id": "b005370e9b7039d288ac65fe094e124e6908109d",
        "resolution": "immutable-revision-selected-by-base-descriptor",
    },
    {
        "authority": "policy",
        "path": "skills/agent-policy",
        "revision": "344aaf0b140e3c066363297012bb866efbc106e4",
        "object_type": "tree",
        "object_id": "a753a167c68fda0cb08393c35f0b13b79788309d",
        "resolution": "immutable-revision-selected-by-installer",
    },
    {
        "authority": "policy",
        "path": "skills/agent-policy/runtime-manifest.json",
        "revision": "344aaf0b140e3c066363297012bb866efbc106e4",
        "object_type": "blob",
        "object_id": "06497eb775adb674539ab9fbf3d222d4024a6e47",
        "resolution": "runtime-selection-record-inside-installed-skill",
    },
    {
        "authority": "policy",
        "path": "requirements-runtime.lock",
        "revision": "9c702d755ddc42b941a63eafd8f9aee06969517d",
        "object_type": "blob",
        "object_id": "0514ecc1c5e13b1491cb582aa907df77bc3862ae",
        "sha256": "b2fd430887774e9625dfbe7fdc1e1c4d855e1d5335b7c3e977e87d6278abdee8",
        "resolution": "immutable-toolchain-runtime-lock-selected-by-skill",
    },
    {
        "authority": "policy",
        "path": "pyproject.toml",
        "revision": "9c702d755ddc42b941a63eafd8f9aee06969517d",
        "object_type": "blob",
        "object_id": "0b323c1b7282f2d36e2ae25abd47dcb38e719ce2",
        "resolution": "immutable-toolchain-build-metadata",
    },
    {
        "authority": "policy",
        "path": "src/agent_policy",
        "revision": "9c702d755ddc42b941a63eafd8f9aee06969517d",
        "object_type": "tree",
        "object_id": "43912a315d2a5de90be5007a5b648a3d9cfb6fb9",
        "resolution": "immutable-toolchain-package-source",
    },
)
RUNTIME_INPUTS += tuple(
    {
        "authority": "policy",
        "path": path,
        "revision": revision,
        "object_type": object_type,
        "object_id": object_id,
        "resolution": resolution,
    }
    for revision, resolution, entries in (
        (
            "9c702d755ddc42b941a63eafd8f9aee06969517d",
            "immutable-skill-default-toolchain-package-closure",
            (
                ("requirements-runtime.lock", "blob", "0514ecc1c5e13b1491cb582aa907df77bc3862ae"),
                ("pyproject.toml", "blob", "0b323c1b7282f2d36e2ae25abd47dcb38e719ce2"),
                ("src/agent_policy", "tree", "43912a315d2a5de90be5007a5b648a3d9cfb6fb9"),
                ("LICENSE", "blob", "c853b1437f5e9749f069308ac88883cc7b011681"),
                ("README.md", "blob", "5b4079e162f1030f2602a72edb8d93ef3180e6c2"),
                ("schemas", "tree", "065d6a032e5a0b9a69bdc808d69c1dd743fd3cf9"),
                ("profiles", "tree", "abf33a2fe19679d8a02a3aacc9b0aea872c348e5"),
                ("policy", "tree", "19d8f263db710c522d7e3180a7d54b65cb3d8776"),
                ("templates", "tree", "cb74ff9e5ee1239d14f9d577c58c8d3a1b496fb8"),
                ("skills", "tree", "0d1042e7c8f86192475f1b646cea7e046bad21c6"),
            ),
        ),
        (
            "aa6f9ac4822cbbb9b7bb6940525d54ad690d76d3",
            "immutable-policy-lock-selected-toolchain-package-closure",
            (
                ("requirements-runtime.lock", "blob", "0514ecc1c5e13b1491cb582aa907df77bc3862ae"),
                ("pyproject.toml", "blob", "0fe1e7498c9c7746defcac6cd40c830701a90ba0"),
                ("src/agent_policy", "tree", "604c2065eda78da9e8f5f150e0c6433b0eef3f7d"),
                ("LICENSE", "blob", "c853b1437f5e9749f069308ac88883cc7b011681"),
                ("README.md", "blob", "0a9c762fb121e65681d1123d07a98fe96e3284d6"),
                ("schemas", "tree", "0d3d8e6681e9456154fea3d0e1282022d8978891"),
                ("profiles", "tree", "d0bea91f6004737e4155401bd25d22fddbd88e86"),
                ("policy", "tree", "519b076014b1c05538aa99094870f2e0f96e8134"),
                ("templates", "tree", "e68eb2b28b3629d982946946cb16a381d3571bbd"),
                ("skills", "tree", "88804f9908e95dff6face0d6b92f273f684936c4"),
                ("delivery", "tree", "79e6c537c271851848bab516ed23d611791c5585"),
            ),
        ),
    )
    for path, object_type, object_id in entries
)
EXECUTION_FILES = (
    ("workflow", ".github/workflows/trusted-review-bootstrap.yml", "100644", "4690223a4dfab92870ac124281fea06e0e2fc302"),
    ("local-action", ".github/actions/trusted-review-freeze-role/action.yml", "100644", "6d2b93a752a105bd3093675084fc207b15d720f4"),
    ("runtime-lock", "requirements-runtime.lock", "100644", "0514ecc1c5e13b1491cb582aa907df77bc3862ae"),
    ("handoff-tool", "scripts/prepare_trusted_review_handoff.py", "100644", "7fce312601e640b5caffce2ea4bf3cfbc5ad3c8e"),
    ("actions-observer", "scripts/trusted_review_actions.py", "100644", "4c1ae88948dd25333bb9d2f8c4d228308d5a485b"),
    ("freeze-tool", "scripts/trusted_review_freeze.py", "100644", "bd57fcdba9fd554e0ce91ec12c37418c7551f788"),
    ("freeze-provider", "scripts/trusted_review_freeze_provider.py", "100644", "212be2adf54767ee76706d6009ef7f6030ebd230"),
    ("provider-observation-schema", "schemas/trusted-review-provider-observation.schema.json", "100644", "f2994df3321ff006113463c00a01614025750434"),
    ("role-freeze-schema", "schemas/trusted-review-role-freeze-evidence.schema.json", "100644", "6e6c42895dd7a667ca12ca1d716474eb2ba29e7b"),
    ("aggregate-freeze-schema", "schemas/trusted-review-freeze-evidence.schema.json", "100644", "1912ba8a7b19c9cf8f3d685b785680bd78350fe2"),
    ("protected-local-view-schema", "schemas/trusted-review-local-view.schema.json", "100644", "a0339093439f843b85f50695d1b48400cba81309"),
)


def git(*args: str, text: bool = True) -> str | bytes:
    result = subprocess.run(
        ["git", "-C", str(ROOT), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=text,
    )
    return result.stdout.strip() if text else result.stdout


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def ensure_commit(revision: str) -> None:
    present = subprocess.run(
        ["git", "-C", str(ROOT), "cat-file", "-e", f"{revision}^{{commit}}"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if present.returncode == 0:
        return
    subprocess.run(
        [
            "git",
            "-C",
            str(ROOT),
            "fetch",
            "--no-tags",
            "--depth=1",
            "https://github.com/TakashiSasaki/templates.git",
            revision,
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def project_site_workflow(source: bytes) -> bytes:
    """Apply Site's one recorded workflow integration transform to exact Policy bytes."""
    anchor = (
        b"      ROLE_PROTECTED_ROOT: ${{ runner.temp }}/trusted-review/role-protected\n"
        b"      AGGREGATE_PROTECTED_ROOT: ${{ runner.temp }}/trusted-review/aggregate-protected\n"
    )
    insertion = (
        b"      TRUSTED_REVIEW_PROTECTED_ROOT: "
        b"${{ runner.temp }}/trusted-review/role-protected\n"
    )
    require(source.count(anchor) == 1, "Policy workflow transform input anchor is not unique")
    return source.replace(
        anchor,
        anchor.replace(b"      AGGREGATE_PROTECTED_ROOT:", insertion + b"      AGGREGATE_PROTECTED_ROOT:"),
        1,
    )


def main() -> int:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    try:
        import jsonschema
    except ImportError as exc:
        raise RuntimeError("jsonschema is required to verify the adoption record") from exc
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.validate(manifest, schema)

    source = manifest["source"]
    require(source["revision"] == SOURCE_REVISION, "unexpected Policy source revision")
    require(source["tree"] == SOURCE_TREE, "unexpected Policy source tree")
    revisions = sorted({SOURCE_REVISION, *(item["revision"] for item in RUNTIME_INPUTS)})
    for revision in revisions:
        ensure_commit(revision)
    require(git("rev-parse", f"{SOURCE_REVISION}^{{tree}}") == SOURCE_TREE, "Policy source tree object mismatch")
    require(git("cat-file", "-t", SOURCE_REVISION) == "commit", "exact Policy source commit is unavailable")

    procedure = manifest["adoption_procedure"]
    verifier = ROOT / procedure["verifier"]
    verifier_digest = hashlib.sha256(verifier.read_bytes()).hexdigest()
    require(verifier_digest == procedure["verifier_sha256"], "adoption verifier digest mismatch")
    require(manifest["runtime_inputs"] == list(RUNTIME_INPUTS), "Policy runtime input closure mismatch")

    adopted = manifest["adopted_files"]
    actual_paths = tuple(item["destination_path"] for item in adopted)
    expected_paths = tuple(entry[1] for entry in EXECUTION_FILES)
    require(actual_paths == expected_paths, "adopted file order or destination closure mismatch")
    transformed = 0
    for item, (role, path, mode, blob) in zip(adopted, EXECUTION_FILES, strict=True):
        require(item["role"] == role, f"adoption role mismatch for {path}")
        require(item["source_path"] == path, f"source path mismatch for {path}")
        require(item["destination_path"] == path, f"destination path mismatch for {path}")
        require(item["source_blob"] == blob, f"manifest source blob mismatch for {path}")
        require(item["source_mode"] == mode, f"manifest source mode mismatch for {path}")
        source_entry = git("ls-tree", SOURCE_REVISION, "--", path).split(maxsplit=3)
        require(len(source_entry) == 4, f"Policy source entry is missing: {path}")
        source_mode, source_type, source_blob, source_path = source_entry
        require(source_type == "blob", f"Policy source is not a file blob: {path}")
        require(source_mode == mode, f"Policy source mode changed for {path}")
        require(source_blob == blob, f"Policy source object changed for {path}")
        require(source_path == path, f"Policy source path changed for {path}")
        destination = ROOT / path
        require(destination.is_file(), f"adopted destination is missing: {path}")
        require(not destination.is_symlink(), f"adopted destination is a symlink: {path}")
        require(stat.S_IMODE(destination.stat().st_mode) == 0o644, f"adopted file mode differs from Policy source: {path}")
        destination_bytes = destination.read_bytes()
        transformation = item.get("transformation")
        if transformation is None:
            projected_blob = git("hash-object", "--", path)
            require(projected_blob == blob, f"adopted bytes differ from Policy source: {path}")
        else:
            require(
                path == ".github/workflows/trusted-review-bootstrap.yml",
                f"unsupported transformed adoption path: {path}",
            )
            source_bytes = git("show", f"{SOURCE_REVISION}:{path}", text=False)
            source_digest = hashlib.sha256(source_bytes).hexdigest()
            require(
                transformation["id"] == "site.trusted-review-add-role-protected-root-env"
                and transformation["version"] == 1,
                f"unsupported Policy-to-Site transform for {path}",
            )
            require(
                transformation["source_sha256"] == source_digest,
                f"workflow transform input digest mismatch for {path}",
            )
            projected_bytes = project_site_workflow(source_bytes)
            projected_digest = hashlib.sha256(projected_bytes).hexdigest()
            require(
                transformation["output_sha256"] == projected_digest,
                f"workflow transform output digest mismatch for {path}",
            )
            require(
                destination_bytes == projected_bytes,
                f"adopted workflow differs from deterministic Policy projection: {path}",
            )
            transformed += 1
    require(transformed == 1, "expected exactly one recorded Site workflow transform")

    for item in RUNTIME_INPUTS:
        revision = item["revision"]
        path = item["path"]
        require(git("cat-file", "-t", revision) == "commit", f"immutable Policy runtime revision is unavailable: {revision}")
        object_entry = git("ls-tree", revision, "--", path).split(maxsplit=3)
        require(len(object_entry) == 4, f"dynamic Policy runtime input is missing: {path}")
        mode, object_type, object_id, source_path = object_entry
        require(source_path == path, f"dynamic Policy runtime path changed: {path}")
        require(object_type == item["object_type"], f"dynamic Policy runtime object type changed: {path}")
        require(object_id == item["object_id"], f"dynamic Policy runtime object changed: {path}")
        if "sha256" in item:
            raw = git("show", f"{revision}:{path}", text=False)
            require(hashlib.sha256(raw).hexdigest() == item["sha256"], f"dynamic Policy runtime digest changed: {path}")
    descriptor = json.loads(git("show", f"{SOURCE_REVISION}:release/skill-installer.json"))
    require(descriptor["installer"]["revision"] == "f4457c90854db34c3ce8e1c381f67a4d7d5ea523", "reviewed source installer revision differs from recorded runtime")
    require(descriptor["installer"]["path"] == "scripts/install_agent_policy_skill.py", "reviewed source installer path differs from recorded runtime")
    require(descriptor["skill_source"]["revision"] == "344aaf0b140e3c066363297012bb866efbc106e4", "reviewed source skill revision differs from recorded runtime")
    require(descriptor["skill_source"]["path"] == "skills/agent-policy", "reviewed source skill path differs from recorded runtime")
    installer_source = git("show", "f4457c90854db34c3ce8e1c381f67a4d7d5ea523:scripts/install_agent_policy_skill.py")
    require('SKILL_SOURCE_REVISION = "344aaf0b140e3c066363297012bb866efbc106e4"' in installer_source, "immutable installer selects an unexpected skill source")
    require('SKILL_SOURCE_PATH = "skills/agent-policy"' in installer_source, "immutable installer selects an unexpected skill path")
    skill_manifest = json.loads(git("show", "344aaf0b140e3c066363297012bb866efbc106e4:skills/agent-policy/runtime-manifest.json"))
    require(skill_manifest["toolchain"]["revision"] == "9c702d755ddc42b941a63eafd8f9aee06969517d", "installed skill selects an unexpected toolchain")
    require(skill_manifest["runtime_lock"]["sha256"] == "b2fd430887774e9625dfbe7fdc1e1c4d855e1d5335b7c3e977e87d6278abdee8", "installed skill runtime lock digest changed")
    policy_lock = git("show", f"{SOURCE_REVISION}:.agent-policy.lock")
    require("revision: aa6f9ac4822cbbb9b7bb6940525d54ad690d76d3" in policy_lock, "reviewed Policy source selects an unexpected locked toolchain")
    return 0


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as exc:
        print(f"TRUSTED_REVIEW_ADOPTION_FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    print(
        "TRUSTED_REVIEW_ADOPTION_OK "
        f"policy={SOURCE_REVISION} tree={SOURCE_TREE} files={len(EXECUTION_FILES)} "
        f"exact={len(EXECUTION_FILES) - 1} transformed=1"
    )
