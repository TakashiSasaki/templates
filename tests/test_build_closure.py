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


def make_wheel(path: Path, *, code: bytes, version: str = "1.31.0") -> bytes:
    dist_info = f"hatchling-{version}.dist-info"
    metadata = (
        f"Metadata-Version: 2.1\nName: hatchling\nVersion: {version}\n\n".encode()
    )
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


def test_checked_in_build_closure_binds_exact_frontend_backend_and_transitives() -> None:
    closure = build_closure.parse_build_closure(CLOSURE_PATH.read_bytes())

    assert closure.builder_contract == "policy-pep517-hatchling-v2"
    assert closure.python_requires == ">=3.11"
    assert closure.frontend.name == "pip"
    assert closure.frontend.version == "26.2.1"
    assert closure.frontend.filename == "pip-26.2.1-py3-none-any.whl"
    assert closure.frontend.sha256 == (
        "71138adf1f4ca900cdb7d289c21b7494329f2332b6d85f0e1c42108c0384ed3e"
    )
    assert closure.backend == "hatchling.build"
    assert closure.build_system_requires == ("hatchling>=1.25",)
    assert {item.name for item in closure.artifacts} == {
        "hatchling",
        "packaging",
        "pathspec",
        "pluggy",
        "trove-classifiers",
        "pip",
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
            '{"schema_version":2,"schema_version":2}'
        )

    document = closure_document()
    document["index"] = "https://pypi.org/simple"
    with pytest.raises(build_closure.BuildClosureError, match="unsupported fields"):
        build_closure.parse_build_closure(json.dumps(document))


def test_build_closure_requires_a_digest_bound_exact_pip_frontend() -> None:
    document = closure_document()
    document["frontend"]["version"] = "26.2.2"
    with pytest.raises(build_closure.BuildClosureError, match="exact pip frontend wheel"):
        build_closure.parse_build_closure(json.dumps(document))

    document = closure_document()
    document["frontend"]["name"] = "setuptools"
    with pytest.raises(build_closure.BuildClosureError, match="exact pip version"):
        build_closure.parse_build_closure(json.dumps(document))

    document = closure_document()
    document["artifacts"] = [
        item for item in document["artifacts"] if item["name"] != "pip"
    ]
    with pytest.raises(build_closure.BuildClosureError, match="exact pip frontend wheel"):
        build_closure.parse_build_closure(json.dumps(document))


def test_build_closure_binding_includes_frontend_artifact_digest() -> None:
    closure_data = CLOSURE_PATH.read_bytes()
    closure = build_closure.parse_build_closure(closure_data)

    assert build_closure.build_closure_binding(closure_data) == {
        "build_closure_sha256": hashlib.sha256(closure_data).hexdigest(),
        "backend_artifact_sha256": closure.backend_artifact.sha256,
        "build_frontend_artifact_sha256": closure.frontend.sha256,
        "builder_contract": closure.builder_contract,
    }


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


def test_hatchling_wheel_with_unexpected_version_metadata_is_rejected(
    tmp_path: Path,
) -> None:
    closure = build_closure.parse_build_closure(CLOSURE_PATH.read_bytes())
    artifact = closure.backend_artifact
    path = tmp_path / artifact.filename
    payload = make_wheel(path, code=b"# test backend\n", version="1.32.0")
    path.write_bytes(payload)
    mismatched = build_closure.BuildArtifact(
        name=artifact.name,
        version=artifact.version,
        filename=artifact.filename,
        url=artifact.url,
        sha256=hashlib.sha256(payload).hexdigest(),
    )

    with pytest.raises(build_closure.BuildClosureError, match="metadata version"):
        build_closure.verify_wheel_artifact(path, mismatched)


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
