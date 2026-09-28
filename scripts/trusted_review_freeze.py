"""GitHub Actions/GHCR freeze evidence and protected-view verification."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, ValidationError

try:
    from scripts.trusted_review_actions import (
        ActionsRunIdentity,
        TrustedObservationError,
        _verify_attestation_claims,
    )
except ImportError:
    from trusted_review_actions import (
        ActionsRunIdentity,
        TrustedObservationError,
        _verify_attestation_claims,
    )

GH_EXECUTABLE = "/usr/bin/gh"
OCI_REPOSITORY = "ghcr.io/takashisasaki/templates/trusted-review-authority"
FREEZE_SCHEMA = (
    Path(__file__).resolve().parents[1] / "schemas/trusted-review-freeze-evidence.schema.json"
)
ROLE_TO_SECTION = {
    "bootstrap_run_image": "frozen_bootstrap_image",
    "trusted_base_snapshot": "frozen_trusted_base",
    "runtime_image": "frozen_runtime",
    "review_bundle": "review_authority_bundle",
}
SECTION_TO_LOCATOR = {
    "bootstrap_run_image": "bootstrap_run_image",
    "trusted_base_snapshot": "trusted_base_snapshot",
    "runtime_image": "runtime_image",
    "review_bundle": "review_bundle",
}


class TrustedFreezeError(ValueError):
    """Raised when OCI freeze evidence or its protected view is invalid."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise TrustedFreezeError("duplicate JSON key in freeze evidence")
        result[key] = value
    return result


def validate_freeze_evidence(document: Any) -> None:
    try:
        schema = json.loads(FREEZE_SCHEMA.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(document)
    except OSError as exc:
        raise TrustedFreezeError("freeze-evidence schema is unavailable") from exc
    except json.JSONDecodeError as exc:
        raise TrustedFreezeError("freeze-evidence schema is malformed") from exc
    except ValidationError as exc:
        path = ".".join(str(part) for part in exc.absolute_path) or "<root>"
        raise TrustedFreezeError(f"freeze evidence violates schema at {path}") from exc
    roles = [item["role"] for item in document["roles"]]
    if len(roles) != len(set(roles)) or set(roles) != set(ROLE_TO_SECTION):
        raise TrustedFreezeError("freeze evidence must contain each of the four roles exactly once")


def load_freeze_evidence(path: Path) -> tuple[dict[str, Any], bytes, str]:
    try:
        raw = path.read_bytes()
        document = json.loads(raw, object_pairs_hook=_reject_duplicate_keys)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TrustedFreezeError("freeze evidence is unavailable or malformed") from exc
    if not isinstance(document, dict):
        raise TrustedFreezeError("freeze evidence must be a JSON object")
    validate_freeze_evidence(document)
    return document, raw, hashlib.sha256(raw).hexdigest()


def _inventory_digest(directory: Path) -> str:
    absolute = directory.expanduser().absolute()
    current = Path(absolute.anchor)
    for component in absolute.parts[1:]:
        current /= component
        if current.is_symlink():
            raise TrustedFreezeError(
                f"authority inventory contains a symbolic-link component: {current}"
            )
    if not absolute.is_dir():
        raise TrustedFreezeError("authority inventory root is not a directory")
    records: list[dict[str, str]] = []
    for path in sorted(absolute.rglob("*"), key=lambda item: item.as_posix()):
        relative = path.relative_to(absolute).as_posix()
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode):
            raise TrustedFreezeError(f"authority inventory contains a symbolic link: {relative}")
        if stat.S_ISDIR(info.st_mode):
            records.append({"path": relative, "type": "directory"})
        elif stat.S_ISREG(info.st_mode):
            if info.st_nlink != 1:
                raise TrustedFreezeError(f"authority inventory contains a hard link: {relative}")
            records.append({"path": relative, "type": "file", "sha256": _file_sha256(path)})
        else:
            raise TrustedFreezeError(f"authority inventory contains a special file: {relative}")
    raw = json.dumps(records, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(64 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _readonly_mount(path: Path, mountinfo: str | None = None) -> bool:
    resolved = path.expanduser().absolute().resolve(strict=True)
    try:
        contents = (
            Path("/proc/self/mountinfo").read_text(encoding="utf-8")
            if mountinfo is None
            else mountinfo
        )
    except OSError as exc:
        raise TrustedFreezeError("cannot inspect protected-view mount state") from exc
    matches: list[tuple[int, bool]] = []
    for line in contents.splitlines():
        try:
            before, after = line.split(" - ", 1)
            left = before.split()
            right = after.split()
            mountpoint = Path(
                left[4].replace("\\040", " ").replace("\\011", "\t").replace("\\134", "\\")
            ).resolve()
            resolved.relative_to(mountpoint)
        except (ValueError, IndexError):
            continue
        opts = set(left[5].split(",")) | set(right[2].split(","))
        matches.append((len(mountpoint.parts), "ro" in opts))
    if not matches:
        raise TrustedFreezeError("authority path is not represented in mount information")
    return max(matches, key=lambda item: item[0])[1]


def require_protected_view(path: Path, *, mountinfo: str | None = None) -> None:
    absolute = path.expanduser().absolute()
    current = Path(absolute.anchor)
    for component in absolute.parts[1:]:
        current /= component
        if current.is_symlink():
            raise TrustedFreezeError(f"authority path contains a symbolic link: {current}")
    if not absolute.exists() or not absolute.is_dir():
        raise TrustedFreezeError(f"authority role is not a regular directory: {path}")
    try:
        stat_readonly = bool(os.statvfs(absolute).f_flag & getattr(os, "ST_RDONLY", 1))
    except OSError as exc:
        raise TrustedFreezeError("cannot inspect authority filesystem flags") from exc
    if not stat_readonly or not _readonly_mount(path, mountinfo):
        raise TrustedFreezeError(f"authority role is not on a read-only filesystem: {path}")


class GitHubActionsOciFreezeVerifier:
    """Verifies one attested GHCR image and its four read-only role views."""

    name = "github-actions-ghcr-oci-v1"

    def __init__(
        self,
        freeze_evidence_path: Path,
        *,
        token: str | None = None,
        run_identity: ActionsRunIdentity | None = None,
        gh_executable: str = GH_EXECUTABLE,
        runner: Callable[..., Any] = subprocess.run,
        mountinfo_reader: Callable[[], str] | None = None,
    ) -> None:
        self.freeze_evidence_path = freeze_evidence_path.expanduser().resolve()
        self.token = token if token is not None else os.environ.get("GH_TOKEN", "")
        if not self.token:
            raise TrustedFreezeError("GH_TOKEN is required to verify the GHCR attestation")
        self.run_identity = run_identity or ActionsRunIdentity.from_env()
        self.gh_executable = gh_executable
        self.runner = runner
        self.mountinfo_reader = mountinfo_reader
        self.document, self.raw_bytes, self.sha256 = load_freeze_evidence(self.freeze_evidence_path)
        self.production_capable = (
            token is None
            and run_identity is None
            and gh_executable == GH_EXECUTABLE
            and runner is subprocess.run
            and mountinfo_reader is None
        )
        self._attestation_verified = False
        self._evidence_attestation_verified = False
        self._verified_roles: set[str] = set()

    def verify_document_digest(self, handoff: dict[str, Any]) -> None:
        self._require_unchanged_evidence()
        meta = handoff.get("freeze_evidence")
        if not isinstance(meta, dict) or meta.get("sha256") != self.sha256:
            raise TrustedFreezeError("freeze-evidence bytes do not match the handoff digest")
        self._verify_evidence_attestation()
        self.bind_handoff(handoff)
        self._verify_target(handoff)
        self._verify_attestation()

    def verify(self, section: str, entry: dict[str, Any]) -> None:
        role = next((name for name, value in ROLE_TO_SECTION.items() if value == section), None)
        if role is None:
            raise TrustedFreezeError(f"unsupported freeze section: {section}")
        record = self._role_record(role)
        if entry.get("inventory_digest") != record["inventory_sha256"]:
            raise TrustedFreezeError(f"freeze role inventory mismatch: {role}")
        if record.get("identity") != self._expected_role_identity(role):
            raise TrustedFreezeError(f"freeze role identity mismatch: {role}")
        locator_key = SECTION_TO_LOCATOR[role]
        locators = getattr(self, "_handoff_locators", None)
        if locators is None:
            raise TrustedFreezeError("freeze verifier has not been bound to handoff locators")
        role_path = Path(locators[locator_key])
        self._verify_role_view(role, role_path, record)
        self._verified_roles.add(role)

    def _expected_role_identity(self, role: str) -> dict[str, Any]:
        handoff = getattr(self, "_bound_handoff", None)
        if handoff is None:
            raise TrustedFreezeError("freeze verifier has not been bound to a handoff")
        if role == "bootstrap_run_image":
            installer = handoff["bootstrap_authority"]["installer"]
            installation = handoff["bootstrap_authority"]["installation_attestation"]
            return {
                "installer_repository": installer["repository"],
                "installer_revision": installer["revision"],
                "installer_path": installer["path"],
                "installer_blob_sha": installer.get("git_blob") or installer["blob_sha"],
                "installer_sha256": installer["sha256"],
                "installation_attestation_sha256": installation["sha256"],
            }
        if role == "trusted_base_snapshot":
            entry = handoff["frozen_trusted_base"]
            return {"base_sha": entry["revision"], "base_tree": entry["tree"]}
        if role == "runtime_image":
            entry = handoff["frozen_runtime"]
            return {
                "toolchain_repository": entry["toolchain"]["repository"],
                "toolchain_revision": entry["toolchain"]["revision"],
                "lock_sha256": entry["lock"]["sha256"],
                "runtime_attestation_sha256": entry["runtime_attestation"]["sha256"],
            }
        if role == "review_bundle":
            entry = handoff["review_authority_bundle"]
            return {
                "manifest_sha256": entry["manifest_sha256"],
                "procedure_skill_sha256": entry["procedure"]["skill_sha256"],
                "semantic_policy_sha256": entry["semantic"]["sha256"],
            }
        raise TrustedFreezeError(f"unsupported role: {role}")

    def bind_handoff(self, handoff: dict[str, Any]) -> None:
        locators = handoff.get("locators")
        if not isinstance(locators, dict):
            raise TrustedFreezeError("handoff locators are missing")
        self._handoff_locators = locators
        self._bound_handoff = handoff

    def verify_post_use(self, handoff: dict[str, Any]) -> None:
        self._require_unchanged_evidence()
        if self._verified_roles != set(ROLE_TO_SECTION):
            raise TrustedFreezeError("all four freeze roles were not verified before use")
        locators = handoff.get("locators") or {}
        for role, locator_key in SECTION_TO_LOCATOR.items():
            self._verify_role_view(role, Path(locators[locator_key]), self._role_record(role))

    def _require_unchanged_evidence(self) -> None:
        try:
            current = self.freeze_evidence_path.read_bytes()
        except OSError as exc:
            raise TrustedFreezeError("freeze evidence changed or disappeared during use") from exc
        if hashlib.sha256(current).hexdigest() != self.sha256:
            raise TrustedFreezeError("freeze-evidence bytes changed during use")

    def _verify_target(self, handoff: dict[str, Any]) -> None:
        target = handoff.get("target")
        repo = (target or {}).get("repository") or {}
        pull = (target or {}).get("pull_request") or {}
        observation = handoff.get("provider_observation") or {}
        target_data = self.document["target"]
        expected = {
            "repository_id": repo.get("id"),
            "repository_name": repo.get("name_with_owner"),
            "pull_request_id": pull.get("id"),
            "pull_request_node_id": pull.get("node_id"),
            "pull_request_number": pull.get("number"),
            "base_sha": pull.get("base_ref_oid"),
            "base_tree": pull.get("base_tree"),
            "head_sha": pull.get("head_ref_oid"),
            "head_tree": pull.get("head_tree"),
            "observation_sha256": observation.get("observation_sha256"),
        }
        for field, value in expected.items():
            if target_data.get(field) != value:
                raise TrustedFreezeError(f"freeze target binding mismatch: {field}")
        if target_data["repository_id"] != self.run_identity.repository_id:
            raise TrustedFreezeError("freeze evidence belongs to another repository")
        attestation = self.document["attestation"]
        if (
            attestation["issuer"] != "https://token.actions.githubusercontent.com"
            or attestation["repository_id"] != self.run_identity.repository_id
            or attestation["workflow_ref"] != self.run_identity.workflow_ref
            or attestation["workflow_sha"] != self.run_identity.workflow_sha
            or attestation["source_sha"] != self.run_identity.source_sha
            or attestation["run_id"] != self.run_identity.run_id
            or attestation["run_attempt"] != self.run_identity.run_attempt
            or attestation["event"] != self.run_identity.event
        ):
            raise TrustedFreezeError("freeze evidence workflow identity is stale or mismatched")
        if self.document["object"]["repository"] != OCI_REPOSITORY:
            raise TrustedFreezeError("freeze evidence names an unexpected GHCR repository")
        if attestation["digest"] != self.document["object"]["manifest_digest"]:
            raise TrustedFreezeError("attestation digest does not match immutable OCI identity")

    def _role_record(self, role: str) -> dict[str, Any]:
        records = [item for item in self.document["roles"] if item.get("role") == role]
        if len(records) != 1:
            raise TrustedFreezeError(f"freeze evidence must contain exactly one {role} record")
        return records[0]

    def _verify_role_view(self, role: str, path: Path, record: dict[str, Any]) -> None:
        mountinfo = self.mountinfo_reader() if self.mountinfo_reader is not None else None
        require_protected_view(path, mountinfo=mountinfo)
        if _inventory_digest(path) != record["inventory_sha256"]:
            raise TrustedFreezeError(f"post-freeze authority inventory changed: {role}")
        expected_rel = record["path"]
        if path.as_posix().rstrip("/").endswith(expected_rel) is False:
            raise TrustedFreezeError(f"authority locator does not match frozen role path: {role}")

    def _verify_attestation(self) -> None:
        if self._attestation_verified:
            return
        digest = self.document["object"]["manifest_digest"]
        self._verify_subject_attestation(
            f"oci://{OCI_REPOSITORY}@{digest}",
            digest.removeprefix("sha256:"),
            use_oci_bundle=True,
        )
        self._attestation_verified = True

    def _verify_evidence_attestation(self) -> None:
        if self._evidence_attestation_verified:
            return
        self._verify_subject_attestation(
            str(self.freeze_evidence_path),
            self.sha256,
            use_oci_bundle=False,
        )
        self._evidence_attestation_verified = True

    def _verify_subject_attestation(
        self,
        subject: str,
        subject_sha256: str,
        *,
        use_oci_bundle: bool,
    ) -> None:
        run = self.run_identity
        command = [
            self.gh_executable,
            "attestation",
            "verify",
            subject,
            "--repo",
            "TakashiSasaki/templates",
            "--signer-workflow",
            "TakashiSasaki/templates/.github/workflows/trusted-review-bootstrap.yml",
            "--signer-digest",
            run.workflow_sha,
            "--source-ref",
            "refs/heads/site",
            "--source-digest",
            run.source_sha,
            "--cert-identity",
            "https://github.com/TakashiSasaki/templates/.github/workflows/trusted-review-bootstrap.yml@refs/heads/site",
            "--cert-oidc-issuer",
            "https://token.actions.githubusercontent.com",
            "--deny-self-hosted-runners",
            "--format",
            "json",
        ]
        if use_oci_bundle:
            command.insert(4, "--bundle-from-oci")
        try:
            result = self.runner(command, check=True, capture_output=True, text=True, timeout=120)
        except (OSError, subprocess.SubprocessError) as exc:
            raise TrustedFreezeError("GitHub OCI Artifact Attestation verification failed") from exc
        try:
            results = json.loads(result.stdout)
        except (TypeError, json.JSONDecodeError) as exc:
            raise TrustedFreezeError("attestation verifier returned malformed JSON") from exc
        if not isinstance(results, list) or len(results) != 1:
            raise TrustedFreezeError("attestation verifier did not return exactly one result")
        verification = (
            results[0].get("verificationResult") if isinstance(results[0], dict) else None
        )
        if not isinstance(verification, dict):
            raise TrustedFreezeError("OCI attestation verification result is incomplete")
        signature = verification.get("signature") or {}
        certificate = signature.get("certificate") or {}
        statement = verification.get("statement") or {}
        try:
            _verify_attestation_claims(
                certificate,
                statement,
                run,
                subject_sha256,
                self.document["attestation"]["owner_id"],
            )
        except TrustedObservationError as exc:
            raise TrustedFreezeError(str(exc)) from exc
