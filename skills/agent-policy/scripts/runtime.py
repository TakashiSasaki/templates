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
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
EXACT_REQUIREMENT = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9_.-]*===([A-Za-z0-9][A-Za-z0-9_.+!-]*)$"
)
BOOTSTRAP_DISTRIBUTIONS = frozenset({"pip", "setuptools", "wheel"})
SKILL_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = SKILL_ROOT / "runtime-manifest.json"
CACHE_SCHEMA = 1
CLI_MODULE = "agent_policy.cli"


@dataclass(frozen=True)
class RuntimePin:
    repository: str
    revision: str
    lock_path: str
    expected_lock_sha256: str | None
    project_distribution: str
    project_version: str | None
    executable: str


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


def normalize_distribution_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def load_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise ValueError("Unsupported agent-policy runtime manifest")
    return value


def pin_from_manifest(manifest: Mapping[str, Any]) -> RuntimePin:
    toolchain = manifest.get("toolchain")
    runtime_lock = manifest.get("runtime_lock")
    project = manifest.get("project")
    if not isinstance(toolchain, dict) or not isinstance(runtime_lock, dict):
        raise ValueError("Runtime manifest is missing toolchain or runtime_lock")
    if not isinstance(project, dict):
        raise ValueError("Runtime manifest is missing project metadata")

    repository = toolchain.get("repository")
    revision = toolchain.get("revision")
    lock_path = runtime_lock.get("path")
    lock_sha256 = runtime_lock.get("sha256")
    distribution = project.get("distribution")
    version = project.get("version")
    executable = project.get("executable")

    if repository != "TakashiSasaki/templates":
        raise ValueError("Runtime manifest repository identity is unsupported")
    if not isinstance(revision, str) or FULL_SHA.fullmatch(revision) is None:
        raise ValueError("Runtime manifest revision must be a full lowercase commit SHA")
    if lock_path != "requirements-runtime.lock":
        raise ValueError("Runtime manifest lock path is unsupported")
    if (
        not isinstance(lock_sha256, str)
        or re.fullmatch(r"[0-9a-f]{64}", lock_sha256) is None
    ):
        raise ValueError("Runtime manifest lock digest must be lowercase SHA-256")
    if not all(
        isinstance(value, str) and value
        for value in (distribution, version, executable)
    ):
        raise ValueError("Runtime manifest project metadata is invalid")

    return RuntimePin(
        repository=repository,
        revision=revision,
        lock_path=lock_path,
        expected_lock_sha256=lock_sha256,
        project_distribution=distribution,
        project_version=version,
        executable=executable,
    )


def find_repository_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    raise FileNotFoundError("No Git repository root found")


def lock_toolchain(path: Path) -> tuple[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    in_toolchain = False
    found_toolchain = False
    fields: dict[str, str] = {}
    allowed = {"repository", "revision"}

    for raw in lines:
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        if indent == 0:
            if stripped == "toolchain:":
                if found_toolchain:
                    raise ValueError(
                        ".agent-policy.lock must contain exactly one toolchain mapping"
                    )
                found_toolchain = True
                in_toolchain = True
            else:
                in_toolchain = False
            continue
        if not in_toolchain:
            continue
        if indent != 2 or ":" not in stripped:
            raise ValueError(
                ".agent-policy.lock toolchain must be a flat two-space mapping"
            )
        key, raw_value = stripped.split(":", 1)
        if key not in allowed:
            raise ValueError(f".agent-policy.lock toolchain has unsupported key: {key}")
        if key in fields:
            raise ValueError(f".agent-policy.lock toolchain key is duplicated: {key}")
        value = raw_value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        elif not value or value[0] in {'"', "'"} or value[-1:] in {'"', "'"}:
            raise ValueError(
                f".agent-policy.lock toolchain {key} must be a plain scalar"
            )
        fields[key] = value

    if not found_toolchain:
        raise ValueError(".agent-policy.lock is missing the toolchain mapping")
    if set(fields) != allowed:
        missing = ", ".join(sorted(allowed - set(fields)))
        raise ValueError(f".agent-policy.lock toolchain is missing keys: {missing}")

    repository = fields["repository"]
    revision = fields["revision"]
    if repository != "TakashiSasaki/templates":
        raise ValueError(".agent-policy.lock has an unsupported toolchain repository")
    if FULL_SHA.fullmatch(revision) is None:
        raise ValueError(
            ".agent-policy.lock toolchain revision must be a full lowercase commit SHA"
        )
    return repository, revision


def select_pin(
    repository_root: Path,
    manifest: Mapping[str, Any] | None = None,
) -> RuntimePin:
    manifest_value = load_manifest() if manifest is None else dict(manifest)
    default = pin_from_manifest(manifest_value)
    lock_path = repository_root / ".agent-policy.lock"
    if not lock_path.exists():
        return default
    repository, revision = lock_toolchain(lock_path)
    is_default = revision == default.revision
    return RuntimePin(
        repository=repository,
        revision=revision,
        lock_path=default.lock_path,
        expected_lock_sha256=(default.expected_lock_sha256 if is_default else None),
        project_distribution=default.project_distribution,
        project_version=(default.project_version if is_default else None),
        executable=default.executable,
    )


def platform_token() -> str:
    machine = platform.machine().lower() or "unknown"
    return f"{sys.platform}-{machine}"


def python_token() -> str:
    return f"{sys.version_info.major}.{sys.version_info.minor}"


def cache_root() -> Path:
    override = os.environ.get("AGENT_POLICY_RUNTIME_CACHE")
    if override:
        return Path(override).expanduser().resolve()
    if os.name == "nt":
        local = os.environ.get("LOCALAPPDATA")
        base = Path(local) if local else Path.home() / ".cache"
    else:
        xdg = os.environ.get("XDG_CACHE_HOME")
        base = Path(xdg) if xdg else Path.home() / ".cache"
    return base / "agent-policy" / "runtime-v1"


def sanitized_environment(source: Mapping[str, str] | None = None) -> dict[str, str]:
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


def raw_url(pin: RuntimePin) -> str:
    return (
        f"https://raw.githubusercontent.com/{pin.repository}/"
        f"{pin.revision}/{pin.lock_path}"
    )


def download_runtime_lock(pin: RuntimePin) -> bytes:
    with urllib.request.urlopen(raw_url(pin), timeout=30) as response:  # noqa: S310
        data = response.read()
    digest = hashlib.sha256(data).hexdigest()
    if pin.expected_lock_sha256 is not None and digest != pin.expected_lock_sha256:
        raise RuntimeError(
            "Pinned runtime lock digest mismatch: "
            f"expected {pin.expected_lock_sha256}, received {digest}"
        )
    parse_runtime_lock(data.decode("utf-8"))
    return data


def parse_runtime_lock(text: str) -> dict[str, str]:
    requirements: dict[str, str] = {}
    for line in text.splitlines():
        value = line.strip()
        if not value or value.startswith("#"):
            continue
        match = EXACT_REQUIREMENT.fullmatch(value)
        if match is None:
            raise ValueError(f"Runtime lock entry is not exact name===version: {value}")
        name, version = value.split("===", 1)
        normalized = normalize_distribution_name(name)
        if normalized in requirements:
            raise ValueError(f"Runtime lock distribution is duplicated: {name}")
        requirements[normalized] = version
    if not requirements:
        raise ValueError("Runtime lock must not be empty")
    return requirements


def identity_for(pin: RuntimePin, lock_data: bytes) -> RuntimeIdentity:
    return RuntimeIdentity(
        repository=pin.repository,
        revision=pin.revision,
        lock_sha256=hashlib.sha256(lock_data).hexdigest(),
        python=python_token(),
        platform=platform_token(),
    )


def venv_python(root: Path) -> Path:
    if os.name == "nt":
        return root / "venv" / "Scripts" / "python.exe"
    return root / "venv" / "bin" / "python"


def executable_path(root: Path, executable: str) -> Path:
    suffix = ".exe" if os.name == "nt" else ""
    directory = root / "venv" / ("Scripts" if os.name == "nt" else "bin")
    return directory / f"{executable}{suffix}"


def cli_command(root: Path) -> list[str]:
    return [str(venv_python(root)), "-I", "-m", CLI_MODULE]


def marker_path(root: Path) -> Path:
    return root / "runtime.json"


def marker_payload(
    identity: RuntimeIdentity,
    pin: RuntimePin,
    project_version: str,
) -> dict[str, Any]:
    return {
        "schema_version": CACHE_SCHEMA,
        "identity": identity.payload(),
        "project": {
            "distribution": pin.project_distribution,
            "version": project_version,
            "executable": pin.executable,
        },
    }


def expected_marker(
    identity: RuntimeIdentity,
    pin: RuntimePin,
    project_version: str | None = None,
) -> dict[str, Any]:
    version = project_version if project_version is not None else pin.project_version
    if version is None:
        raise ValueError("Project version is unknown for this runtime pin")
    return marker_payload(identity, pin, version)


def marker_matches(root: Path, identity: RuntimeIdentity, pin: RuntimePin) -> bool:
    try:
        marker = json.loads(marker_path(root).read_text(encoding="utf-8"))
        project = marker["project"]
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return False
    if not isinstance(project, dict):
        return False
    version = project.get("version")
    if not isinstance(version, str) or not version:
        return False
    if pin.project_version is not None and version != pin.project_version:
        return False
    return (
        marker.get("schema_version") == CACHE_SCHEMA
        and marker.get("identity") == identity.payload()
        and project.get("distribution") == pin.project_distribution
        and project.get("executable") == pin.executable
        and venv_python(root).is_file()
        and executable_path(root, pin.executable).is_file()
    )


def runtime_valid(root: Path, identity: RuntimeIdentity, pin: RuntimePin) -> bool:
    return marker_matches(root, identity, pin)


def cached_for_revision(root: Path, pin: RuntimePin) -> Path | None:
    if not root.is_dir():
        return None
    for candidate in root.iterdir():
        if not candidate.is_dir():
            continue
        try:
            marker = json.loads(marker_path(candidate).read_text(encoding="utf-8"))
            identity_value = marker["identity"]
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            continue
        if not isinstance(identity_value, dict):
            continue
        lock_digest = identity_value.get("lock_sha256")
        if not isinstance(lock_digest, str) or re.fullmatch(
            r"[0-9a-f]{64}", lock_digest
        ) is None:
            continue
        identity = RuntimeIdentity(
            repository=pin.repository,
            revision=pin.revision,
            lock_sha256=lock_digest,
            python=python_token(),
            platform=platform_token(),
        )
        if candidate.name == identity.digest() and marker_matches(candidate, identity, pin):
            return candidate
    return None


def run(command: list[str], *, env: Mapping[str, str]) -> None:
    subprocess.run(command, check=True, env=dict(env))


def installed_distributions(
    python: Path,
    env: Mapping[str, str],
) -> dict[str, str]:
    script = (
        "import importlib.metadata as m,json;"
        "print(json.dumps({d.metadata['Name']:d.version for d in m.distributions()}))"
    )
    result = subprocess.run(
        [str(python), "-I", "-c", script],
        check=True,
        env=dict(env),
        capture_output=True,
        text=True,
    )
    value = json.loads(result.stdout)
    if not isinstance(value, dict) or not all(
        isinstance(key, str) and isinstance(version, str)
        for key, version in value.items()
    ):
        raise RuntimeError("Cached runtime returned invalid distribution metadata")
    return {
        normalize_distribution_name(key): version for key, version in value.items()
    }


def verify_installed_set(
    python: Path,
    requirements: Mapping[str, str],
    pin: RuntimePin,
    env: Mapping[str, str],
) -> str:
    installed = installed_distributions(python, env)
    expected = {
        normalize_distribution_name(name): version
        for name, version in requirements.items()
    }
    project_name = normalize_distribution_name(pin.project_distribution)
    actual_project = installed.get(project_name)
    if actual_project is None:
        raise RuntimeError("Cached project distribution is missing")
    if pin.project_version is not None and actual_project != pin.project_version:
        raise RuntimeError(
            f"Cached project version mismatch: expected {pin.project_version}, "
            f"installed {actual_project!r}"
        )
    checked = {
        name: version
        for name, version in installed.items()
        if name not in BOOTSTRAP_DISTRIBUTIONS and name != project_name
    }
    if checked != expected:
        raise RuntimeError(
            "Cached runtime distribution set does not match requirements-runtime.lock"
        )
    return actual_project


def build_runtime(
    target: Path,
    identity: RuntimeIdentity,
    pin: RuntimePin,
    lock_data: bytes,
) -> Path:
    root = target.parent
    root.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{target.name}.build-", dir=root))
    env = sanitized_environment()
    backup: Path | None = None
    try:
        lock = stage / "requirements-runtime.lock"
        lock.write_bytes(lock_data)
        requirements = parse_runtime_lock(lock_data.decode("utf-8"))
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
                "--disable-pip-version-check",
                "--no-deps",
                "--requirement",
                str(lock),
            ],
            env=env,
        )
        requirement = f"git+https://github.com/{pin.repository}.git@{pin.revision}"
        run(
            [
                str(python),
                "-I",
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--no-deps",
                requirement,
            ],
            env=env,
        )
        run([str(python), "-I", "-m", "pip", "check"], env=env)
        project_version = verify_installed_set(python, requirements, pin, env)
        executable = executable_path(stage, pin.executable)
        if not executable.is_file():
            raise RuntimeError("Cached runtime executable was not installed")
        marker_path(stage).write_text(
            json.dumps(
                marker_payload(identity, pin, project_version),
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        if target.exists():
            if runtime_valid(target, identity, pin):
                shutil.rmtree(stage)
                return target
            backup = target.with_name(f".{target.name}.backup-{os.getpid()}")
            if backup.exists():
                shutil.rmtree(backup)
            target.rename(backup)
        stage.rename(target)
        try:
            run([*cli_command(target), "--help"], env=env)
        except Exception:
            shutil.rmtree(target, ignore_errors=True)
            if backup is not None and backup.exists():
                backup.rename(target)
                backup = None
            raise
        if backup is not None:
            shutil.rmtree(backup, ignore_errors=True)
        return target
    except Exception:
        if backup is not None and backup.exists() and not target.exists():
            backup.rename(target)
        shutil.rmtree(stage, ignore_errors=True)
        raise


def ensure_runtime(pin: RuntimePin, *, root: Path | None = None) -> Path:
    cache = cache_root() if root is None else root
    if pin.expected_lock_sha256 is None:
        cached = cached_for_revision(cache, pin)
        if cached is not None:
            return cached

    if pin.expected_lock_sha256 is not None:
        identity = RuntimeIdentity(
            repository=pin.repository,
            revision=pin.revision,
            lock_sha256=pin.expected_lock_sha256,
            python=python_token(),
            platform=platform_token(),
        )
        target = cache / identity.digest()
        if runtime_valid(target, identity, pin):
            return target

    lock_data = download_runtime_lock(pin)
    identity = identity_for(pin, lock_data)
    target = cache / identity.digest()
    if runtime_valid(target, identity, pin):
        return target
    return build_runtime(target, identity, pin, lock_data)


def runtime_command(repository_root: Path) -> list[str]:
    pin = select_pin(repository_root)
    runtime = ensure_runtime(pin)
    return cli_command(runtime)
