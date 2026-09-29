"""Policy build-closure contract and artifact-integrity regressions."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CLOSURE_PATH = ROOT / "skills/agent-policy/build-closure.json"
MODULE_PATH = ROOT / "skills/agent-policy/scripts/build_closure.py"
SPEC = importlib.util.spec_from_file_location("policy_build_closure", MODULE_PATH)
assert SPEC and SPEC.loader
build_closure = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = build_closure
SPEC.loader.exec_module(build_closure)


def closure_document() -> dict[str, object]:
    return json.loads(CLOSURE_PATH.read_text(encoding="utf-8"))


def make_wheel(path: Path, *, code: bytes) -> bytes:
    dist_info = "hatchling-1.31.0.dist-info"
    metadata = b"Metadata-Version: 2.1\nName: hatchling\nVersion: 1.31.0\n\n"
    wheel_metadata = (
        b"Wheel-Version: 1.0\nGenerator: policy-test\nRoot-Is-Purelib: true\n"
        b"Tag: py3-none-any\n"
    )
    entries = {
        "hatchling/__init__.py": code,
        f"{dist_info}/METADATA": metadata,
        f"{dist_info}/WHEEL": wheel_metadata,
        f"{dist_info}/RECORD": b"hatchling/__init__.py,,\n",
    }
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, payload in entries.items():
            archive.writestr(name, payload)
    return path.read_bytes()


def test_checked_in_build_closure_binds_exact_backend_and_transitives() -> None:
    closure = build_closure.parse_build_closure(CLOSURE_PATH.read_bytes())

    assert closure.builder_contract == "policy-pep517-hatchling-v1"
    assert closure.python_requires == ">=3.11"
    assert closure.backend == "hatchling.build"
    assert closure.build_system_requires == ("hatchling>=1.25",)
    assert {item.name for item in closure.artifacts} == {
        "hatchling",
        "packaging",
        "pathspec",
        "pluggy",
        "trove-classifiers",
    }
    assert closure.backend_artifact.version == "1.31.0"
    assert all(item.url.startswith("https://files.pythonhosted.org/") for item in closure.artifacts)
    assert all(len(item.sha256) == 64 for item in closure.artifacts)


@pytest.mark.parametrize(
    "build_system",
    [
        {"requires": ["hatchling>=1.26"], "build-backend": "hatchling.build"},
        {"requires": ["hatchling>=1.25"], "build-backend": "setuptools.build_meta"},
        {
            "requires": ["hatchling>=1.25", "setuptools>=70"],
            "build-backend": "hatchling.build",
        },
        {
            "requires": ["hatchling>=1.25"],
            "build-backend": "hatchling.build",
            "backend-path": ["vendor"],
        },
    ],
)
def test_target_build_system_must_match_the_reviewed_contract(
    build_system: dict[str, object],
) -> None:
    closure = build_closure.parse_build_closure(CLOSURE_PATH.read_bytes())
    pyproject = (
        "[build-system]\n"
        f"requires = {json.dumps(build_system['requires'])}\n"
        f"build-backend = {json.dumps(build_system['build-backend'])}\n"
        + (
            f"backend-path = {json.dumps(build_system['backend-path'])}\n"
            if "backend-path" in build_system
            else ""
        )
    ).encode()

    with pytest.raises(build_closure.BuildClosureError):
        build_closure.validate_build_system(pyproject, closure)


@pytest.mark.parametrize(
    "pyproject",
    [
        b"[project]\nname='missing-build-system'\n",
        b"[build-system\nrequires = ['hatchling>=1.25']\n",
        b"[build-system]\nrequires = 'hatchling>=1.25'\nbuild-backend = 'hatchling.build'\n",
    ],
)
def test_malformed_or_missing_target_build_system_fails_closed(pyproject: bytes) -> None:
    closure = build_closure.parse_build_closure(CLOSURE_PATH.read_bytes())

    with pytest.raises(build_closure.BuildClosureError):
        build_closure.validate_build_system(pyproject, closure)


def test_build_closure_rejects_duplicate_json_keys_and_extra_fields() -> None:
    with pytest.raises(build_closure.BuildClosureError, match="duplicate JSON key"):
        build_closure.parse_build_closure(
            '{"schema_version":1,"schema_version":1}'
        )

    document = closure_document()
    document["index"] = "https://pypi.org/simple"
    with pytest.raises(build_closure.BuildClosureError, match="unsupported fields"):
        build_closure.parse_build_closure(json.dumps(document))


def test_build_closure_rejects_non_direct_or_mutable_artifact_urls() -> None:
    document = closure_document()
    artifacts = document["artifacts"]
    assert isinstance(artifacts, list)
    artifacts[0]["url"] = "https://pypi.org/simple/hatchling/"

    with pytest.raises(build_closure.BuildClosureError, match="direct reviewed wheel URL"):
        build_closure.parse_build_closure(json.dumps(document))


def test_build_closure_rejects_hatchling_version_below_declared_minimum() -> None:
    document = closure_document()
    artifacts = document["artifacts"]
    assert isinstance(artifacts, list)
    artifacts[0]["version"] = "1.24.0"
    artifacts[0]["filename"] = "hatchling-1.24.0-py3-none-any.whl"
    artifacts[0]["url"] = artifacts[0]["url"].replace(
        "hatchling-1.31.0-py3-none-any.whl",
        "hatchling-1.24.0-py3-none-any.whl",
    )

    with pytest.raises(build_closure.BuildClosureError, match="does not satisfy"):
        build_closure.parse_build_closure(json.dumps(document))


def test_wheel_with_matching_name_and_version_but_different_bytes_is_rejected(
    tmp_path: Path,
) -> None:
    expected = tmp_path / "hatchling-1.31.0-py3-none-any.whl"
    original_bytes = make_wheel(expected, code=b"# reviewed test backend\n")
    artifact = build_closure.BuildArtifact(
        name="hatchling",
        version="1.31.0",
        filename=expected.name,
        url=(
            "https://files.pythonhosted.org/packages/test/"
            "hatchling-1.31.0-py3-none-any.whl"
        ),
        sha256=hashlib.sha256(original_bytes).hexdigest(),
    )
    build_closure.verify_wheel_artifact(expected, artifact)

    substituted = tmp_path / "substituted"
    changed_bytes = make_wheel(substituted, code=b"# different executable bytes\n")
    substituted.rename(tmp_path / artifact.filename)
    with pytest.raises(build_closure.BuildClosureError, match="SHA-256 mismatch"):
        build_closure.verify_wheel_artifact(tmp_path / artifact.filename, artifact)
    assert changed_bytes != original_bytes


def test_missing_wheel_fails_closed(tmp_path: Path) -> None:
    artifact = build_closure.BuildArtifact(
        name="hatchling",
        version="1.31.0",
        filename="hatchling-1.31.0-py3-none-any.whl",
        url=(
            "https://files.pythonhosted.org/packages/test/"
            "hatchling-1.31.0-py3-none-any.whl"
        ),
        sha256="a" * 64,
    )

    with pytest.raises(build_closure.BuildClosureError, match="missing"):
        build_closure.verify_wheel_artifact(tmp_path / artifact.filename, artifact)


def test_wrong_backend_or_unpinned_transitive_artifact_is_rejected() -> None:
    document = closure_document()
    document["build_system"]["backend"] = "setuptools.build_meta"
    with pytest.raises(build_closure.BuildClosureError, match="unsupported PEP 517 backend"):
        build_closure.parse_build_closure(json.dumps(document))

    document = closure_document()
    document["artifacts"][1]["sha256"] = "not-a-digest"
    with pytest.raises(build_closure.BuildClosureError, match="lowercase SHA-256"):
        build_closure.parse_build_closure(json.dumps(document))
