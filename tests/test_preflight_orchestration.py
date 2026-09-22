from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.orchestrate_preflights import (  # noqa: E402
    MAX_SUMMARY_BYTES,
    build_parser,
    orchestrate_preflights,
    run_single_preflight,
)

FAKE_SHA = "1234567890abcdef1234567890abcdef12345678"


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


def test_multiple_successful_preflights_serial(tmp_path: Path) -> None:
    repo_root = tmp_path / "workspace"
    _create_mock_authority(repo_root, "policy", exit_code=0, output_text="POLICY_PASS")
    _create_mock_authority(repo_root, "composition", exit_code=0, output_text="COMPOSITION_PASS")
    _create_mock_authority(repo_root, "modeling", exit_code=0, output_text="MODELING_PASS")

    res = orchestrate_preflights(
        authorities=["policy", "composition", "modeling"],
        repo_root=repo_root,
        concurrent_jobs=1,
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
        concurrent_jobs=3,
    )
    assert res["overall_status"] == "PASSED"
    assert res["concurrency"] == 3
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
    log_file = log_dir / "policy.log"
    assert log_file.is_file()
    log_content = log_file.read_text(encoding="utf-8")
    assert "DETAILED_LOG_LINE_1" in log_content

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
    assert data["concurrency"] == 2


def test_default_concurrency_is_two_api(tmp_path: Path) -> None:
    repo_root = tmp_path / "workspace"
    _create_mock_authority(repo_root, "policy", exit_code=0, output_text="POLICY_OK")

    res = orchestrate_preflights(
        authorities=["policy"],
        repo_root=repo_root,
    )
    assert res["overall_status"] == "PASSED"
    assert res["concurrency"] == 2

    with pytest.raises(ValueError, match="concurrent_jobs must be at least 1"):
        orchestrate_preflights(
            authorities=["policy"],
            repo_root=repo_root,
            concurrent_jobs=0,
        )

    with pytest.raises(ValueError, match="concurrent_jobs must be at least 1"):
        orchestrate_preflights(
            authorities=["policy"],
            repo_root=repo_root,
            concurrent_jobs=-1,
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
    assert data["concurrency"] == 1

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

