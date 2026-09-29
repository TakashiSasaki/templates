"""Build the pinned Policy toolchain with its reviewed, digest-bound PEP 517 closure."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_closure import (  # noqa: E402, I001
    BUILD_RECORD_SCHEMA,
    BuildClosure,
    BuildClosureError,
    build_closure_binding,
    parse_build_closure,
    project_metadata_from_pyproject,
    validate_build_system,
    verify_project_wheel,
    verify_wheel_artifact,
)
from runtime import SKILL_ROOT, RuntimePin, select_pin  # noqa: E402

CLOSURE_PATH = SKILL_ROOT / "build-closure.json"
MAX_DOWNLOAD_BYTES = 32 * 1024 * 1024


def _runtime_environment(home: Path, temporary: Path) -> dict[str, str]:
    allowed = {
        "PATH",
        "LANG",
        "LC_ALL",
        "SYSTEMROOT",
        "WINDIR",
        "COMSPEC",
        "PATHEXT",
    }
    environment = {key: value for key, value in os.environ.items() if key in allowed}
    environment["HOME"] = str(home)
    environment["TMPDIR"] = str(temporary)
    environment["TMP"] = str(temporary)
    environment["TEMP"] = str(temporary)
    environment["PYTHONNOUSERSITE"] = "1"
    environment["PIP_CONFIG_FILE"] = os.devnull
    environment["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    environment["PIP_NO_INDEX"] = "1"
    environment["GIT_CONFIG_NOSYSTEM"] = "1"
    environment["GIT_CONFIG_GLOBAL"] = os.devnull
    environment["GIT_CONFIG_COUNT"] = "0"
    environment["GIT_TERMINAL_PROMPT"] = "0"
    return environment


def _run(command: list[str], environment: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=True,
        env=environment,
        capture_output=True,
        text=True,
    )


def _download_wheel(artifact: Any, directory: Path) -> Path:
    destination = directory / artifact.filename
    request = urllib.request.Request(
        artifact.url,
        headers={"Accept": "application/octet-stream", "User-Agent": "agent-policy-builder"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
        if response.geturl() != artifact.url:
            raise BuildClosureError("reviewed build wheel URL redirected")
        payload = response.read(MAX_DOWNLOAD_BYTES + 1)
    if len(payload) > MAX_DOWNLOAD_BYTES:
        raise BuildClosureError("reviewed build wheel exceeds the download size limit")
    with destination.open("xb") as stream:
        stream.write(payload)
    return destination


def _stage_and_verify_artifacts(closure: BuildClosure, directory: Path) -> list[Path]:
    staged = [_download_wheel(artifact, directory) for artifact in closure.artifacts]
    # Nothing is installed or imported until every reviewed input is present and verified.
    for artifact, path in zip(closure.artifacts, staged, strict=True):
        verify_wheel_artifact(path, artifact)
    return staged


def _verify_pre_staged_artifacts(closure: BuildClosure, directory: Path) -> list[Path]:
    if directory.is_symlink() or not directory.is_dir():
        raise BuildClosureError("pre-staged build wheelhouse is missing or unsafe")
    expected = {artifact.filename for artifact in closure.artifacts}
    actual = {path.name for path in directory.iterdir()}
    if actual != expected:
        raise BuildClosureError("pre-staged build wheelhouse does not match the reviewed closure")
    staged = [directory / artifact.filename for artifact in closure.artifacts]
    for artifact, path in zip(closure.artifacts, staged, strict=True):
        verify_wheel_artifact(path, artifact)
    return staged


def _fetch_toolchain(pin: RuntimePin, destination: Path, environment: dict[str, str]) -> None:
    destination.mkdir()
    _run(["git", "-C", str(destination), "init", "--quiet"], environment)
    _run(
        ["git", "-C", str(destination), "remote", "add", "origin", f"https://github.com/{pin.repository}.git"],
        environment,
    )
    _run(
        [
            "git",
            "-c",
            "credential.helper=",
            "-c",
            "core.askPass=",
            "-c",
            "http.followRedirects=false",
            "-C",
            str(destination),
            "fetch",
            "--no-tags",
            "--no-recurse-submodules",
            "--depth=1",
            "origin",
            pin.revision,
        ],
        environment,
    )
    _run(
        ["git", "-C", str(destination), "checkout", "--detach", "FETCH_HEAD"],
        environment,
    )
    result = _run(
        ["git", "-C", str(destination), "rev-parse", "HEAD"],
        environment,
    )
    if result.stdout.strip() != pin.revision:
        raise BuildClosureError("fetched toolchain checkout does not match the exact Git pin")
    _verify_toolchain_checkout(pin, destination, environment)


def _verify_toolchain_checkout(
    pin: RuntimePin,
    source: Path,
    environment: dict[str, str],
) -> None:
    expected_origin = f"https://github.com/{pin.repository}.git"
    origin = _run(
        ["git", "-C", str(source), "remote", "get-url", "origin"],
        environment,
    ).stdout.strip()
    revision = _run(
        ["git", "-C", str(source), "rev-parse", "HEAD"],
        environment,
    ).stdout.strip()
    status = _run(
        ["git", "-C", str(source), "status", "--porcelain", "--untracked-files=all"],
        environment,
    ).stdout
    if origin != expected_origin or revision != pin.revision or status:
        raise BuildClosureError("toolchain checkout is not a clean exact repository revision")


def _verify_installed_builder(
    python: Path,
    closure: BuildClosure,
    closure_data: bytes,
    config_path: Path,
    environment: dict[str, str],
) -> None:
    config_path.write_bytes(closure_data)
    script = r'''
import importlib, importlib.metadata, json, sys
from pathlib import Path
from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

document = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
expected = {canonicalize_name(item["name"]): item["version"] for item in document["artifacts"]}
installed = {
    canonicalize_name(dist.metadata["Name"]): dist.version
    for dist in importlib.metadata.distributions()
    if dist.metadata.get("Name")
}
for name, version in expected.items():
    if installed.get(name) != version:
        raise SystemExit(f"verified builder distribution mismatch: {name}")

edges = {name: set() for name in expected}
environment = default_environment()
for dist in importlib.metadata.distributions():
    raw_name = dist.metadata.get("Name")
    if not raw_name:
        continue
    name = canonicalize_name(raw_name)
    if name not in expected:
        continue
    for raw_requirement in dist.metadata.get_all("Requires-Dist", []):
        requirement = Requirement(raw_requirement)
        if requirement.marker is not None and not requirement.marker.evaluate(environment):
            continue
        dependency = canonicalize_name(requirement.name)
        if requirement.url or dependency not in expected:
            raise SystemExit(f"unclosed active build dependency: {raw_requirement}")
        version = expected[dependency]
        if requirement.specifier and not requirement.specifier.contains(
            version, prereleases=True
        ):
            raise SystemExit(
                "build dependency version is outside metadata constraint: "
                f"{raw_requirement}"
            )
        edges[name].add(dependency)

reachable = set()
pending = [canonicalize_name(document["frontend"]["name"]), "hatchling"]
while pending:
    current = pending.pop()
    if current in reachable:
        continue
    reachable.add(current)
    pending.extend(edges[current] - reachable)
if reachable != set(expected):
    raise SystemExit("reviewed build closure contains an unexpected or unreachable artifact")

backend = importlib.import_module("hatchling.build")
dynamic = backend.get_requires_for_build_wheel({})
if not isinstance(dynamic, list) or dynamic != document["build_system"]["dynamic_requires"]:
    raise SystemExit("Hatchling returned build requirements outside the reviewed closure")
'''
    _run([str(python), "-I", "-c", script, str(config_path)], environment)


def _install_verified_wheels(
    builder: Path,
    python: Path,
    wheels: list[Path],
    environment: dict[str, str],
) -> None:
    site_result = _run(
        [
            str(python),
            "-I",
            "-c",
            "import sysconfig; print(sysconfig.get_paths()['purelib'])",
        ],
        environment,
    )
    site_packages = Path(site_result.stdout.strip()).resolve(strict=False)
    if not site_packages.is_relative_to(builder.resolve()):
        raise BuildClosureError("disposable builder site-packages path escaped its venv")
    site_packages.mkdir(parents=True, exist_ok=True)
    for wheel_path in wheels:
        with zipfile.ZipFile(wheel_path) as wheel:
            for info in wheel.infolist():
                relative = PurePosixPath(info.filename)
                if relative.parts and relative.parts[0].endswith(".data"):
                    raise BuildClosureError("reviewed build wheels may not contain .data layouts")
                destination = site_packages.joinpath(*relative.parts)
                if info.is_dir():
                    destination.mkdir(parents=True, exist_ok=True)
                    continue
                destination.parent.mkdir(parents=True, exist_ok=True)
                with destination.open("xb") as stream:
                    stream.write(wheel.read(info))


def prepare_runtime_wheel(
    target_repository: Path | None,
    output_directory: Path,
    *,
    closure_path: Path = CLOSURE_PATH,
    selected_pin: RuntimePin | None = None,
    target_base_sha: str | None = None,
    pre_staged_directory: Path | None = None,
    source_checkout: Path | None = None,
) -> dict[str, Any]:
    if sys.version_info < (3, 11):  # noqa: UP036 - enforce the reviewed builder contract
        raise BuildClosureError("Policy's reviewed build closure requires Python >=3.11")
    if selected_pin is None:
        if target_repository is None:
            raise BuildClosureError("a target repository is required to select the toolchain pin")
        target_repository = target_repository.expanduser().resolve(strict=True)
    if output_directory.exists() or output_directory.is_symlink():
        raise BuildClosureError("prebuilt wheel output directory must be new")
    output_directory.parent.mkdir(parents=True, exist_ok=True)

    pin = selected_pin if selected_pin is not None else select_pin(target_repository)
    if target_base_sha is not None and re.fullmatch(r"[0-9a-f]{40}", target_base_sha) is None:
        raise BuildClosureError("target base must be a full lowercase Git commit SHA")
    if (pre_staged_directory is None) != (source_checkout is None):
        raise BuildClosureError(
            "pre-staged builds require both a verified wheelhouse and exact toolchain checkout"
        )
    closure_data = closure_path.read_bytes()
    closure = parse_build_closure(closure_data)
    binding = build_closure_binding(closure_data)

    with tempfile.TemporaryDirectory(
        prefix="agent-policy-build-", dir=output_directory.parent
    ) as temporary_name:
        temporary = Path(temporary_name)
        home = temporary / "home"
        home.mkdir()
        env = _runtime_environment(home, temporary)

        if pre_staged_directory is None:
            artifact_directory = temporary / "build-wheelhouse"
            artifact_directory.mkdir()
            staged_artifacts = _stage_and_verify_artifacts(closure, artifact_directory)
        else:
            staged_artifacts = _verify_pre_staged_artifacts(
                closure,
                pre_staged_directory.expanduser(),
            )

        if source_checkout is None:
            source = temporary / "toolchain"
            _fetch_toolchain(pin, source, env)
        else:
            source = source_checkout.expanduser().resolve(strict=True)
            _verify_toolchain_checkout(pin, source, env)
        pyproject_data = (source / "pyproject.toml").read_bytes()
        validate_build_system(pyproject_data, closure)
        project_name, project_version = project_metadata_from_pyproject(pyproject_data)
        if (
            project_name.lower().replace("_", "-")
            != pin.project_distribution.lower().replace("_", "-")
        ):
            raise BuildClosureError(
                "toolchain project name does not match the Policy runtime contract"
            )
        if pin.project_version is not None and project_version != pin.project_version:
            raise BuildClosureError(
                "toolchain project version does not match the Policy runtime manifest"
            )

        builder = temporary / "builder-venv"
        _run(
            [sys.executable, "-I", "-m", "venv", "--without-pip", str(builder)],
            env,
        )
        builder_python = builder / (
            "Scripts/python.exe" if os.name == "nt" else "bin/python"
        )
        if not builder_python.is_file():
            raise BuildClosureError("disposable builder Python executable is missing")
        _install_verified_wheels(builder, builder_python, staged_artifacts, env)
        _verify_installed_builder(
            builder_python,
            closure,
            closure_data,
            temporary / "build-closure.json",
            env,
        )

        output_directory.mkdir()
        _run(
            [
                str(builder_python),
                "-I",
                "-m",
                "pip",
                "wheel",
                "--disable-pip-version-check",
                "--no-index",
                "--no-deps",
                "--no-cache-dir",
                "--no-build-isolation",
                "--no-input",
                "--wheel-dir",
                str(output_directory),
                str(source),
            ],
            env,
        )
        wheels = list(output_directory.glob("*.whl"))
        if len(wheels) != 1:
            raise BuildClosureError("Policy toolchain build must produce exactly one wheel")
        wheel_path = wheels[0]
        verify_project_wheel(
            wheel_path,
            expected_name=project_name,
            expected_version=project_version,
        )
        record = {
            "schema_version": BUILD_RECORD_SCHEMA,
            "repository": pin.repository,
            "revision": pin.revision,
            "target_base_sha": target_base_sha,
            **binding,
            "pyproject_sha256": hashlib.sha256(pyproject_data).hexdigest(),
            "project": {"name": project_name, "version": project_version},
            "wheel": {
                "filename": wheel_path.name,
                "sha256": hashlib.sha256(wheel_path.read_bytes()).hexdigest(),
            },
        }
        record_path = output_directory / "build-record.json"
        record_path.write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-repository", required=True, type=Path)
    parser.add_argument("--output-directory", required=True, type=Path)
    parser.add_argument("--target-base-sha")
    parser.add_argument("--pre-staged-artifacts", type=Path)
    parser.add_argument("--toolchain-checkout", type=Path)
    args = parser.parse_args()
    try:
        record = prepare_runtime_wheel(
            args.target_repository,
            args.output_directory,
            target_base_sha=args.target_base_sha,
            pre_staged_directory=args.pre_staged_artifacts,
            source_checkout=args.toolchain_checkout,
        )
    except (BuildClosureError, OSError, subprocess.CalledProcessError) as exc:
        if isinstance(exc, subprocess.CalledProcessError) and exc.stderr:
            print(exc.stderr, file=sys.stderr, end="")
        print(f"Policy toolchain wheel preparation failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
