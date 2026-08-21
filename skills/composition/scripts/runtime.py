from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

CANONICAL_REPOSITORY = "TakashiSasaki/templates"
CANONICAL_REMOTE = f"https://github.com/{CANONICAL_REPOSITORY}.git"
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
EXACT_REQUIREMENT = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9_.-]*===([A-Za-z0-9][A-Za-z0-9_.+!-]*)$"
)
SUPPORTED_MIN = (3, 11)
SUPPORTED_MAX_EXCLUSIVE = (3, 15)
SKILL_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = SKILL_ROOT / "runtime-manifest.json"


class RunnerError(RuntimeError):
    pass


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON member: {key}")
        result[key] = value
    return result


def read_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_unique_object,
        )
    except (OSError, UnicodeError, ValueError) as exc:
        raise RunnerError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise RunnerError(f"{label} must be a JSON object")
    return value


def load_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    manifest = read_json_object(path, "Composition runtime manifest")
    if set(manifest) != {"schema_version", "toolchain", "runtime_lock", "entrypoint"}:
        raise RunnerError("Composition runtime manifest has unsupported members")
    if type(manifest["schema_version"]) is not int or manifest["schema_version"] != 1:
        raise RunnerError("unsupported Composition runtime manifest schema")
    toolchain = manifest["toolchain"]
    runtime_lock = manifest["runtime_lock"]
    if not isinstance(toolchain, dict) or set(toolchain) != {"repository", "revision"}:
        raise RunnerError("Composition runtime manifest toolchain is invalid")
    if toolchain["repository"] != CANONICAL_REPOSITORY:
        raise RunnerError("Composition runtime manifest repository is unsupported")
    revision = toolchain["revision"]
    if not isinstance(revision, str) or FULL_SHA.fullmatch(revision) is None:
        raise RunnerError("Composition runtime manifest revision must be a full SHA")
    if not isinstance(runtime_lock, dict) or set(runtime_lock) != {"path", "sha256"}:
        raise RunnerError("Composition runtime manifest runtime_lock is invalid")
    if runtime_lock["path"] != "requirements-runtime.lock":
        raise RunnerError("Composition runtime manifest lock path is unsupported")
    digest = runtime_lock["sha256"]
    if not isinstance(digest, str) or SHA256.fullmatch(digest) is None:
        raise RunnerError("Composition runtime manifest lock digest must be SHA-256")
    if manifest["entrypoint"] != "scripts/compose.py":
        raise RunnerError("Composition runtime manifest entrypoint is unsupported")
    return manifest


def stable_revision(manifest: Mapping[str, Any] | None = None) -> str:
    value = load_manifest() if manifest is None else manifest
    toolchain = value["toolchain"]
    assert isinstance(toolchain, dict)
    revision = toolchain["revision"]
    assert isinstance(revision, str)
    return revision


def verify_host_python() -> None:
    if sys.implementation.name != "cpython":
        raise RunnerError("Composition runner requires CPython")
    version = sys.version_info[:2]
    if not (SUPPORTED_MIN <= version < SUPPORTED_MAX_EXCLUSIVE):
        raise RunnerError(
            f"unsupported CPython {version[0]}.{version[1]}; "
            "supported versions are 3.11 through 3.14"
        )


def _source_revision(value: Any, label: str) -> str:
    if not isinstance(value, dict) or set(value) != {"repository", "revision"}:
        raise RunnerError(f"{label}.source must contain repository and revision")
    if value["repository"] != CANONICAL_REPOSITORY:
        raise RunnerError(f"{label}.source.repository is unsupported")
    revision = value["revision"]
    if not isinstance(revision, str) or FULL_SHA.fullmatch(revision) is None:
        raise RunnerError(f"{label}.source.revision must be a full lowercase SHA")
    return revision


def transaction_revision(repository: Path) -> str | None:
    metadata = repository / ".template-composition"
    if metadata.is_symlink():
        raise RunnerError("Composition metadata directory must not be a symbolic link")
    path = metadata / "transaction.json"
    if not path.exists() and not path.is_symlink():
        return None
    if path.is_symlink() or not path.is_file():
        raise RunnerError("Composition transaction metadata must be a regular file")
    value = read_json_object(path, "Composition transaction")
    schema_version = value.get("schema_version")
    if type(schema_version) is not int or schema_version != 1:
        raise RunnerError("unsupported Composition transaction schema")
    operation = value.get("operation")
    if not isinstance(operation, str) or operation not in {"update", "upgrade"}:
        raise RunnerError("Composition transaction operation is invalid")
    if "source" not in value:
        raise RunnerError("Composition transaction is missing source metadata")
    return _source_revision(value["source"], "transaction")


def select_revision(
    repository: Path,
    explicit_revision: str | None = None,
    manifest: Mapping[str, Any] | None = None,
) -> str:
    if explicit_revision is not None and FULL_SHA.fullmatch(explicit_revision) is None:
        raise RunnerError("--revision must be a full lowercase 40-character commit SHA")
    recovery = transaction_revision(repository)
    if recovery is not None:
        if explicit_revision is not None and explicit_revision != recovery:
            raise RunnerError(
                "managed recovery requires the exact transaction source revision "
                f"{recovery}; refusing explicit revision {explicit_revision}"
            )
        return recovery
    return explicit_revision or stable_revision(manifest)


def sanitized_environment(
    source: Mapping[str, str] | None = None,
) -> dict[str, str]:
    supplied = os.environ if source is None else source
    result = {
        key: value
        for key, value in supplied.items()
        if not key.upper().startswith("PIP_")
        and not key.upper().startswith("PYTHON")
    }
    result["PYTHONNOUSERSITE"] = "1"
    result["PIP_CONFIG_FILE"] = os.devnull
    result["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    return result


def run(
    command: Sequence[str],
    *,
    cwd: Path | None = None,
    env: Mapping[str, str],
    capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            list(command),
            cwd=cwd,
            env=dict(env),
            check=True,
            text=True,
            capture_output=capture_output,
        )
    except OSError as exc:
        raise RunnerError(f"cannot execute {command[0]}: {exc}") from exc
    except subprocess.CalledProcessError as exc:
        detail = ""
        if capture_output and exc.stderr:
            detail = f": {exc.stderr.strip()}"
        raise RunnerError(
            f"command failed with exit {exc.returncode}: {' '.join(command)}{detail}"
        ) from exc


def parse_runtime_lock(text: str) -> dict[str, str]:
    requirements: dict[str, str] = {}
    for line_number, raw in enumerate(text.splitlines(), 1):
        value = raw.strip()
        if not value or value.startswith("#"):
            continue
        if EXACT_REQUIREMENT.fullmatch(value) is None:
            raise RunnerError(
                f"requirements-runtime.lock:{line_number}: "
                "entry must be exact name===version"
            )
        name, version = value.split("===", 1)
        normalized = re.sub(r"[-_.]+", "-", name).lower()
        if normalized in requirements:
            raise RunnerError(
                f"requirements-runtime.lock contains duplicate distribution {name!r}"
            )
        requirements[normalized] = version
    if not requirements:
        raise RunnerError("requirements-runtime.lock must not be empty")
    return requirements


def materialize_source(revision: str, root: Path, env: Mapping[str, str]) -> Path:
    if shutil.which("git") is None:
        raise RunnerError("Composition runner requires Git on PATH")
    source = root / "source"
    run(["git", "init", "--quiet", str(source)], env=env)
    run(
        ["git", "-C", str(source), "remote", "add", "origin", CANONICAL_REMOTE],
        env=env,
    )
    run(
        [
            "git",
            "-C",
            str(source),
            "fetch",
            "--quiet",
            "--no-tags",
            "origin",
            revision,
        ],
        env=env,
    )
    run(
        ["git", "-C", str(source), "checkout", "--quiet", "--detach", "FETCH_HEAD"],
        env=env,
    )
    actual = run(
        ["git", "-C", str(source), "rev-parse", "HEAD"],
        env=env,
        capture_output=True,
    ).stdout.strip()
    if actual != revision:
        raise RunnerError(
            f"fetched Composition revision mismatch: expected {revision}, got {actual}"
        )
    return source


def verify_default_lock(
    source: Path,
    revision: str,
    manifest: Mapping[str, Any],
) -> bytes:
    lock = source / "requirements-runtime.lock"
    try:
        data = lock.read_bytes()
    except OSError as exc:
        raise RunnerError(f"cannot read fetched requirements-runtime.lock: {exc}") from exc
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RunnerError("requirements-runtime.lock must be UTF-8") from exc
    parse_runtime_lock(text)
    default_revision = stable_revision(manifest)
    if revision == default_revision:
        runtime_lock = manifest["runtime_lock"]
        assert isinstance(runtime_lock, dict)
        expected = runtime_lock["sha256"]
        assert isinstance(expected, str)
        actual = hashlib.sha256(data).hexdigest()
        if actual != expected:
            raise RunnerError(
                "stable runtime lock digest mismatch: "
                f"expected {expected}, got {actual}"
            )
    return data


def venv_python(root: Path) -> Path:
    if os.name == "nt":
        return root / "venv" / "Scripts" / "python.exe"
    return root / "venv" / "bin" / "python"


def build_runtime(source: Path, root: Path, env: Mapping[str, str]) -> Path:
    lock = source / "requirements-runtime.lock"
    run(
        [sys.executable, "-I", "-m", "venv", str(root / "venv")],
        env=env,
    )
    python = venv_python(root)
    run(
        [
            str(python),
            "-I",
            "-m",
            "pip",
            "install",
            "--isolated",
            "--disable-pip-version-check",
            "--no-deps",
            "--requirement",
            str(lock),
        ],
        env=env,
    )
    run([str(python), "-I", "-m", "pip", "check"], env=env)
    run(
        [str(python), "-I", str(source / "scripts" / "verify_runtime_environment.py")],
        cwd=source,
        env=env,
    )
    return python


def run_composer(
    repository: Path,
    arguments: Sequence[str],
    *,
    explicit_revision: str | None = None,
) -> int:
    verify_host_python()
    manifest = load_manifest()
    revision = select_revision(repository, explicit_revision, manifest)
    env = sanitized_environment()
    with tempfile.TemporaryDirectory(prefix="composition-runner-") as temporary:
        root = Path(temporary)
        source = materialize_source(revision, root, env)
        verify_default_lock(source, revision, manifest)
        python = build_runtime(source, root, env)
        command = [
            str(python),
            "-I",
            str(source / manifest["entrypoint"]),
            *arguments,
            "--target",
            str(repository),
        ]
        try:
            completed = subprocess.run(
                command,
                cwd=source,
                env=env,
                check=False,
            )
        except OSError as exc:
            raise RunnerError(f"cannot execute Composition Composer: {exc}") from exc
        return completed.returncode
