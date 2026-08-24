from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
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
CACHE_SCHEMA = 1
CACHE_OVERRIDE = "COMPOSITION_RUNTIME_CACHE"


class RunnerError(RuntimeError):
    pass


@dataclass(frozen=True)
class RuntimeIdentity:
    repository: str
    revision: str
    lock_sha256: str
    python: str
    platform: str

    def payload(self) -> dict[str, str]:
        return {
            "repository": self.repository,
            "revision": self.revision,
            "lock_sha256": self.lock_sha256,
            "python": self.python,
            "platform": self.platform,
        }

    def digest(self) -> str:
        encoded = json.dumps(
            self.payload(), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


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


def python_token() -> str:
    return f"{sys.version_info.major}.{sys.version_info.minor}"


def platform_token() -> str:
    machine = platform.machine().lower() or "unknown"
    return f"{sys.platform}-{machine}"


def cache_root() -> Path:
    override = os.environ.get(CACHE_OVERRIDE)
    if override:
        return Path(override).expanduser().resolve()
    if os.name == "nt":
        local = os.environ.get("LOCALAPPDATA")
        base = Path(local) if local else Path.home() / ".cache"
    else:
        xdg = os.environ.get("XDG_CACHE_HOME")
        base = Path(xdg) if xdg else Path.home() / ".cache"
    return base / "composition" / "runner-v1"


def cache_write_error(path: Path, exc: OSError) -> RunnerError:
    return RunnerError(
        f"Composition runtime cache is unusable at {path}: {exc}. "
        f"Set {CACHE_OVERRIDE} to a writable directory."
    )


def ensure_cache_parent(parent: Path) -> None:
    """Verify that a cache parent supports the writes and atomic rename we require."""
    probe: Path | None = None
    renamed: Path | None = None
    try:
        parent.mkdir(parents=True, exist_ok=True)
        probe = Path(tempfile.mkdtemp(prefix=".composition-write-probe-", dir=parent))
        (probe / "probe").write_text("ok\n", encoding="utf-8")
        renamed = probe.with_name(f"{probe.name}.renamed")
        probe.rename(renamed)
        probe = None
        remove_path(renamed)
        renamed = None
    except OSError as exc:
        if probe is not None:
            remove_path(probe)
        if renamed is not None:
            remove_path(renamed)
        raise cache_write_error(parent, exc) from exc


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
        and not key.upper().startswith("GIT_")
    }
    result["PYTHONNOUSERSITE"] = "1"
    result["PIP_CONFIG_FILE"] = os.devnull
    result["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    result["GIT_TERMINAL_PROMPT"] = "0"
    result["GIT_CONFIG_NOSYSTEM"] = "1"
    result["GIT_CONFIG_GLOBAL"] = os.devnull
    result["GIT_NO_REPLACE_OBJECTS"] = "1"
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


def remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
    elif path.is_dir():
        shutil.rmtree(path, ignore_errors=True)


def read_cache_marker(path: Path) -> dict[str, Any] | None:
    if path.is_symlink() or not path.is_file():
        return None
    try:
        return read_json_object(path, "Composition runner cache marker")
    except RunnerError:
        return None


def install_cache_directory(
    stage: Path,
    target: Path,
    valid_existing: Callable[[Path], bool],
) -> Path:
    if valid_existing(target):
        remove_path(stage)
        return target

    backup: Path | None = None
    if target.exists() or target.is_symlink():
        placeholder = Path(
            tempfile.mkdtemp(prefix=f".{target.name}.backup-", dir=target.parent)
        )
        placeholder.rmdir()
        backup = placeholder
        try:
            target.rename(backup)
        except FileNotFoundError:
            backup = None

    try:
        stage.rename(target)
    except OSError as rename_error:
        if valid_existing(target):
            remove_path(stage)
            if backup is not None:
                remove_path(backup)
            return target
        if (
            backup is not None
            and (backup.exists() or backup.is_symlink())
            and not (target.exists() or target.is_symlink())
        ):
            try:
                backup.rename(target)
            except OSError as restore_error:
                raise RunnerError(
                    f"cache installation failed for {target}: {rename_error}; "
                    f"previous cache entry could not be restored: {restore_error}"
                ) from restore_error
        raise

    if backup is not None:
        remove_path(backup)
    return target


def source_cache_entry(cache: Path, revision: str) -> Path:
    return cache / "sources" / revision


def source_checkout(entry: Path) -> Path:
    return entry / "checkout"


def source_marker(entry: Path) -> Path:
    return entry / "source.json"


def source_marker_payload(revision: str) -> dict[str, Any]:
    return {
        "schema_version": CACHE_SCHEMA,
        "repository": CANONICAL_REPOSITORY,
        "revision": revision,
    }


def source_valid(entry: Path, revision: str, env: Mapping[str, str]) -> bool:
    if entry.is_symlink() or not entry.is_dir():
        return False
    if read_cache_marker(source_marker(entry)) != source_marker_payload(revision):
        return False

    checkout = source_checkout(entry)
    git_directory = checkout / ".git"
    if checkout.is_symlink() or not checkout.is_dir():
        return False
    if git_directory.is_symlink() or not git_directory.is_dir():
        return False
    for forbidden in (
        git_directory / "shallow",
        git_directory / "info" / "grafts",
        git_directory / "refs" / "replace",
    ):
        if forbidden.exists() or forbidden.is_symlink():
            return False
    for required in (
        checkout / "requirements-runtime.lock",
        checkout / "scripts" / "compose.py",
        checkout / "scripts" / "verify_runtime_environment.py",
    ):
        if required.is_symlink() or not required.is_file():
            return False

    try:
        actual = run(
            ["git", "-C", str(checkout), "rev-parse", "HEAD"],
            env=env,
            capture_output=True,
        ).stdout.strip()
        remote = run(
            ["git", "-C", str(checkout), "remote", "get-url", "origin"],
            env=env,
            capture_output=True,
        ).stdout.strip()
        autocrlf = run(
            ["git", "-C", str(checkout), "config", "--local", "--get", "core.autocrlf"],
            env=env,
            capture_output=True,
        ).stdout.strip()
        eol = run(
            ["git", "-C", str(checkout), "config", "--local", "--get", "core.eol"],
            env=env,
            capture_output=True,
        ).stdout.strip()
        longpaths = run(
            ["git", "-C", str(checkout), "config", "--local", "--get", "core.longpaths"],
            env=env,
            capture_output=True,
        ).stdout.strip()
        status = run(
            [
                "git",
                "-C",
                str(checkout),
                "status",
                "--porcelain=v1",
                "--untracked-files=all",
            ],
            env=env,
            capture_output=True,
        ).stdout
        history_count = run(
            ["git", "-C", str(checkout), "rev-list", "--count", "HEAD"],
            env=env,
            capture_output=True,
        ).stdout.strip()
    except RunnerError:
        return False

    return (
        actual == revision
        and remote == CANONICAL_REMOTE
        and autocrlf == "false"
        and eol == "lf"
        and longpaths == "true"
        and not status.strip()
        and history_count.isdigit()
        and int(history_count) > 0
    )


def populate_source_checkout(
    checkout: Path,
    revision: str,
    env: Mapping[str, str],
) -> None:
    run(["git", "init", "--quiet", str(checkout)], env=env)
    run(
        ["git", "-C", str(checkout), "config", "--local", "core.autocrlf", "false"],
        env=env,
    )
    run(
        ["git", "-C", str(checkout), "config", "--local", "core.eol", "lf"],
        env=env,
    )
    run(
        ["git", "-C", str(checkout), "config", "--local", "core.longpaths", "true"],
        env=env,
    )
    run(
        ["git", "-C", str(checkout), "remote", "add", "origin", CANONICAL_REMOTE],
        env=env,
    )
    run(
        [
            "git",
            "-C",
            str(checkout),
            "fetch",
            "--quiet",
            "--no-tags",
            "origin",
            revision,
        ],
        env=env,
    )
    run(
        ["git", "-C", str(checkout), "checkout", "--quiet", "--detach", "FETCH_HEAD"],
        env=env,
    )


def build_source_cache(
    target: Path,
    revision: str,
    env: Mapping[str, str],
) -> Path:
    ensure_cache_parent(target.parent)
    stage = Path(tempfile.mkdtemp(prefix=f".{target.name}.build-", dir=target.parent))
    try:
        populate_source_checkout(source_checkout(stage), revision, env)
        source_marker(stage).write_text(
            json.dumps(source_marker_payload(revision), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if not source_valid(stage, revision, env):
            raise RunnerError("new Composition source cache failed validation")
        return install_cache_directory(
            stage,
            target,
            lambda candidate: source_valid(candidate, revision, env),
        )
    except OSError as exc:
        remove_path(stage)
        raise cache_write_error(target.parent, exc) from exc
    except Exception:
        remove_path(stage)
        raise


def ensure_source_cache(
    revision: str,
    cache: Path,
    env: Mapping[str, str],
) -> Path:
    if shutil.which("git") is None:
        raise RunnerError("Composition runner requires Git on PATH")
    target = source_cache_entry(cache, revision)
    if source_valid(target, revision, env):
        return source_checkout(target)
    entry = build_source_cache(target, revision, env)
    return source_checkout(entry)


def runtime_lock_data(
    source: Path,
    revision: str,
    manifest: Mapping[str, Any],
) -> bytes:
    lock = source / "requirements-runtime.lock"
    try:
        data = lock.read_bytes()
    except OSError as exc:
        raise RunnerError(f"cannot read cached requirements-runtime.lock: {exc}") from exc
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RunnerError("requirements-runtime.lock must be UTF-8") from exc
    parse_runtime_lock(text)
    if revision == stable_revision(manifest):
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


def runtime_identity(revision: str, lock_data: bytes) -> RuntimeIdentity:
    return RuntimeIdentity(
        repository=CANONICAL_REPOSITORY,
        revision=revision,
        lock_sha256=hashlib.sha256(lock_data).hexdigest(),
        python=python_token(),
        platform=platform_token(),
    )


def runtime_cache_entry(cache: Path, identity: RuntimeIdentity) -> Path:
    return cache / "runtimes" / identity.digest()


def runtime_marker(entry: Path) -> Path:
    return entry / "runtime.json"


def runtime_marker_payload(identity: RuntimeIdentity) -> dict[str, Any]:
    return {
        "schema_version": CACHE_SCHEMA,
        "identity": identity.payload(),
    }


def venv_python(root: Path) -> Path:
    if os.name == "nt":
        return root / "venv" / "Scripts" / "python.exe"
    return root / "venv" / "bin" / "python"


def runtime_valid(
    entry: Path,
    identity: RuntimeIdentity,
    source: Path,
    env: Mapping[str, str],
) -> bool:
    if entry.is_symlink() or not entry.is_dir():
        return False
    if read_cache_marker(runtime_marker(entry)) != runtime_marker_payload(identity):
        return False

    lock = entry / "requirements-runtime.lock"
    python = venv_python(entry)
    if lock.is_symlink() or not lock.is_file():
        return False
    if not python.is_file():
        return False
    try:
        lock_data = lock.read_bytes()
        parse_runtime_lock(lock_data.decode("utf-8"))
    except (OSError, UnicodeError, RunnerError):
        return False
    if hashlib.sha256(lock_data).hexdigest() != identity.lock_sha256:
        return False

    probe = (
        "import json,platform,sys;"
        "machine=platform.machine().lower() or 'unknown';"
        "print(json.dumps({"
        "'python':str(sys.version_info.major)+'.'+str(sys.version_info.minor),"
        "'platform':sys.platform+'-'+machine"
        "},sort_keys=True))"
    )
    try:
        result = run(
            [str(python), "-I", "-c", probe],
            env=env,
            capture_output=True,
        )
        actual_identity = json.loads(result.stdout)
        if actual_identity != {
            "python": identity.python,
            "platform": identity.platform,
        }:
            return False
        run(
            [str(python), "-I", "-m", "pip", "check"],
            env=env,
            capture_output=True,
        )
        run(
            [str(python), "-I", str(source / "scripts" / "verify_runtime_environment.py")],
            cwd=source,
            env=env,
            capture_output=True,
        )
    except (RunnerError, ValueError, json.JSONDecodeError):
        return False
    return True


def build_runtime_cache(
    target: Path,
    identity: RuntimeIdentity,
    source: Path,
    lock_data: bytes,
    env: Mapping[str, str],
) -> Path:
    ensure_cache_parent(target.parent)
    stage = Path(tempfile.mkdtemp(prefix=f".{target.name}.build-", dir=target.parent))
    try:
        lock = stage / "requirements-runtime.lock"
        lock.write_bytes(lock_data)
        run(
            [sys.executable, "-I", "-m", "venv", str(stage / "venv")],
            env=env,
        )
        python = venv_python(stage)
        run(
            [
                str(python),
                "-I",
                "-m",
                "pip",
                "install",
                "--isolated",
                "--disable-pip-version-check",
                "--no-cache-dir",
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
        runtime_marker(stage).write_text(
            json.dumps(runtime_marker_payload(identity), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if not runtime_valid(stage, identity, source, env):
            raise RunnerError("new Composition runtime cache failed validation")
        return install_cache_directory(
            stage,
            target,
            lambda candidate: runtime_valid(candidate, identity, source, env),
        )
    except OSError as exc:
        remove_path(stage)
        raise cache_write_error(target.parent, exc) from exc
    except Exception:
        remove_path(stage)
        raise


def ensure_runtime_cache(
    source: Path,
    revision: str,
    manifest: Mapping[str, Any],
    cache: Path,
    env: Mapping[str, str],
) -> Path:
    lock_data = runtime_lock_data(source, revision, manifest)
    identity = runtime_identity(revision, lock_data)
    target = runtime_cache_entry(cache, identity)
    if runtime_valid(target, identity, source, env):
        return venv_python(target)
    entry = build_runtime_cache(target, identity, source, lock_data, env)
    return venv_python(entry)


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
    cache = cache_root()
    source = ensure_source_cache(revision, cache, env)
    python = ensure_runtime_cache(source, revision, manifest, cache, env)
    command = [
        str(python),
        "-I",
        "-B",
        str(source / manifest["entrypoint"]),
        *arguments,
        "--target",
        str(repository),
    ]
    try:
        completed = subprocess.run(
            command,
            env=env,
            check=False,
        )
    except OSError as exc:
        raise RunnerError(f"cannot execute Composition Composer: {exc}") from exc
    return completed.returncode
