from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "agent-policy"
SCRIPTS = SKILL_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def load_script(name: str, relative: str) -> ModuleType:
    path = SKILL_ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


runtime = load_script("agent_policy_cache_runtime", "scripts/runtime.py")
runner = load_script("agent_policy_cache_runner", "scripts/run.py")


def write_fake_runtime_entrypoints(target: Path, executable_name: str) -> None:
    python = runtime.venv_python(target)
    python.parent.mkdir(parents=True, exist_ok=True)
    python.write_text("cached-python", encoding="utf-8")
    executable = runtime.executable_path(target, executable_name)
    executable.parent.mkdir(parents=True, exist_ok=True)
    executable.write_text("cached-executable", encoding="utf-8")


def test_cache_preflight_reports_actionable_override(tmp_path: Path) -> None:
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("blocked", encoding="utf-8")
    cache = blocker / "cache"

    with pytest.raises(RuntimeError, match="AGENT_POLICY_RUNTIME_CACHE") as exc_info:
        runtime.ensure_cache_writable(cache)

    assert str(cache) in str(exc_info.value)


def test_cache_preflight_cleans_probe_artifacts(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    runtime.ensure_cache_writable(cache)
    assert cache.is_dir()
    assert list(cache.iterdir()) == []


def test_valid_warm_cache_skips_writability_probe_and_network(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pin = runtime.pin_from_manifest(runtime.load_manifest())
    identity = runtime.RuntimeIdentity(
        pin.repository,
        pin.revision,
        pin.expected_lock_sha256,
        runtime.python_token(),
        runtime.platform_token(),
    )
    target = tmp_path / identity.digest()
    target.mkdir(parents=True)
    write_fake_runtime_entrypoints(target, pin.executable)
    runtime.marker_path(target).write_text(
        json.dumps(runtime.expected_marker(identity, pin)),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        runtime,
        "ensure_cache_writable",
        lambda _root: (_ for _ in ()).throw(
            AssertionError("warm cache hit must not require a writable cache root")
        ),
    )
    monkeypatch.setattr(
        runtime,
        "download_runtime_lock",
        lambda _pin: (_ for _ in ()).throw(
            AssertionError("warm cache hit must not use the network")
        ),
    )

    assert runtime.ensure_runtime(pin, root=tmp_path) == target


def test_runtime_build_disables_independent_pip_download_cache() -> None:
    source = (SCRIPTS / "runtime.py").read_text(encoding="utf-8")
    assert source.count('"--no-cache-dir"') == 2


def test_managed_runner_normalizes_runtime_setup_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository = tmp_path / "repo"
    (repository / ".git").mkdir(parents=True)
    monkeypatch.setattr(
        runner,
        "runtime_command",
        lambda _repository: (_ for _ in ()).throw(
            RuntimeError(
                "agent-policy runtime cache is unusable; "
                "set AGENT_POLICY_RUNTIME_CACHE"
            )
        ),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["run.py", "--repository", str(repository), "validate"],
    )

    assert runner.main() == 2
    captured = capsys.readouterr()
    assert "agent-policy skill error:" in captured.err
    assert "AGENT_POLICY_RUNTIME_CACHE" in captured.err
    assert "Traceback" not in captured.err
