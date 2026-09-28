from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import _authority_supervisor  # noqa: E402
from scripts import orchestrate_preflights as orchestrator_module  # noqa: E402
from scripts.orchestrate_preflights import (  # noqa: E402
    ALL_AUTHORITIES,
    MAX_SUMMARY_BYTES,
    AuthorityRunResult,
    allocate_worker_batches,
    build_parser,
    orchestrate_preflights,
    run_single_preflight,
)

FAKE_SHA = "1234567890abcdef1234567890abcdef12345678"


def _pid_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def _cleanup_test_process_group(process_group_id: int) -> None:
    try:
        os.killpg(process_group_id, signal.SIGKILL)
    except ProcessLookupError:
        return
    while True:
        try:
            os.waitpid(-process_group_id, 0)
        except InterruptedError:
            continue
        except ChildProcessError:
            return


def _assert_nested_timeout_is_reaped(
    workspace: Path, tmp_path: Path, *, drop_uid: int | None = None
) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    worktree = _create_mock_authority(workspace, "policy")
    authority_pid_file = tmp_path / "authority.pid"
    child_pid_file = tmp_path / "child.pid"
    child_code = (
        "import os, signal; os.setsid(); "
        + (f"os.setuid({drop_uid}); " if drop_uid is not None else "")
        + "signal.signal(signal.SIGTERM, signal.SIG_IGN); signal.pause()"
    )
    script = worktree / "scripts" / "run_policy_preflight.py"
    script.write_text(
        "import os, signal, subprocess, sys\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        f"open({str(authority_pid_file)!r}, 'w').write(str(os.getpid()))\n"
        f"child = subprocess.Popen([sys.executable, '-c', {child_code!r}])\n"
        f"open({str(child_pid_file)!r}, 'w').write(str(child.pid))\n"
        "os.write(1, b'o' * 131072)\n"
        "os.write(2, b'e' * 131072)\n"
        "signal.pause()\n",
        encoding="utf-8",
    )

    authority_pid: int | None = None
    child_pid: int | None = None
    try:
        result = run_single_preflight(
            authority="policy", repo_root=workspace, timeout=1.0
        )

        assert result.status == "TIMEOUT"
        authority_pid = int(authority_pid_file.read_text(encoding="utf-8"))
        child_pid = int(child_pid_file.read_text(encoding="utf-8"))
        assert not _pid_exists(authority_pid)
        assert not _pid_exists(child_pid)
    finally:
        if authority_pid is None and authority_pid_file.exists():
            authority_pid = int(authority_pid_file.read_text(encoding="utf-8"))
        if authority_pid is not None:
            _cleanup_test_process_group(authority_pid)
        if child_pid is None and child_pid_file.exists():
            child_pid = int(child_pid_file.read_text(encoding="utf-8"))
        if child_pid is not None:
            try:
                os.kill(child_pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


def _wait_for_path(path: Path, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while not path.exists():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        threading.Event().wait(min(0.01, remaining))
    return True


def _process_state_and_parent(pid: int) -> tuple[str, int] | None:
    try:
        stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    fields = stat[stat.rfind(")") + 2 :].split()
    return fields[0], int(fields[1])


def _wait_for_pid_absent(pid: int, timeout: float = 3.0) -> bool:
    deadline = time.monotonic() + timeout
    while _process_state_and_parent(pid) is not None:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        threading.Event().wait(min(0.01, remaining))
    return True


def _run_normal_completion_case(
    tmp_path: Path, exit_code: int, *, drop_uid: int | None = None
):
    if drop_uid is not None:
        tmp_path.chmod(0o777)
    workspace = tmp_path / "workspace"
    worktree = _create_mock_authority(workspace, "policy")
    parent_pid_file = tmp_path / "authority.pid"
    child_pid_file = tmp_path / "child.pid"
    adopted_file = tmp_path / "adopted"
    release_file = tmp_path / "release"
    child_code = (
        "import os, pathlib, sys, time\n"
        "os.setsid()\n"
        + (f"os.setuid({drop_uid})\n" if drop_uid is not None else "")
        + "authority_pid = int(sys.argv[1])\n"
        + "adopted = pathlib.Path(sys.argv[2])\n"
        + "release = pathlib.Path(sys.argv[3])\n"
        + "while os.getppid() == authority_pid:\n"
        + "    time.sleep(0.001)\n"
        + "adopted.write_text(str(os.getppid()), encoding='utf-8')\n"
        + "while not release.exists():\n"
        + "    time.sleep(0.001)\n"
    )
    script = worktree / "scripts" / "run_policy_preflight.py"
    script.write_text(
        "import os, subprocess, sys\n"
        f"child_code = {child_code!r}\n"
        "child = subprocess.Popen([sys.executable, '-c', child_code, "
        "str(os.getpid()), "
        f"{str(adopted_file)!r}, {str(release_file)!r}], "
        "stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n"
        f"open({str(parent_pid_file)!r}, 'w').write(str(os.getpid()))\n"
        f"open({str(child_pid_file)!r}, 'w').write(str(child.pid))\n"
        + (
            "print('synthetic authority failure', file=sys.stderr)\n"
            if exit_code
            else "print('synthetic authority pass')\n"
        )
        + f"sys.exit({exit_code})\n",
        encoding="utf-8",
    )

    release_errors: list[str] = []

    def release_after_adoption() -> None:
        if _wait_for_path(adopted_file):
            release_file.write_text("release", encoding="utf-8")
        else:
            release_errors.append("descendant was not adopted before the test deadline")

    release_thread = threading.Thread(target=release_after_adoption, daemon=True)
    release_thread.start()
    authority_pid: int | None = None
    child_pid: int | None = None
    supervisor_pid: int | None = None
    try:
        result = run_single_preflight(
            authority="policy", repo_root=workspace, timeout=5.0
        )
        assert result.status == ("PASS" if exit_code == 0 else "FAIL")
        if exit_code:
            assert "synthetic authority failure" in result.failure_excerpt

        assert release_thread.join(timeout=5.0) is None
        assert not release_thread.is_alive()
        assert not release_errors
        authority_pid = int(parent_pid_file.read_text(encoding="utf-8"))
        child_pid = int(child_pid_file.read_text(encoding="utf-8"))
        supervisor_pid = int(adopted_file.read_text(encoding="utf-8"))
        assert supervisor_pid not in (os.getpid(), authority_pid)
        assert _process_state_and_parent(child_pid) is None
        assert not _pid_exists(authority_pid)
        assert not _pid_exists(supervisor_pid)
        assert result.elapsed_seconds < 5.0
        return result
    finally:
        release_file.write_text("release", encoding="utf-8")
        release_thread.join(timeout=5.0)
        if authority_pid is None and parent_pid_file.exists():
            authority_pid = int(parent_pid_file.read_text(encoding="utf-8"))
        if authority_pid is not None:
            _cleanup_test_process_group(authority_pid)
        if child_pid is None and child_pid_file.exists():
            child_pid = int(child_pid_file.read_text(encoding="utf-8"))
        if child_pid is not None:
            try:
                os.kill(child_pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


def _create_mock_authority(
    repo_root: Path,
    authority: str,
    exit_code: int = 0,
    output_text: str = "PASS",
    sleep_seconds: float = 0.0,
    custom_script: str | None = None,
) -> Path:
    worktree = repo_root / authority
    worktree.mkdir(parents=True, exist_ok=True)

    # Initialize fake git repo so git rev-parse HEAD works
    subprocess.run(["git", "init"], cwd=worktree, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.name", "Test Agent"],
        cwd=worktree,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@agent.local"],
        cwd=worktree,
        capture_output=True,
        check=True,
    )
    dummy_file = worktree / "dummy.txt"
    dummy_file.write_text("content\n", encoding="utf-8")
    subprocess.run(["git", "add", "dummy.txt"], cwd=worktree, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "init"], cwd=worktree, capture_output=True, check=True
    )

    if authority == "modeling":
        script_path = worktree / "tools" / "qualify.py"
    else:
        script_path = worktree / "scripts" / f"run_{authority}_preflight.py"

    script_path.parent.mkdir(parents=True, exist_ok=True)

    if custom_script:
        script_code = custom_script
    else:
        script_code = (
            f"#!/usr/bin/env python3\n"
            f"import sys, time\n"
            f"if {sleep_seconds} > 0:\n"
            f"    time.sleep({sleep_seconds})\n"
            f"print('''{output_text}''')\n"
            f"sys.exit({exit_code})\n"
        )
    script_path.write_text(script_code, encoding="utf-8")
    script_path.chmod(0o755)
    return worktree


def test_single_successful_preflight(tmp_path: Path) -> None:
    repo_root = tmp_path / "workspace"
    _create_mock_authority(repo_root, "policy", exit_code=0, output_text="POLICY_OK")

    res = run_single_preflight(
        authority="policy",
        repo_root=repo_root,
        timeout=10,
    )
    assert res.status == "PASS"
    assert res.exit_code == 0
    assert len(res.head_sha) == 40
    assert res.authority == "policy"
    assert res.command[-2:] == ["--jobs", "1"]
    assert res.allocated_workers == 1


def test_empty_and_unknown_authority_selections_are_rejected(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="at least one authority"):
        orchestrate_preflights(authorities=[], repo_root=tmp_path)
    with pytest.raises(ValueError, match="at least one authority"):
        allocate_worker_batches([], global_jobs=2)
    with pytest.raises(ValueError, match="unknown authority selection"):
        orchestrate_preflights(authorities=["invalid"], repo_root=tmp_path)


def test_multiple_successful_preflights_serial(tmp_path: Path) -> None:
    repo_root = tmp_path / "workspace"
    _create_mock_authority(repo_root, "policy", exit_code=0, output_text="POLICY_PASS")
    _create_mock_authority(repo_root, "composition", exit_code=0, output_text="COMPOSITION_PASS")
    _create_mock_authority(repo_root, "modeling", exit_code=0, output_text="MODELING_PASS")

    res = orchestrate_preflights(
        authorities=["policy", "composition", "modeling"],
        repo_root=repo_root,
        global_jobs=1,
    )
    assert res["overall_status"] == "PASSED"
    assert len(res["authorities"]) == 3
    assert all(a["status"] == "PASS" for a in res["authorities"])
    assert "policy       PASS" in res["summary_table"]
    assert "composition  PASS" in res["summary_table"]
    assert "modeling     PASS" in res["summary_table"]


def test_safe_concurrency_execution(tmp_path: Path) -> None:
    repo_root = tmp_path / "workspace"
    _create_mock_authority(repo_root, "policy", sleep_seconds=0.1)
    _create_mock_authority(repo_root, "composition", sleep_seconds=0.1)
    _create_mock_authority(repo_root, "site", sleep_seconds=0.1)

    res = orchestrate_preflights(
        authorities=["policy", "composition", "site"],
        repo_root=repo_root,
        global_jobs=3,
    )
    assert res["overall_status"] == "PASSED"
    assert res["worker_budget"]["requested_jobs"] == 3
    assert res["worker_budget"]["max_active_allocated_workers"] == 3
    assert len(res["authorities"]) == 3


def test_one_authority_failure_captured_and_excerpted(tmp_path: Path) -> None:
    repo_root = tmp_path / "workspace"
    _create_mock_authority(repo_root, "policy", exit_code=0, output_text="PASS")
    _create_mock_authority(
        repo_root,
        "site",
        exit_code=1,
        output_text="Error: syntax error in site.json\nBuild failed!",
    )

    res = orchestrate_preflights(
        authorities=["policy", "site"],
        repo_root=repo_root,
    )
    assert res["overall_status"] == "FAILED"
    site_res = next(a for a in res["authorities"] if a["authority"] == "site")
    assert site_res["status"] == "FAIL"
    assert site_res["exit_code"] == 1
    assert "syntax error in site.json" in site_res["failure_excerpt"]


def test_preflight_timeout_handling(tmp_path: Path) -> None:
    repo_root = tmp_path / "workspace"
    _create_mock_authority(repo_root, "integration", sleep_seconds=5.0)

    res = run_single_preflight(
        authority="integration",
        repo_root=repo_root,
        timeout=1,  # 1 second timeout
    )
    assert res.status == "TIMEOUT"
    assert res.exit_code is None
    assert "timeout limit" in res.failure_excerpt


def test_log_write_failure_is_normalized_as_authority_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "workspace"
    _create_mock_authority(repo_root, "policy")
    original_write_text = Path.write_text

    def fail_authority_log(path: Path, data: str, *args, **kwargs):
        if path.name == "policy.log":
            raise OSError("controlled full filesystem")
        return original_write_text(path, data, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", fail_authority_log)
    result = run_single_preflight(
        authority="policy",
        repo_root=repo_root,
        log_dir=tmp_path / "logs",
    )

    assert result.status == "FAIL"
    assert result.exit_code == 1
    assert "failed to write authority log" in result.failure_excerpt
    assert "controlled full filesystem" in result.failure_excerpt


def test_log_directory_creation_failure_is_aggregated_for_each_authority(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "workspace"
    _create_mock_authority(repo_root, "policy")
    _create_mock_authority(repo_root, "composition")
    log_dir = tmp_path / "logs"
    log_dir.write_text("not a directory", encoding="utf-8")

    result = orchestrate_preflights(
        authorities=["policy", "composition"],
        repo_root=repo_root,
        global_jobs=2,
        log_dir=log_dir,
    )

    assert result["overall_status"] == "FAILED"
    assert [item["authority"] for item in result["authorities"]] == [
        "policy",
        "composition",
    ]
    for item in result["authorities"]:
        assert item["status"] == "FAIL"
        assert "failed to create authority log directory" in item["failure_excerpt"]
        assert "failed to write authority log" in item["failure_excerpt"]


@pytest.mark.skipif(os.name != "posix", reason="requires POSIX supervisor signal handling")
def test_coordinator_sigterm_stops_supervisor_and_authority_tree(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    worktree = _create_mock_authority(workspace, "policy")
    authority_pid_file = tmp_path / "authority.pid"
    child_pid_file = tmp_path / "child.pid"
    child_code = (
        "import os, signal; signal.signal(signal.SIGTERM, signal.SIG_IGN); "
        f"open({str(child_pid_file)!r}, 'w').write(str(os.getpid())); "
        "signal.pause()"
    )
    (worktree / "scripts" / "run_policy_preflight.py").write_text(
        "import os, signal, subprocess, sys\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        f"child = subprocess.Popen([sys.executable, '-c', {child_code!r}])\n"
        f"open({str(authority_pid_file)!r}, 'w').write(str(os.getpid()))\n"
        "signal.pause()\n",
        encoding="utf-8",
    )

    coordinator = subprocess.Popen(
        [
            sys.executable,
            str(ROOT / "scripts" / "orchestrate_preflights.py"),
            "--repo-root",
            str(workspace),
            "--jobs",
            "1",
            "--timeout",
            "30",
            "policy",
        ],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    authority_pid: int | None = None
    child_pid: int | None = None
    try:
        assert _wait_for_path(authority_pid_file)
        assert _wait_for_path(child_pid_file)
        authority_pid = int(authority_pid_file.read_text(encoding="utf-8"))
        child_pid = int(child_pid_file.read_text(encoding="utf-8"))

        coordinator.send_signal(signal.SIGTERM)
        _stdout, stderr = coordinator.communicate(timeout=8)

        assert coordinator.returncode == 128 + signal.SIGTERM
        assert "coordinator interrupted" in stderr
        assert _wait_for_pid_absent(authority_pid)
        assert _wait_for_pid_absent(child_pid)
    finally:
        if coordinator.poll() is None:
            coordinator.kill()
            coordinator.communicate(timeout=3)
        if authority_pid is None and authority_pid_file.exists():
            authority_pid = int(authority_pid_file.read_text(encoding="utf-8"))
        if authority_pid is not None:
            try:
                os.kill(authority_pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if child_pid is None and child_pid_file.exists():
            child_pid = int(child_pid_file.read_text(encoding="utf-8"))
        if child_pid is not None:
            try:
                os.kill(child_pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


def test_supervisor_cleanup_exit_code_reports_cleanup_failure() -> None:
    class CompletedSupervisor:
        returncode = 125

        def terminate(self) -> None:
            pass

        def communicate(self, *, timeout: float) -> tuple[str, str]:
            assert timeout == orchestrator_module.SUPERVISOR_CLEANUP_TIMEOUT_SECONDS
            return "supervisor output", "cleanup failed"

    stdout, stderr, cleanup_complete = orchestrator_module._stop_authority_supervisor(
        CompletedSupervisor()
    )

    assert stdout == "supervisor output"
    assert stderr == "cleanup failed"
    assert not cleanup_complete


def test_timeout_result_surfaces_supervisor_cleanup_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "workspace"
    _create_mock_authority(repo_root, "integration")
    monkeypatch.setattr(
        orchestrator_module, "COORDINATOR_INTERRUPT_POLL_SECONDS", 2.0
    )

    class FailedCleanupSupervisor:
        returncode: int | None = None
        communicate_calls = 0

        def terminate(self) -> None:
            pass

        def communicate(self, *, timeout: float) -> tuple[str, str]:
            self.communicate_calls += 1
            if self.communicate_calls == 1:
                time.sleep(timeout + 0.01)
                raise subprocess.TimeoutExpired("supervisor", timeout)
            self.returncode = 125
            return "supervisor output", "cleanup failed"

    supervisor = FailedCleanupSupervisor()
    monkeypatch.setattr(orchestrator_module, "_get_git_head", lambda _path: FAKE_SHA)
    monkeypatch.setattr(
        orchestrator_module.subprocess, "Popen", lambda *_args, **_kwargs: supervisor
    )

    result = run_single_preflight(
        authority="integration", repo_root=repo_root, timeout=1
    )

    assert result.status == "TIMEOUT"
    assert (
        "authority supervisor did not complete bounded descendant cleanup"
        in result.failure_excerpt
    )


def test_timeout_reports_incomplete_cleanup_when_supervisor_is_signal_killed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "workspace"
    _create_mock_authority(repo_root, "integration")

    class SignalKilledSupervisor:
        pid = 4242
        returncode = -signal.SIGKILL

        def terminate(self) -> None:
            pass

        def communicate(self, *, timeout: float) -> tuple[str, str]:
            assert timeout == orchestrator_module.SUPERVISOR_CLEANUP_TIMEOUT_SECONDS
            return "", ""

    supervisor = SignalKilledSupervisor()
    monkeypatch.setattr(orchestrator_module, "_get_git_head", lambda _path: FAKE_SHA)
    monkeypatch.setattr(
        orchestrator_module.subprocess, "Popen", lambda *_args, **_kwargs: supervisor
    )

    result = run_single_preflight(
        authority="integration", repo_root=repo_root, timeout=0
    )

    assert result.status == "TIMEOUT"
    assert (
        "authority supervisor did not complete bounded descendant cleanup"
        in result.failure_excerpt
    )


def test_pipe_error_result_surfaces_supervisor_cleanup_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "workspace"
    _create_mock_authority(repo_root, "integration")

    class FailedCleanupSupervisor:
        returncode: int | None = None
        communicate_calls = 0

        def terminate(self) -> None:
            pass

        def communicate(self, *, timeout: float) -> tuple[str, str]:
            self.communicate_calls += 1
            if self.communicate_calls == 1:
                raise OSError("controlled pipe read error")
            self.returncode = 125
            return "supervisor output", "cleanup failed"

    supervisor = FailedCleanupSupervisor()
    monkeypatch.setattr(orchestrator_module, "_get_git_head", lambda _path: FAKE_SHA)
    monkeypatch.setattr(
        orchestrator_module.subprocess, "Popen", lambda *_args, **_kwargs: supervisor
    )

    result = run_single_preflight(
        authority="integration", repo_root=repo_root, timeout=1
    )

    assert result.status == "FAIL"
    assert "controlled pipe read error" in result.failure_excerpt
    assert (
        "authority supervisor did not complete bounded descendant cleanup"
        in result.failure_excerpt
    )


def test_pipe_errors_during_cleanup_force_supervisor_termination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "workspace"
    _create_mock_authority(repo_root, "integration")

    class BrokenPipeSupervisor:
        pid = 4242
        returncode: int | None = None
        communicate_calls = 0
        wait_calls = 0
        stdout = None
        stderr = None

        def terminate(self) -> None:
            pass

        def communicate(self, *, timeout: float) -> tuple[str, str]:
            self.communicate_calls += 1
            raise OSError(f"controlled pipe read error {self.communicate_calls}")

        def wait(self, *, timeout: float) -> int:
            self.wait_calls += 1
            if self.wait_calls == 1:
                raise subprocess.TimeoutExpired("supervisor", timeout)
            self.returncode = -signal.SIGKILL
            return self.returncode

    supervisor = BrokenPipeSupervisor()
    killed_groups: list[tuple[int, int]] = []
    monkeypatch.setattr(orchestrator_module, "_get_git_head", lambda _path: FAKE_SHA)
    monkeypatch.setattr(
        orchestrator_module.subprocess, "Popen", lambda *_args, **_kwargs: supervisor
    )
    monkeypatch.setattr(
        orchestrator_module.os,
        "killpg",
        lambda process_group, signum: killed_groups.append((process_group, signum)),
    )

    result = run_single_preflight(
        authority="integration", repo_root=repo_root, timeout=1
    )

    assert result.status == "FAIL"
    assert "controlled pipe read error 1" in result.failure_excerpt
    assert (
        "authority supervisor did not complete bounded descendant cleanup"
        in result.failure_excerpt
    )
    assert killed_groups == [(supervisor.pid, signal.SIGKILL)]
    assert supervisor.communicate_calls == 2
    assert supervisor.wait_calls == 2


def test_pipe_read_failures_wait_for_real_supervisor_tree_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "workspace"
    worktree = _create_mock_authority(repo_root, "integration")
    authority_pid_file = tmp_path / "authority.pid"
    child_pid_file = tmp_path / "child.pid"
    child_code = (
        "import os, signal; os.setsid(); "
        "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
        f"open({str(child_pid_file)!r}, 'w').write(str(os.getpid())); "
        "signal.pause()"
    )
    (worktree / "scripts" / "run_integration_preflight.py").write_text(
        "import os, signal, subprocess, sys\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        f"open({str(authority_pid_file)!r}, 'w').write(str(os.getpid()))\n"
        f"child = subprocess.Popen([sys.executable, '-c', {child_code!r}])\n"
        "signal.pause()\n",
        encoding="utf-8",
    )

    real_popen = subprocess.Popen
    wrapped_processes = []

    class PipeReadErrorProcess:
        def __init__(self, *args, **kwargs):
            self.process = real_popen(*args, **kwargs)
            wrapped_processes.append(self)

        @property
        def pid(self):
            return self.process.pid

        @property
        def returncode(self):
            return self.process.returncode

        @property
        def stdout(self):
            return self.process.stdout

        @property
        def stderr(self):
            return self.process.stderr

        def communicate(self, *, timeout: float) -> tuple[str, str]:
            assert _wait_for_path(child_pid_file, timeout=5.0)
            raise OSError("controlled supervisor pipe read error")

        def terminate(self) -> None:
            self.process.terminate()

        def kill(self) -> None:
            self.process.kill()

        def send_signal(self, signum: int) -> None:
            self.process.send_signal(signum)

        def wait(self, *, timeout: float) -> int:
            return self.process.wait(timeout=timeout)

    monkeypatch.setattr(orchestrator_module, "_get_git_head", lambda _path: FAKE_SHA)
    monkeypatch.setattr(
        orchestrator_module.subprocess, "Popen", PipeReadErrorProcess
    )

    result = run_single_preflight(
        authority="integration", repo_root=repo_root, timeout=10
    )

    authority_pid = int(authority_pid_file.read_text(encoding="utf-8"))
    child_pid = int(child_pid_file.read_text(encoding="utf-8"))
    assert result.status == "FAIL"
    assert "controlled supervisor pipe read error" in result.failure_excerpt
    assert wrapped_processes[0].returncode not in (None, 125)
    assert not _pid_exists(authority_pid)
    assert not _pid_exists(child_pid)


def test_pipe_read_failure_reports_unverified_real_supervisor_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "workspace"
    worktree = _create_mock_authority(repo_root, "integration")
    authority_pid_file = tmp_path / "authority.pid"
    child_pid_file = tmp_path / "child.pid"
    child_code = (
        "import os, signal; os.setsid(); "
        "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
        f"open({str(child_pid_file)!r}, 'w').write(str(os.getpid())); "
        "signal.pause()"
    )
    (worktree / "scripts" / "run_integration_preflight.py").write_text(
        "import os, signal, subprocess, sys\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        f"open({str(authority_pid_file)!r}, 'w').write(str(os.getpid()))\n"
        f"subprocess.Popen([sys.executable, '-c', {child_code!r}])\n"
        "signal.pause()\n",
        encoding="utf-8",
    )

    supervisor_directory = tmp_path / "supervisor"
    supervisor_directory.mkdir()
    supervisor_path = supervisor_directory / "_authority_supervisor.py"
    supervisor_source = (ROOT / "scripts" / "_authority_supervisor.py").read_text(
        encoding="utf-8"
    )
    main_marker = "\ndef main(argv: list[str] | None = None) -> int:\n"
    assert main_marker in supervisor_source
    failure_hook = (
        "\n_signal_adopted_children_for_test = _signal_adopted_children\n"
        "def _signal_adopted_children(signum: int, timeout: float) -> bool:\n"
        "    _signal_adopted_children_for_test(signum, timeout)\n"
        "    return False\n"
    )
    supervisor_path.write_text(
        supervisor_source.replace(main_marker, failure_hook + main_marker),
        encoding="utf-8",
    )

    real_popen = subprocess.Popen
    wrapped_processes = []

    class PipeReadErrorProcess:
        def __init__(self, *args, **kwargs):
            self.process = real_popen(*args, **kwargs)
            wrapped_processes.append(self)

        @property
        def pid(self):
            return self.process.pid

        @property
        def returncode(self):
            return self.process.returncode

        @property
        def stdout(self):
            return self.process.stdout

        @property
        def stderr(self):
            return self.process.stderr

        def communicate(self, *, timeout: float) -> tuple[str, str]:
            assert _wait_for_path(child_pid_file, timeout=5.0)
            raise OSError("controlled supervisor pipe read error")

        def terminate(self) -> None:
            self.process.terminate()

        def kill(self) -> None:
            self.process.kill()

        def send_signal(self, signum: int) -> None:
            self.process.send_signal(signum)

        def wait(self, *, timeout: float) -> int:
            return self.process.wait(timeout=timeout)

    monkeypatch.setattr(
        orchestrator_module,
        "__file__",
        str(supervisor_directory / "orchestrate_preflights.py"),
    )
    monkeypatch.setattr(orchestrator_module, "_get_git_head", lambda _path: FAKE_SHA)
    monkeypatch.setattr(
        orchestrator_module.subprocess, "Popen", PipeReadErrorProcess
    )

    result = run_single_preflight(
        authority="integration", repo_root=repo_root, timeout=10
    )

    authority_pid = int(authority_pid_file.read_text(encoding="utf-8"))
    child_pid = int(child_pid_file.read_text(encoding="utf-8"))
    assert result.status == "FAIL"
    assert "controlled supervisor pipe read error" in result.failure_excerpt
    assert (
        "authority supervisor did not complete bounded descendant cleanup"
        in result.failure_excerpt
    )
    assert wrapped_processes[0].returncode not in (
        None,
        orchestrator_module.SUPERVISOR_STOPPED_CLEANLY_EXIT_CODE,
        125,
    )
    assert not _pid_exists(authority_pid)
    assert not _pid_exists(child_pid)


def test_pipe_read_failure_runs_real_supervisor_lifecycle_fallback_before_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "workspace"
    worktree = _create_mock_authority(repo_root, "integration")
    authority_pid_file = tmp_path / "authority.pid"
    child_pid_file = tmp_path / "child.pid"
    child_code = (
        "import os, signal; os.setsid(); "
        "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
        f"open({str(child_pid_file)!r}, 'w').write(str(os.getpid())); "
        "signal.pause()"
    )
    (worktree / "scripts" / "run_integration_preflight.py").write_text(
        "import os, signal, subprocess, sys\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        f"open({str(authority_pid_file)!r}, 'w').write(str(os.getpid()))\n"
        f"subprocess.Popen([sys.executable, '-c', {child_code!r}])\n"
        "signal.pause()\n",
        encoding="utf-8",
    )

    supervisor_directory = tmp_path / "lifecycle-error-supervisor"
    supervisor_directory.mkdir()
    supervisor_path = supervisor_directory / "_authority_supervisor.py"
    supervisor_source = (ROOT / "scripts" / "_authority_supervisor.py").read_text(
        encoding="utf-8"
    )
    finish_marker = "    process_group_id = process.pid\n"
    assert finish_marker in supervisor_source
    supervisor_path.write_text(
        supervisor_source.replace(
            finish_marker,
            '    raise OSError("controlled authority lifecycle failure")\n'
            + finish_marker,
            1,
        ),
        encoding="utf-8",
    )

    real_popen = subprocess.Popen
    wrapped_processes = []

    class PipeReadErrorProcess:
        def __init__(self, *args, **kwargs):
            self.process = real_popen(*args, **kwargs)
            wrapped_processes.append(self)

        @property
        def pid(self):
            return self.process.pid

        @property
        def returncode(self):
            return self.process.returncode

        @property
        def stdout(self):
            return self.process.stdout

        @property
        def stderr(self):
            return self.process.stderr

        def communicate(self, *, timeout: float) -> tuple[str, str]:
            assert _wait_for_path(child_pid_file, timeout=5.0)
            raise OSError("controlled supervisor pipe read error")

        def terminate(self) -> None:
            self.process.terminate()

        def kill(self) -> None:
            self.process.kill()

        def send_signal(self, signum: int) -> None:
            self.process.send_signal(signum)

        def wait(self, *, timeout: float) -> int:
            return self.process.wait(timeout=timeout)

    monkeypatch.setattr(
        orchestrator_module,
        "__file__",
        str(supervisor_directory / "orchestrate_preflights.py"),
    )
    monkeypatch.setattr(orchestrator_module, "_get_git_head", lambda _path: FAKE_SHA)
    monkeypatch.setattr(
        orchestrator_module.subprocess, "Popen", PipeReadErrorProcess
    )

    result = run_single_preflight(
        authority="integration", repo_root=repo_root, timeout=10
    )

    authority_pid = int(authority_pid_file.read_text(encoding="utf-8"))
    child_pid = int(child_pid_file.read_text(encoding="utf-8"))
    assert result.status == "FAIL"
    assert "controlled supervisor pipe read error" in result.failure_excerpt
    assert (
        "authority supervisor did not complete bounded descendant cleanup"
        in result.failure_excerpt
    )
    assert wrapped_processes[0].returncode == 125
    assert not _pid_exists(authority_pid)
    assert not _pid_exists(child_pid)


def test_windows_supervisor_uses_control_break_and_private_process_group(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(orchestrator_module.os, "name", "nt")
    monkeypatch.setattr(
        orchestrator_module.subprocess,
        "CREATE_NEW_PROCESS_GROUP",
        512,
        raising=False,
    )
    monkeypatch.setattr(
        orchestrator_module.signal, "CTRL_BREAK_EVENT", 1, raising=False
    )
    process = Mock()
    process.returncode = 124
    process.communicate.return_value = ("", "")

    assert orchestrator_module._supervisor_process_options() == {
        "creationflags": 512
    }
    _, _, cleanup_complete = orchestrator_module._stop_authority_supervisor(
        process
    )

    process.send_signal.assert_called_once_with(1)
    process.terminate.assert_not_called()
    assert cleanup_complete


def test_supervisor_installs_windows_break_handler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registered: dict[int, object] = {}
    monkeypatch.setattr(_authority_supervisor.signal, "SIGBREAK", 21, raising=False)
    monkeypatch.setattr(
        _authority_supervisor.signal,
        "signal",
        lambda signum, handler: registered.__setitem__(signum, handler),
    )

    _authority_supervisor._install_stop_handlers()

    assert registered[21] is _authority_supervisor._request_stop


@pytest.mark.skipif(sys.platform != "linux", reason="Linux-specific subreaper contract")
def test_linux_preflight_fails_before_launch_without_subreaper_support(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "workspace"
    worktree = _create_mock_authority(repo_root, "policy")
    started_file = tmp_path / "started"
    (worktree / "scripts" / "run_policy_preflight.py").write_text(
        f"from pathlib import Path; Path({str(started_file)!r}).write_text('yes')\n",
        encoding="utf-8",
    )

    def unavailable() -> bool:
        raise OSError("subreaper unavailable")

    monkeypatch.setattr(
        "scripts._authority_supervisor._enable_linux_child_subreaper", unavailable
    )
    result = _authority_supervisor.main(
        ["--", sys.executable, str(worktree / "scripts" / "run_policy_preflight.py")]
    )

    assert result == 125
    assert not started_file.exists()


@pytest.mark.skipif(sys.platform != "linux", reason="Linux-specific subreaper contract")
def test_linux_preflight_fails_before_launch_without_procfs_process_records(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "workspace"
    worktree = _create_mock_authority(repo_root, "policy")
    started_file = tmp_path / "started"
    script = worktree / "scripts" / "run_policy_preflight.py"
    script.write_text(
        f"from pathlib import Path; Path({str(started_file)!r}).write_text('yes')\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(_authority_supervisor, "_enable_linux_child_subreaper", lambda: True)
    monkeypatch.setattr(_authority_supervisor, "_direct_child_pids", lambda: None)

    result = _authority_supervisor.main(["--", sys.executable, str(script)])

    assert result == 125
    assert not started_file.exists()


def test_direct_child_enumeration_uses_standard_proc_stat_records(
    tmp_path: Path,
) -> None:
    proc_root = tmp_path / "proc"
    proc_root.mkdir()
    expected_parent = 700
    records = (
        (801, "authority worker", expected_parent),
        (802, "unrelated worker", 701),
        (803, "worker ) with spaces", expected_parent),
    )
    for pid, command, parent_pid in records:
        process_dir = proc_root / str(pid)
        process_dir.mkdir()
        (process_dir / "stat").write_text(
            f"{pid} ({command}) S {parent_pid} 1 1 0 0\n",
            encoding="ascii",
        )

    non_ascii_pid = 804
    non_ascii_process_dir = proc_root / str(non_ascii_pid)
    non_ascii_process_dir.mkdir()
    (non_ascii_process_dir / "stat").write_bytes(
        b"804 (worker \xff with bytes) S 700 1 1 0 0\n"
    )

    assert not (proc_root / "801" / "task" / "801" / "children").exists()
    assert _authority_supervisor._direct_child_pids(
        proc_root=proc_root,
        parent_pid=expected_parent,
    ) == (801, 803, non_ascii_pid)


def test_direct_child_enumeration_tracks_a_child_with_changed_credentials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    proc_root = tmp_path / "proc"
    proc_root.mkdir()
    child = proc_root / "901"
    child.mkdir()
    (child / "stat").write_text("901 (dropped uid worker) S 700 1 1 0 0\n")
    original_stat = Path.stat

    def stat_with_different_owner(path: Path, *args, **kwargs):
        result = original_stat(path, *args, **kwargs)
        if path == child:
            fields = list(result)
            fields[4] = 65534
            return os.stat_result(fields)
        return result

    monkeypatch.setattr(Path, "stat", stat_with_different_owner)
    assert _authority_supervisor._direct_child_pids(
        proc_root=proc_root, parent_pid=700
    ) == (901,)


@pytest.mark.skipif(sys.platform != "linux", reason="Linux-specific subreaper contract")
def test_authority_spawn_failure_is_reported_without_launching_child(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_to_spawn(*_: object, **__: object) -> subprocess.Popen[bytes]:
        raise OSError("synthetic authority spawn failure")

    monkeypatch.setattr(_authority_supervisor, "_enable_linux_child_subreaper", lambda: True)
    monkeypatch.setattr(_authority_supervisor.subprocess, "Popen", fail_to_spawn)

    assert _authority_supervisor.main(["--", "/not/a/real/authority"]) == 126


def test_timeout_terminates_nested_authority_processes(tmp_path: Path) -> None:
    _assert_nested_timeout_is_reaped(tmp_path / "workspace", tmp_path)


@pytest.mark.skipif(
    sys.platform != "linux" or os.geteuid() != 0,
    reason="requires Linux and root to change descendant credentials",
)
def test_timeout_reaps_adopted_descendant_after_uid_change(tmp_path: Path) -> None:
    _assert_nested_timeout_is_reaped(
        tmp_path / "workspace", tmp_path, drop_uid=65534
    )


def test_repeated_timeout_runs_do_not_leak_child_processes(tmp_path: Path) -> None:
    for run_number in range(3):
        run_root = tmp_path / f"run-{run_number}"
        _assert_nested_timeout_is_reaped(
            run_root / "workspace", run_root / "processes"
        )


@pytest.mark.skipif(sys.platform != "linux", reason="Linux-specific subreaper contract")
@pytest.mark.parametrize(
    ("exit_code", "expected_status"),
    ((0, "PASS"), (7, "FAIL")),
    ids=("pass", "fail"),
)
def test_normal_completion_reaps_adopted_descendants(
    tmp_path: Path, exit_code: int, expected_status: str
) -> None:
    result = _run_normal_completion_case(tmp_path, exit_code)
    assert result.status == expected_status


@pytest.mark.skipif(sys.platform != "linux", reason="Linux-specific subreaper contract")
def test_normal_exit_does_not_signal_a_reaped_authority_process_group(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "workspace"
    worktree = _create_mock_authority(repo_root, "policy")
    authority_pid_file = tmp_path / "authority.pid"
    child_pid_file = tmp_path / "child.pid"
    stale_group_signals = tmp_path / "stale-group-signals.log"
    child_code = (
        "import os, pathlib, signal, sys, time\n"
        "os.setsid()\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        "pathlib.Path(sys.argv[1]).write_text(str(os.getpid()), encoding='utf-8')\n"
        "while True:\n"
        "    time.sleep(1)\n"
    )
    (worktree / "scripts" / "run_policy_preflight.py").write_text(
        "import os, pathlib, subprocess, sys, time\n"
        f"child_code = {child_code!r}\n"
        "child = subprocess.Popen([sys.executable, '-c', child_code, "
        f"{str(child_pid_file)!r}], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n"
        f"child_pid_file = pathlib.Path({str(child_pid_file)!r})\n"
        "deadline = time.monotonic() + 5\n"
        "while not child_pid_file.exists() and time.monotonic() < deadline:\n"
        "    time.sleep(0.001)\n"
        "if not child_pid_file.exists():\n"
        "    raise RuntimeError('detached child did not start')\n"
        f"pathlib.Path({str(authority_pid_file)!r}).write_text("
        "str(os.getpid()), encoding='utf-8')\n",
        encoding="utf-8",
    )

    supervisor_directory = tmp_path / "supervisor"
    supervisor_directory.mkdir()
    supervisor_path = supervisor_directory / "_authority_supervisor.py"
    supervisor_source = (ROOT / "scripts" / "_authority_supervisor.py").read_text(
        encoding="utf-8"
    )
    main_marker = "\ndef main(argv: list[str] | None = None) -> int:\n"
    assert main_marker in supervisor_source
    signal_audit = (
        "\n_signal_authority_group_before_audit = _signal_authority_group\n"
        "def _signal_authority_group(process_group_id: int, signum: int) -> None:\n"
        f"    leader_file = Path({str(authority_pid_file)!r})\n"
        "    if leader_file.exists() and int("
        "leader_file.read_text(encoding='utf-8')) == process_group_id:\n"
        f"        audit_file = Path({str(stale_group_signals)!r})\n"
        "        try:\n"
        "            Path(f'/proc/{process_group_id}/stat').read_bytes()\n"
        "            leader_present = True\n"
        "        except FileNotFoundError:\n"
        "            leader_present = False\n"
        "        with audit_file.open('a', encoding='utf-8') as stream:\n"
        "            stream.write(f'{signum} {leader_present}\\n')\n"
        "    _signal_authority_group_before_audit(process_group_id, signum)\n"
    )
    supervisor_path.write_text(
        supervisor_source.replace(main_marker, signal_audit + main_marker),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        orchestrator_module,
        "__file__",
        str(supervisor_directory / "orchestrate_preflights.py"),
    )
    result = run_single_preflight(authority="policy", repo_root=repo_root, timeout=5.0)

    assert result.status == "PASS"
    assert _wait_for_pid_absent(int(child_pid_file.read_text(encoding="utf-8")))
    if stale_group_signals.exists():
        assert all(
            line.endswith(" True")
            for line in stale_group_signals.read_text(encoding="utf-8").splitlines()
        )


@pytest.mark.skipif(
    os.name != "posix" or not _authority_supervisor._supports_unreaped_child_observation(),
    reason="requires POSIX waitid(WNOWAIT)",
)
def test_posix_without_subreaper_signals_only_while_group_id_is_reserved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "workspace"
    worktree = _create_mock_authority(repo_root, "policy")
    authority_pid_file = tmp_path / "authority.pid"
    signal_audit = tmp_path / "group-signals.log"
    (worktree / "scripts" / "run_policy_preflight.py").write_text(
        "import os, pathlib\n"
        f"pathlib.Path({str(authority_pid_file)!r}).write_text(\n"
        "    str(os.getpid()), encoding='utf-8'\n"
        ")\n",
        encoding="utf-8",
    )

    supervisor_directory = tmp_path / "supervisor"
    supervisor_directory.mkdir()
    supervisor_path = supervisor_directory / "_authority_supervisor.py"
    supervisor_source = (ROOT / "scripts" / "_authority_supervisor.py").read_text(
        encoding="utf-8"
    )
    main_marker = "\ndef main(argv: list[str] | None = None) -> int:\n"
    assert main_marker in supervisor_source
    signal_audit_wrapper = (
        "\n_signal_group_before_audit = _signal_authority_group\n"
        "def _signal_authority_group(process_group_id: int, signum: int) -> None:\n"
        f"    leader_file = Path({str(authority_pid_file)!r})\n"
        "    if leader_file.exists():\n"
        "        leader_id = int(leader_file.read_text(encoding='utf-8'))\n"
        "    else:\n"
        "        leader_id = None\n"
        "    if leader_id == process_group_id:\n"
        "        leader_present = Path(f'/proc/{process_group_id}/stat').exists()\n"
        f"        with Path({str(signal_audit)!r}).open('a', encoding='utf-8') as stream:\n"
        "            stream.write(f'{signum} {leader_present}\\n')\n"
        "    _signal_group_before_audit(process_group_id, signum)\n"
    )
    supervisor_source = supervisor_source.replace(main_marker, signal_audit_wrapper + main_marker)
    supervisor_source = supervisor_source.replace(
        "        subreaper_enabled = _enable_linux_child_subreaper()\n",
        "        subreaper_enabled = False\n",
    )
    supervisor_source = supervisor_source.replace(
        "NATURAL_EXIT_GRACE_SECONDS = 0.25",
        "NATURAL_EXIT_GRACE_SECONDS = 0.01",
    )
    supervisor_path.write_text(supervisor_source, encoding="utf-8")
    monkeypatch.setattr(
        orchestrator_module,
        "__file__",
        str(supervisor_directory / "orchestrate_preflights.py"),
    )

    result = run_single_preflight(authority="policy", repo_root=repo_root, timeout=5.0)

    assert result.status == "PASS"
    signals = signal_audit.read_text(encoding="utf-8").splitlines()
    assert len(signals) == 2
    assert all(line.endswith(" True") for line in signals)
    assert not _pid_exists(int(authority_pid_file.read_text(encoding="utf-8")))


@pytest.mark.skipif(
    sys.platform != "linux" or os.geteuid() != 0,
    reason="requires Linux and root to change descendant credentials",
)
def test_normal_completion_reaps_adopted_descendant_after_uid_change(
    tmp_path: Path,
) -> None:
    with TemporaryDirectory(prefix="policy-adopted-uid-", dir="/tmp") as directory:
        shared_root = Path(directory)
        shared_root.chmod(0o777)
        result = _run_normal_completion_case(shared_root, 0, drop_uid=65534)
    assert result.status == "PASS"


@pytest.mark.skipif(sys.platform != "linux", reason="Linux-specific subreaper contract")
def test_repeated_pass_fail_completions_do_not_leak_adopted_children(
    tmp_path: Path,
) -> None:
    for run_number in range(4):
        exit_code = 0 if run_number % 2 == 0 else 7
        result = _run_normal_completion_case(
            tmp_path / f"run-{run_number}", exit_code
        )
        assert result.status == ("PASS" if exit_code == 0 else "FAIL")


def test_spawn_failure_is_reported_without_leaking_a_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "workspace"
    _create_mock_authority(repo_root, "policy")

    def fail_to_spawn(*_: object, **__: object) -> subprocess.Popen[str]:
        raise OSError("synthetic spawn failure")

    monkeypatch.setattr("scripts.orchestrate_preflights._get_git_head", lambda _: FAKE_SHA)
    monkeypatch.setattr("scripts.orchestrate_preflights.subprocess.Popen", fail_to_spawn)
    result = run_single_preflight(authority="policy", repo_root=repo_root)

    assert result.status == "FAIL"
    assert "synthetic spawn failure" in result.failure_excerpt


@pytest.mark.skipif(sys.platform != "linux", reason="Linux-specific subreaper contract")
def test_authority_cleanup_does_not_reap_a_concurrent_groups_child(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    b_parent_pid_file = tmp_path / "b-parent.pid"
    b_child_pid_file = tmp_path / "b-child.pid"
    b_adopted_file = tmp_path / "b-adopted"
    b_release_child = tmp_path / "b-release-child"
    b_release_parent = tmp_path / "b-release-parent"
    _create_mock_authority(
        workspace, "policy", custom_script="print('authority A passed')\n"
    )
    b = _create_mock_authority(workspace, "composition")

    child_code = (
        "import os, pathlib, sys, time\n"
        "os.setsid()\n"
        "intermediate_pid = int(sys.argv[1])\n"
        "adopted = pathlib.Path(sys.argv[2])\n"
        "release = pathlib.Path(sys.argv[3])\n"
        "while os.getppid() == intermediate_pid:\n"
        "    time.sleep(0.001)\n"
        "adopted.write_text(str(os.getppid()), encoding='utf-8')\n"
        "while not release.exists():\n"
        "    time.sleep(0.001)\n"
    )
    intermediate_code = (
        "import os, pathlib, subprocess, sys\n"
        f"child_code = {child_code!r}\n"
        "child = subprocess.Popen([sys.executable, '-c', child_code, "
        "str(os.getpid()), "
        f"{str(b_adopted_file)!r}, {str(b_release_child)!r}], "
        "stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n"
        f"pathlib.Path({str(b_child_pid_file)!r}).write_text(str(child.pid))\n"
    )
    b_script = b / "scripts" / "run_composition_preflight.py"
    b_script.write_text(
        "import os, pathlib, subprocess, sys, time\n"
        f"intermediate_code = {intermediate_code!r}\n"
        "intermediate = subprocess.Popen([sys.executable, '-c', intermediate_code], "
        "stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n"
        "intermediate.wait()\n"
        f"pathlib.Path({str(b_parent_pid_file)!r}).write_text(str(os.getpid()))\n"
        f"release_parent = pathlib.Path({str(b_release_parent)!r})\n"
        "while not release_parent.exists():\n"
        "    time.sleep(0.001)\n",
        encoding="utf-8",
    )

    b_result: list[AuthorityRunResult] = []
    b_errors: list[BaseException] = []

    def run_b() -> None:
        try:
            b_result.append(
                run_single_preflight(
                    authority="composition", repo_root=workspace, timeout=10.0
                )
            )
        except BaseException as exc:
            b_errors.append(exc)

    b_thread = threading.Thread(target=run_b, daemon=True)
    b_thread.start()
    b_parent_pid: int | None = None
    try:
        assert _wait_for_path(b_adopted_file)
        b_parent_pid = int(b_parent_pid_file.read_text(encoding="utf-8"))
        b_child_pid = int(b_child_pid_file.read_text(encoding="utf-8"))
        b_supervisor_pid = int(b_adopted_file.read_text(encoding="utf-8"))
        assert b_supervisor_pid != b_parent_pid
        child_state = _process_state_and_parent(b_child_pid)
        assert child_state is not None
        assert child_state[0] != "Z"
        assert child_state[1] == b_supervisor_pid

        b_release_child.write_text("release", encoding="utf-8")
        deadline = time.monotonic() + 5.0
        while True:
            child_state = _process_state_and_parent(b_child_pid)
            if child_state is not None and child_state[0] == "Z":
                break
            assert time.monotonic() < deadline, "authority B descendant did not exit"
            threading.Event().wait(0.01)
        assert child_state[1] == b_supervisor_pid

        a_result = run_single_preflight(
            authority="policy", repo_root=workspace, timeout=5.0
        )
        assert a_result.status == "PASS"

        # B's adopted zombie must remain waitable until B's own finalizer runs.
        assert _process_state_and_parent(b_child_pid) == ("Z", b_supervisor_pid)
        assert b_thread.is_alive()

        b_release_parent.write_text("release", encoding="utf-8")
        b_thread.join(timeout=5.0)
        assert not b_thread.is_alive()
        assert not b_errors
        assert b_result[0].status == "PASS"
        assert _wait_for_pid_absent(b_child_pid)
    finally:
        b_release_child.write_text("release", encoding="utf-8")
        b_release_parent.write_text("release", encoding="utf-8")
        b_thread.join(timeout=5.0)
        if b_parent_pid is None and b_parent_pid_file.exists():
            b_parent_pid = int(b_parent_pid_file.read_text(encoding="utf-8"))
        if b_parent_pid is not None:
            _cleanup_test_process_group(b_parent_pid)
        if b_child_pid_file.exists():
            try:
                os.kill(int(b_child_pid_file.read_text(encoding="utf-8")), signal.SIGKILL)
            except ProcessLookupError:
                pass


def test_static_worker_batches_never_exceed_global_budget() -> None:
    authorities = ("policy", "composition", "modeling", "integration", "site")
    expected = {
        1: (
            (("policy", 1),),
            (("composition", 1),),
            (("modeling", 1),),
            (("integration", 1),),
            (("site", 1),),
        ),
        2: (
            (("policy", 1), ("composition", 1)),
            (("modeling", 1), ("integration", 1)),
            (("site", 2),),
        ),
        4: (
            (("policy", 1), ("composition", 1), ("modeling", 1), ("integration", 1)),
            (("site", 4),),
        ),
    }
    for jobs, expected_batches in expected.items():
        batches = allocate_worker_batches(authorities, jobs)
        assert batches == expected_batches
        assert all(sum(workers for _, workers in batch) <= jobs for batch in batches)
        assert tuple(authority for batch in batches for authority, _ in batch) == authorities


def test_active_authority_budgets_obey_global_limit_with_barriers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    authorities = ("policy", "composition", "modeling", "integration", "site")
    batches = allocate_worker_batches(authorities, 2)
    barriers = {
        index: threading.Barrier(len(batch))
        for index, batch in enumerate(batches, start=1)
    }
    active_workers = 0
    peak_workers = 0
    lock = threading.Lock()

    def fake_run_single(
        authority: str,
        *,
        allocated_workers: int,
        allocation_batch: int,
        **_: object,
    ) -> AuthorityRunResult:
        nonlocal active_workers, peak_workers
        with lock:
            active_workers += allocated_workers
            peak_workers = max(peak_workers, active_workers)
        barriers[allocation_batch].wait(timeout=2.0)
        with lock:
            active_workers -= allocated_workers
        return AuthorityRunResult(
            authority=authority,
            status="PASS",
            head_sha=FAKE_SHA,
            command=["mock", "--jobs", str(allocated_workers)],
            working_directory=str(tmp_path),
            elapsed_seconds=0.0,
            exit_code=0,
            allocated_workers=allocated_workers,
            allocation_batch=allocation_batch,
        )

    monkeypatch.setattr(
        "scripts.orchestrate_preflights.run_single_preflight", fake_run_single
    )
    result = orchestrate_preflights(
        authorities=authorities, repo_root=tmp_path, global_jobs=2
    )

    assert result["overall_status"] == "PASSED"
    assert peak_workers == 2
    assert active_workers == 0
    assert [row["authority"] for row in result["authorities"]] == list(authorities)


def test_missing_canonical_runner_reported_as_unavailable(tmp_path: Path) -> None:
    repo_root = tmp_path / "workspace"
    worktree = _create_mock_authority(repo_root, "policy")
    script = worktree / "scripts" / "run_policy_preflight.py"
    script.unlink()

    res = run_single_preflight(
        authority="policy",
        repo_root=repo_root,
    )
    assert res.status == "UNAVAILABLE"
    assert "entrypoint not found" in res.failure_excerpt


def test_unexpected_exact_head_fails_closed(tmp_path: Path) -> None:
    repo_root = tmp_path / "workspace"
    _create_mock_authority(repo_root, "policy", exit_code=0)

    res = run_single_preflight(
        authority="policy",
        repo_root=repo_root,
        expected_heads={"policy": FAKE_SHA},  # Different from real commit SHA
    )
    assert res.status == "FAIL"
    assert res.exit_code == 2
    assert "head mismatch" in res.failure_excerpt


def test_modeling_runner_receives_exact_head_and_allocated_budget(tmp_path: Path) -> None:
    repo_root = tmp_path / "workspace"
    worktree = _create_mock_authority(repo_root, "modeling", output_text="MODELING_PASS")
    expected_head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=worktree, check=True, capture_output=True, text=True
    ).stdout.strip()

    result = run_single_preflight(
        authority="modeling",
        repo_root=repo_root,
        expected_heads={"modeling": expected_head},
        allocated_workers=2,
    )

    assert result.status == "PASS"
    assert result.command[-4:] == ["--expected-head", expected_head, "--jobs", "2"]


def test_log_preservation_and_bounded_summary_size(tmp_path: Path) -> None:
    repo_root = tmp_path / "workspace"
    log_dir = tmp_path / "logs"
    _create_mock_authority(repo_root, "policy", output_text="DETAILED_LOG_LINE_1\nLINE_2\n")

    res = orchestrate_preflights(
        authorities=["policy"],
        repo_root=repo_root,
        log_dir=log_dir,
    )
    assert res["overall_status"] == "PASSED"
    log_file = Path(res["authorities"][0]["log_file"])
    assert log_file.is_file()
    assert log_file.parent.parent == log_dir
    log_content = log_file.read_text(encoding="utf-8")
    assert "DETAILED_LOG_LINE_1" in log_content

    second = orchestrate_preflights(
        authorities=["policy"],
        repo_root=repo_root,
        log_dir=log_dir,
    )
    second_log = Path(second["authorities"][0]["log_file"])
    assert second_log.is_file()
    assert second_log != log_file
    assert second["run_id"] != res["run_id"]

    # Check bounded summary size
    dumped = json.dumps(res, indent=2)
    assert len(dumped.encode("utf-8")) <= MAX_SUMMARY_BYTES


def test_cli_execution_with_json_output(tmp_path: Path) -> None:
    repo_root = tmp_path / "workspace"
    _create_mock_authority(repo_root, "policy", exit_code=0, output_text="POLICY_CLI_OK")

    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "orchestrate_preflights.py"),
            "policy",
            "--repo-root",
            str(repo_root),
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"CLI failed: {proc.stderr}"
    data = json.loads(proc.stdout)
    assert data["overall_status"] == "PASSED"
    assert data["authorities"][0]["authority"] == "policy"
    assert data["worker_budget"]["requested_jobs"] == 2
    assert data["worker_budget"]["max_active_allocated_workers"] == 2
    assert data["schema_version"] == 2
    assert data["kind"] == "preflight-orchestration-result"
    assert data["is_validation_evidence_only"] is True
    assert data["may_establish_acceptance"] is False
    assert data["run_id"]
    assert data["authorities"][0]["head_sha"]


def test_api_and_cli_default_to_all_authorities(tmp_path: Path) -> None:
    api_root = tmp_path / "api"
    cli_root = tmp_path / "cli"
    for repo_root in (api_root, cli_root):
        for authority in ALL_AUTHORITIES:
            _create_mock_authority(repo_root, authority, output_text=f"{authority}_OK")

    api_result = orchestrate_preflights(repo_root=api_root, global_jobs=4)
    assert api_result["overall_status"] == "PASSED"
    assert [row["authority"] for row in api_result["authorities"]] == list(
        ALL_AUTHORITIES
    )

    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "orchestrate_preflights.py"),
            "--repo-root",
            str(cli_root),
            "--jobs",
            "4",
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"CLI failed: {proc.stderr}"
    data = json.loads(proc.stdout)
    assert data["overall_status"] == "PASSED"
    assert [row["authority"] for row in data["authorities"]] == list(
        ALL_AUTHORITIES
    )
    assert data["worker_budget"]["requested_jobs"] == 4


def test_cli_rejects_invalid_or_blank_authority_names(tmp_path: Path) -> None:
    for authority in ("invalid", ""):
        proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "orchestrate_preflights.py"),
                authority,
                "--repo-root",
                str(tmp_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 2
        assert "unknown authority selection" in proc.stderr


def test_default_global_worker_budget_is_two(tmp_path: Path) -> None:
    repo_root = tmp_path / "workspace"
    _create_mock_authority(repo_root, "policy", exit_code=0, output_text="POLICY_OK")

    res = orchestrate_preflights(
        authorities=["policy"],
        repo_root=repo_root,
    )
    assert res["overall_status"] == "PASSED"
    assert res["worker_budget"]["requested_jobs"] == 2
    assert res["worker_budget"]["max_active_allocated_workers"] == 2

    with pytest.raises(ValueError, match="jobs must be at least 1"):
        orchestrate_preflights(
            authorities=["policy"],
            repo_root=repo_root,
            global_jobs=0,
        )

    with pytest.raises(ValueError, match="jobs must be at least 1"):
        orchestrate_preflights(
            authorities=["policy"],
            repo_root=repo_root,
            global_jobs=-1,
        )


def test_cli_jobs_argument_parsing_and_overrides(tmp_path: Path) -> None:
    parser = build_parser()
    args_default = parser.parse_args([])
    assert args_default.jobs == 2

    args_serial = parser.parse_args(["--jobs", "1"])
    assert args_serial.jobs == 1

    args_four = parser.parse_args(["-j", "4"])
    assert args_four.jobs == 4

    repo_root = tmp_path / "workspace"
    _create_mock_authority(repo_root, "policy", exit_code=0, output_text="POLICY_OK")

    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "orchestrate_preflights.py"),
            "policy",
            "--repo-root",
            str(repo_root),
            "--jobs",
            "1",
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"CLI failed: {proc.stderr}"
    data = json.loads(proc.stdout)
    assert data["worker_budget"]["requested_jobs"] == 1
    assert data["worker_budget"]["max_active_allocated_workers"] == 1
    assert data["worker_budget"]["max_authority_processes"] == 1

    proc_invalid = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "orchestrate_preflights.py"),
            "policy",
            "--repo-root",
            str(repo_root),
            "--jobs",
            "0",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc_invalid.returncode != 0
    assert "--jobs must be at least 1" in proc_invalid.stderr
