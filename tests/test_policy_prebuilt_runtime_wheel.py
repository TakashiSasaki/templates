"""Process-level regressions for the offline, pre-staged Policy wheel build."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
import zipfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/agent-policy"
BUILDER = SKILL / "scripts/prepare_runtime_wheel.py"
REPOSITORY_URL = "https://github.com/TakashiSasaki/templates.git"


def _wheel(
    name: str,
    version: str,
    files: dict[str, bytes],
    requirements: tuple[str, ...] = (),
) -> bytes:
    normalized = name.replace("-", "_").replace(".", "_")
    dist_info = f"{normalized}-{version}.dist-info"
    metadata = (
        "Metadata-Version: 2.1\n"
        f"Name: {name}\n"
        f"Version: {version}\n"
        + "".join(f"Requires-Dist: {item}\n" for item in requirements)
        + "\n"
    ).encode()
    entries = dict(files)
    entries[f"{dist_info}/METADATA"] = metadata
    entries[f"{dist_info}/WHEEL"] = (
        b"Wheel-Version: 1.0\nGenerator: policy-test\n"
        b"Root-Is-Purelib: true\nTag: py3-none-any\n"
    )
    entries[f"{dist_info}/RECORD"] = b""
    import io

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        for path, payload in sorted(entries.items()):
            archive.writestr(path, payload)
    return buffer.getvalue()


def _installed_pip_wheel() -> tuple[str, str, bytes]:
    distribution = importlib.metadata.distribution("pip")
    entries: dict[str, bytes] = {}
    for item in distribution.files or ():
        relative = str(item).replace("\\", "/")
        if not (
            relative.startswith("pip/")
            or relative.startswith(f"pip-{distribution.version}.dist-info/")
        ):
            continue
        if relative.endswith(".pyc") or "/__pycache__/" in relative:
            continue
        source = distribution.locate_file(item)
        if source.is_file():
            entries[relative] = source.read_bytes()
    import io

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        for path, payload in sorted(entries.items()):
            archive.writestr(path, payload)
    filename = f"pip-{distribution.version}-py3-none-any.whl"
    return distribution.version, filename, buffer.getvalue()


def _fixture(
    tmp_path: Path,
    *,
    unclosed_dependency: bool = False,
    wrong_dependency_version: bool = False,
) -> dict[str, Path]:
    policy_skill = tmp_path / "policy-skill"
    scripts = policy_skill / "scripts"
    scripts.mkdir(parents=True)
    for name in ("runtime.py", "build_closure.py", "prepare_runtime_wheel.py"):
        shutil.copy2(SKILL / "scripts" / name, scripts / name)
    shutil.copy2(SKILL / "runtime-manifest.json", policy_skill / "runtime-manifest.json")

    dependency_files: dict[str, dict[str, bytes]] = {
        "packaging": {
            "packaging/__init__.py": b"",
            "packaging/utils.py": (
                b"import re\ndef canonicalize_name(name): "
                b"return re.sub(r'[-_.]+', '-', name).lower()\n"
            ),
            "packaging/markers.py": b"def default_environment(): return {}\n",
            "packaging/requirements.py": (
                b"import re\n"
                b"class Specifier:\n"
                b" def __init__(self, value): self.value=value\n"
                b" def contains(self, version, prereleases=True):\n"
                b"  if not self.value: return True\n"
                b"  match=re.fullmatch(r'>=([0-9.]+)', self.value)\n"
                b"  if not match: return False\n"
                b"  parts=lambda v: tuple(int(p) for p in v.split('.'))\n"
                b"  return parts(version) >= parts(match.group(1))\n"
                b"class Requirement:\n"
                b" def __init__(self, value):\n"
                b"  match=re.fullmatch(r'([A-Za-z0-9_.-]+)(.*)', value)\n"
                b"  self.name=match.group(1); self.specifier=Specifier(match.group(2))\n"
                b"  self.url=None; self.marker=None\n"
            ),
        },
        "pathspec": {"pathspec/__init__.py": b""},
        "pluggy": {"pluggy/__init__.py": b""},
        "trove-classifiers": {"trove_classifiers/__init__.py": b""},
    }
    backend = b'''from pathlib import Path
import json, os, tomllib, zipfile

def get_requires_for_build_wheel(config_settings=None):
    return []

def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    source = Path.cwd()
    project = tomllib.loads((source / "pyproject.toml").read_text())["project"]
    name = project["name"]
    version = project["version"]
    filename = name.replace("-", "_") + f"-{version}-py3-none-any.whl"
    info = name.replace("-", "_") + f"-{version}.dist-info"
    metadata = f"Metadata-Version: 2.1\\nName: {name}\\nVersion: {version}\\n\\n".encode()
    entries = {
        "agent_policy/__init__.py": b"POLICY_BUILD_WHEEL = True\\n",
        info + "/METADATA": metadata,
        info + "/WHEEL": b"Wheel-Version: 1.0\\nRoot-Is-Purelib: true\\nTag: py3-none-any\\n",
        info + "/RECORD": b"",
    }
    with zipfile.ZipFile(Path(wheel_directory) / filename, "w") as archive:
        for path, payload in entries.items():
            archive.writestr(path, payload)
    (source / "backend-executed.json").write_text(json.dumps({
        "github_token": "GITHUB_TOKEN" in os.environ,
        "gh_token": "GH_TOKEN" in os.environ,
        "oidc_token": "ACTIONS_ID_TOKEN_REQUEST_TOKEN" in os.environ,
        "index_url": "PIP_INDEX_URL" in os.environ,
        "no_index": os.environ.get("PIP_NO_INDEX"),
    }))
    return filename
'''
    dependency_files["hatchling"] = {
        "hatchling/__init__.py": b"",
        "hatchling/build.py": backend,
    }
    requirements = (
        "packaging>=1",
        "pathspec>=1",
        "pluggy>=1",
        "trove-classifiers>=1",
    )
    if unclosed_dependency:
        requirements += ("unlisted-build-helper>=1",)
    if wrong_dependency_version:
        requirements = ("packaging>=999", *requirements[1:])

    names_versions = {
        "hatchling": "1.31.0",
        "packaging": "26.2",
        "pathspec": "1.1.1",
        "pluggy": "1.6.0",
        "trove-classifiers": "2026.6.1.19",
    }
    artifacts: list[dict[str, str]] = []
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    for name, version in names_versions.items():
        filename = f"{name.replace('-', '_')}-{version}-py3-none-any.whl"
        needs = requirements if name == "hatchling" else ()
        payload = _wheel(name, version, dependency_files[name], needs)
        (wheelhouse / filename).write_bytes(payload)
        artifacts.append(
            {
                "name": name,
                "version": version,
                "filename": filename,
                "url": f"https://files.pythonhosted.org/packages/test/{filename}",
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
    pip_version, pip_filename, pip_payload = _installed_pip_wheel()
    (wheelhouse / pip_filename).write_bytes(pip_payload)
    artifacts.append(
        {
            "name": "pip",
            "version": pip_version,
            "filename": pip_filename,
            "url": f"https://files.pythonhosted.org/packages/test/{pip_filename}",
            "sha256": hashlib.sha256(pip_payload).hexdigest(),
        }
    )
    closure = {
        "schema_version": 2,
        "builder_contract": "policy-pep517-hatchling-v2",
        "python_requires": ">=3.11",
        "frontend": {"name": "pip", "version": pip_version},
        "build_system": {
            "backend": "hatchling.build",
            "requires": ["hatchling>=1.25"],
            "dynamic_requires": [],
        },
        "artifacts": artifacts,
    }
    (policy_skill / "build-closure.json").write_text(
        json.dumps(closure, indent=2) + "\n", encoding="utf-8"
    )

    source = tmp_path / "source"
    source.mkdir()
    (source / "pyproject.toml").write_text(
        '[build-system]\nrequires = ["hatchling>=1.25"]\n'
        'build-backend = "hatchling.build"\n\n'
        '[project]\nname = "takashisasaki-agent-policy"\n'
        'version = "0.1.0"\nrequires-python = ">=3.11"\n',
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "--quiet", str(source)], check=True)
    subprocess.run(["git", "-C", str(source), "config", "user.name", "Policy Test"], check=True)
    subprocess.run(
        ["git", "-C", str(source), "config", "user.email", "policy-test@example.invalid"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(source), "remote", "add", "origin", REPOSITORY_URL],
        check=True,
    )
    subprocess.run(["git", "-C", str(source), "add", "pyproject.toml"], check=True)
    subprocess.run(["git", "-C", str(source), "commit", "--quiet", "-m", "fixture"], check=True)
    revision = subprocess.run(
        ["git", "-C", str(source), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    target = tmp_path / "target"
    target.mkdir()
    (target / ".agent-policy.lock").write_text(
        "lock_version: 1\ntoolchain:\n"
        "  repository: TakashiSasaki/templates\n"
        f"  revision: {revision}\n",
        encoding="utf-8",
    )
    return {
        "builder": scripts / "prepare_runtime_wheel.py",
        "policy_skill": policy_skill,
        "source": source,
        "target": target,
        "wheelhouse": wheelhouse,
        "revision": Path(revision),
    }


class _IndexProbe(BaseHTTPRequestHandler):
    requests = 0

    def do_GET(self) -> None:
        type(self).requests += 1
        self.send_response(404)
        self.end_headers()

    def log_message(self, _format: str, *_args: Any) -> None:
        return


def _run_builder(
    fixture: dict[str, Path],
    output: Path,
    *,
    wheelhouse: Path | None = None,
    index_url: str = "http://127.0.0.1:1/simple",
) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    environment["PIP_INDEX_URL"] = index_url
    environment["GH_TOKEN"] = "must-not-reach-backend"
    environment["GITHUB_TOKEN"] = "must-not-reach-backend"
    environment["ACTIONS_ID_TOKEN_REQUEST_TOKEN"] = "must-not-reach-backend"
    command = [
        sys.executable,
        "-I",
        str(fixture["builder"]),
        "--target-repository",
        str(fixture["target"]),
        "--output-directory",
        str(output),
        "--target-base-sha",
        "c" * 40,
        "--pre-staged-artifacts",
        str(wheelhouse or fixture["wheelhouse"]),
        "--toolchain-checkout",
        str(fixture["source"]),
    ]
    return subprocess.run(
        command,
        check=False,
        env=environment,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_pre_staged_cli_builds_project_offline_without_an_isolated_backend(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    _IndexProbe.requests = 0
    server = HTTPServer(("127.0.0.1", 0), _IndexProbe)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        output = tmp_path / "output"
        result = _run_builder(
            fixture,
            output,
            index_url=f"http://127.0.0.1:{server.server_port}/simple",
        )
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()

    assert result.returncode == 0, result.stderr
    assert _IndexProbe.requests == 0
    record = json.loads((output / "build-record.json").read_text(encoding="utf-8"))
    assert record["revision"] == fixture["revision"].name
    assert record["target_base_sha"] == "c" * 40
    assert record["backend_artifact_sha256"] == next(
        item["sha256"]
        for item in json.loads(
            (fixture["policy_skill"] / "build-closure.json").read_text(encoding="utf-8")
        )["artifacts"]
        if item["name"] == "hatchling"
    )
    marker = json.loads(
        (fixture["source"] / "backend-executed.json").read_text(encoding="utf-8")
    )
    assert marker == {
        "github_token": False,
        "gh_token": False,
        "oidc_token": False,
        "index_url": False,
        "no_index": "1",
    }
    assert len(list(output.glob("*.whl"))) == 1


@pytest.mark.parametrize("failure", ["missing", "altered"])
def test_pre_staged_cli_fails_closed_before_backend_on_missing_or_altered_wheel(
    tmp_path: Path,
    failure: str,
) -> None:
    fixture = _fixture(tmp_path)
    bad_wheelhouse = tmp_path / f"{failure}-wheelhouse"
    shutil.copytree(fixture["wheelhouse"], bad_wheelhouse)
    hatchling = next(bad_wheelhouse.glob("hatchling-*.whl"))
    if failure == "missing":
        hatchling.unlink()
    else:
        hatchling.write_bytes(hatchling.read_bytes() + b"tampered")

    result = _run_builder(fixture, tmp_path / "output", wheelhouse=bad_wheelhouse)

    assert result.returncode != 0
    assert "pre-staged build wheelhouse" in result.stderr or "SHA-256 mismatch" in result.stderr
    assert not (fixture["source"] / "backend-executed.json").exists()


@pytest.mark.parametrize(
    ("fixture_options", "message"),
    [
        ({"unclosed_dependency": True}, "unclosed active build dependency"),
        ({"wrong_dependency_version": True}, "outside metadata constraint"),
    ],
)
def test_pre_staged_cli_rejects_unsupported_transitive_build_dependency(
    tmp_path: Path,
    fixture_options: dict[str, bool],
    message: str,
) -> None:
    fixture = _fixture(tmp_path, **fixture_options)
    result = _run_builder(fixture, tmp_path / "output")

    assert result.returncode != 0
    assert message in result.stderr
    assert not (fixture["source"] / "backend-executed.json").exists()
