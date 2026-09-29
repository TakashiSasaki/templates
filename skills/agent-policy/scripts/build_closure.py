"""Parse and verify Policy's reviewed PEP 517 build artifact closure."""

from __future__ import annotations

import hashlib
import json
import re
import stat
import zipfile
from dataclasses import dataclass
from email.parser import BytesParser
from email.policy import default
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlsplit

SHA256 = re.compile(r"^[0-9a-f]{64}$")
VERSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.+!_-]*$")
NUMERIC_RELEASE = re.compile(r"^(\d+)\.(\d+)(?:\.(\d+))?$")
WHEEL_FILENAME = re.compile(
    r"^(?P<distribution>[A-Za-z0-9_]+)-(?P<version>[A-Za-z0-9.+!_-]+)-py3-none-any\.whl$"
)
BUILD_CLOSURE_SCHEMA = 1
BUILDER_CONTRACT = "policy-pep517-hatchling-v1"
SUPPORTED_BACKEND = "hatchling.build"
SUPPORTED_BUILD_REQUIREMENTS = ("hatchling>=1.25",)
MAX_WHEEL_BYTES = 32 * 1024 * 1024


class BuildClosureError(ValueError):
    """Raised when a reviewed build closure is incomplete or mismatched."""


@dataclass(frozen=True)
class BuildArtifact:
    name: str
    version: str
    filename: str
    url: str
    sha256: str


@dataclass(frozen=True)
class BuildClosure:
    builder_contract: str
    python_requires: str
    backend: str
    build_system_requires: tuple[str, ...]
    dynamic_requires: tuple[str, ...]
    artifacts: tuple[BuildArtifact, ...]

    @property
    def artifact_by_name(self) -> dict[str, BuildArtifact]:
        return {normalize_name(item.name): item for item in self.artifacts}

    @property
    def backend_artifact(self) -> BuildArtifact:
        try:
            return self.artifact_by_name["hatchling"]
        except KeyError as exc:
            raise BuildClosureError("reviewed build closure omits Hatchling") from exc


def normalize_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise BuildClosureError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _require_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise BuildClosureError(f"{label} must be a non-empty string")
    return value


def parse_build_closure(data: bytes | str) -> BuildClosure:
    try:
        raw = data.decode("utf-8") if isinstance(data, bytes) else data
        document = json.loads(raw, object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BuildClosureError(f"build closure is invalid JSON: {exc}") from exc
    if not isinstance(document, dict):
        raise BuildClosureError("build closure must be a JSON object")
    expected_keys = {
        "schema_version",
        "builder_contract",
        "python_requires",
        "build_system",
        "artifacts",
    }
    if set(document) != expected_keys:
        raise BuildClosureError("build closure has missing or unsupported fields")
    if (
        type(document["schema_version"]) is not int
        or document["schema_version"] != BUILD_CLOSURE_SCHEMA
    ):
        raise BuildClosureError("unsupported build closure schema version")
    contract = _require_string(document["builder_contract"], "builder_contract")
    if contract != BUILDER_CONTRACT:
        raise BuildClosureError(f"unsupported builder contract: {contract}")
    python_requires = _require_string(document["python_requires"], "python_requires")
    if python_requires != ">=3.11":
        raise BuildClosureError("unsupported build-closure Python range")

    build_system = document["build_system"]
    if not isinstance(build_system, dict) or set(build_system) != {
        "backend",
        "requires",
        "dynamic_requires",
    }:
        raise BuildClosureError("build_system has missing or unsupported fields")
    backend = _require_string(build_system["backend"], "build_system.backend")
    if backend != SUPPORTED_BACKEND:
        raise BuildClosureError(f"unsupported PEP 517 backend: {backend}")
    requires = build_system["requires"]
    if (
        not isinstance(requires, list)
        or any(not isinstance(item, str) for item in requires)
        or tuple(requires) != SUPPORTED_BUILD_REQUIREMENTS
    ):
        raise BuildClosureError("build_system.requires does not match the reviewed contract")
    dynamic_requires = build_system["dynamic_requires"]
    if (
        not isinstance(dynamic_requires, list)
        or any(not isinstance(item, str) or not item for item in dynamic_requires)
    ):
        raise BuildClosureError("build_system.dynamic_requires must be a string array")

    raw_artifacts = document["artifacts"]
    if not isinstance(raw_artifacts, list) or not raw_artifacts:
        raise BuildClosureError("build closure must contain artifact records")
    artifacts: list[BuildArtifact] = []
    seen: set[str] = set()
    for index, raw_artifact in enumerate(raw_artifacts):
        label = f"artifacts[{index}]"
        if not isinstance(raw_artifact, dict) or set(raw_artifact) != {
            "name",
            "version",
            "filename",
            "url",
            "sha256",
        }:
            raise BuildClosureError(f"{label} has missing or unsupported fields")
        name = _require_string(raw_artifact["name"], f"{label}.name")
        version = _require_string(raw_artifact["version"], f"{label}.version")
        filename = _require_string(raw_artifact["filename"], f"{label}.filename")
        url = _require_string(raw_artifact["url"], f"{label}.url")
        digest = _require_string(raw_artifact["sha256"], f"{label}.sha256")
        normalized = normalize_name(name)
        if not VERSION.fullmatch(version):
            raise BuildClosureError(f"{label}.version is not an exact version")
        if normalized in seen:
            raise BuildClosureError(f"build closure duplicates artifact: {name}")
        seen.add(normalized)
        wheel_match = WHEEL_FILENAME.fullmatch(filename)
        if (
            wheel_match is None
            or normalize_name(wheel_match.group("distribution")) != normalized
            or wheel_match.group("version") != version
        ):
            raise BuildClosureError(f"{label}.filename does not identify its exact wheel")
        parts = urlsplit(url)
        if (
            parts.scheme != "https"
            or parts.hostname != "files.pythonhosted.org"
            or parts.username is not None
            or parts.password is not None
            or parts.query
            or parts.fragment
            or PurePosixPath(parts.path).name != filename
        ):
            raise BuildClosureError(f"{label}.url is not the direct reviewed wheel URL")
        if not SHA256.fullmatch(digest):
            raise BuildClosureError(f"{label}.sha256 is not lowercase SHA-256")
        artifacts.append(BuildArtifact(name, version, filename, url, digest))

    backend_artifacts = [item for item in artifacts if normalize_name(item.name) == "hatchling"]
    if len(backend_artifacts) != 1:
        raise BuildClosureError("build closure must bind exactly one Hatchling wheel")
    backend_requirement = requires[0]
    backend_name = backend_requirement.split(">", 1)[0]
    if normalize_name(backend_name) != "hatchling":
        raise BuildClosureError("reviewed build requirement does not name Hatchling")
    backend_version = backend_artifacts[0].version
    numeric_version = NUMERIC_RELEASE.fullmatch(backend_version)
    if numeric_version is None:
        raise BuildClosureError("reviewed Hatchling version is outside the supported range syntax")
    version_tuple = tuple(int(part or "0") for part in numeric_version.groups())
    if version_tuple < (1, 25, 0):
        raise BuildClosureError("reviewed Hatchling artifact does not satisfy hatchling>=1.25")

    return BuildClosure(
        builder_contract=contract,
        python_requires=python_requires,
        backend=backend,
        build_system_requires=tuple(requires),
        dynamic_requires=tuple(dynamic_requires),
        artifacts=tuple(artifacts),
    )


def validate_build_system(pyproject_data: bytes, closure: BuildClosure) -> None:
    try:
        import tomllib

        document = tomllib.loads(pyproject_data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise BuildClosureError(f"target pyproject.toml is malformed: {exc}") from exc
    build_system = document.get("build-system") if isinstance(document, dict) else None
    if not isinstance(build_system, dict):
        raise BuildClosureError("target pyproject.toml has no build-system table")
    if set(build_system) != {"requires", "build-backend"}:
        raise BuildClosureError("target build-system table has unsupported fields")
    requires = build_system.get("requires")
    backend = build_system.get("build-backend")
    if not isinstance(requires, list) or any(not isinstance(item, str) for item in requires):
        raise BuildClosureError("target build-system.requires must be a string array")
    if tuple(requires) != closure.build_system_requires:
        raise BuildClosureError("target build-system requirements differ from reviewed closure")
    if backend != closure.backend:
        raise BuildClosureError("target build backend differs from reviewed closure")


def verify_wheel_artifact(path: Path, artifact: BuildArtifact) -> None:
    if path.is_symlink() or not path.is_file():
        raise BuildClosureError(f"reviewed build artifact is missing or not a regular file: {path}")
    file_stat = path.stat(follow_symlinks=False)
    if file_stat.st_size < 1 or file_stat.st_size > MAX_WHEEL_BYTES:
        raise BuildClosureError(f"reviewed build artifact has an invalid size: {path}")
    if not stat.S_ISREG(file_stat.st_mode) or file_stat.st_nlink != 1:
        raise BuildClosureError(f"reviewed build artifact has an unsafe file type: {path}")
    if path.name != artifact.filename:
        raise BuildClosureError("staged build artifact filename does not match the lock")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != artifact.sha256:
        raise BuildClosureError(
            f"build artifact SHA-256 mismatch for {artifact.name}=={artifact.version}"
        )
    try:
        with zipfile.ZipFile(path) as wheel:
            infos = wheel.infolist()
            names = [info.filename for info in infos]
            if len(names) != len(set(names)):
                raise BuildClosureError("build wheel contains duplicate paths")
            for info in infos:
                relative = PurePosixPath(info.filename)
                mode = info.external_attr >> 16
                if (
                    relative.is_absolute()
                    or any(part in {"", ".", ".."} for part in relative.parts)
                    or "\\" in info.filename
                    or stat.S_ISLNK(mode)
                ):
                    raise BuildClosureError("build wheel contains an unsafe archive path")
            metadata_paths = [
                name for name in names if name.endswith(".dist-info/METADATA")
            ]
            wheel_paths = [name for name in names if name.endswith(".dist-info/WHEEL")]
            record_paths = [name for name in names if name.endswith(".dist-info/RECORD")]
            if (
                len(metadata_paths) != 1
                or len(wheel_paths) != 1
                or len(record_paths) != 1
                or metadata_paths[0].rsplit("/", 1)[0]
                != wheel_paths[0].rsplit("/", 1)[0]
                or metadata_paths[0].rsplit("/", 1)[0]
                != record_paths[0].rsplit("/", 1)[0]
            ):
                raise BuildClosureError(
                    "build wheel must contain one matching METADATA, WHEEL, and RECORD"
                )
            metadata = BytesParser(policy=default).parsebytes(wheel.read(metadata_paths[0]))
            wheel_metadata = BytesParser(policy=default).parsebytes(wheel.read(wheel_paths[0]))
    except (OSError, zipfile.BadZipFile, KeyError) as exc:
        raise BuildClosureError(f"reviewed build artifact is not a valid wheel: {path}") from exc
    if normalize_name(metadata.get("Name", "")) != normalize_name(artifact.name):
        raise BuildClosureError("build wheel metadata package name does not match the lock")
    if metadata.get("Version") != artifact.version:
        raise BuildClosureError("build wheel metadata version does not match the lock")
    if wheel_metadata.get("Root-Is-Purelib", "").lower() != "true":
        raise BuildClosureError("build wheel is not a pure Python wheel")
    if "py3-none-any" not in wheel_metadata.get_all("Tag", []):
        raise BuildClosureError("build wheel does not have the reviewed universal tag")
