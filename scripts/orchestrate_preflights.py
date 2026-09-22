#!/usr/bin/env python3
"""Orchestrate canonical local preflights across repository authorities.

Provides a thin execution and normalization layer over existing authority-owned preflights:
1. Discovers and binds canonical per-authority commands and exact worktree heads.
2. Executes validations locally with finite timeouts and captured detailed logs.
3. Produces bounded, structured machine-readable results (<= 8 KiB) and a concise summary table.
4. Preserves authority boundaries: does NOT re-implement or alter authority validation semantics.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import subprocess
import sys
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

MAX_SUMMARY_BYTES = 8192
DEFAULT_TIMEOUT_SECONDS = 300

# Canonical authority definitions based on live authority contracts
CANONICAL_CONFIGS: dict[str, dict[str, Any]] = {
    "policy": {
        "worktree_rel": "policy",
        "entrypoint": "scripts/run_policy_preflight.py",
        "default_args": ["fast"],
        "supports_expected_head": True,
    },
    "composition": {
        "worktree_rel": "composition",
        "entrypoint": "scripts/run_composition_preflight.py",
        "default_args": ["fast"],
        "supports_expected_head": True,
    },
    "modeling": {
        "worktree_rel": "modeling",
        "entrypoint": "tools/qualify.py",
        "default_args": [],
        "supports_expected_head": False,
    },
    "integration": {
        "worktree_rel": "integration",
        "entrypoint": "scripts/run_integration_preflight.py",
        "default_args": ["fast"],
        "supports_expected_head": True,
    },
    "site": {
        "worktree_rel": "site",
        "entrypoint": "scripts/run_site_preflight.py",
        "default_args": ["fast"],
        "supports_expected_head": True,
    },
}

ALL_AUTHORITIES = tuple(CANONICAL_CONFIGS.keys())


@dataclass
class AuthorityRunResult:
    authority: str
    status: str  # PASS, FAIL, TIMEOUT, UNAVAILABLE, NOT_RUN
    head_sha: str
    command: list[str]
    working_directory: str
    elapsed_seconds: float
    exit_code: int | None
    log_file: str | None = None
    failure_excerpt: str | None = None


def _get_git_head(worktree: Path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "-C", str(worktree), "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.PIPE,
        ).strip()
    except Exception:
        return None


def run_single_preflight(
    authority: str,
    repo_root: Path,
    expected_heads: dict[str, str] | None = None,
    tier_overrides: dict[str, list[str]] | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    log_dir: Path | None = None,
    python_bin: str | None = None,
) -> AuthorityRunResult:
    """Execute canonical preflight for a single authority and return normalized result."""
    py_exec = python_bin or sys.executable
    cfg = CANONICAL_CONFIGS.get(authority)
    if not cfg:
        return AuthorityRunResult(
            authority=authority,
            status="UNAVAILABLE",
            head_sha="unknown",
            command=[],
            working_directory=str(repo_root),
            elapsed_seconds=0.0,
            exit_code=None,
            failure_excerpt=f"unknown authority: {authority}",
        )

    worktree = repo_root / cfg["worktree_rel"]
    if not worktree.is_dir():
        return AuthorityRunResult(
            authority=authority,
            status="UNAVAILABLE",
            head_sha="missing",
            command=[],
            working_directory=str(worktree),
            elapsed_seconds=0.0,
            exit_code=None,
            failure_excerpt=f"worktree directory does not exist: {worktree}",
        )

    actual_head = _get_git_head(worktree)
    if not actual_head:
        return AuthorityRunResult(
            authority=authority,
            status="UNAVAILABLE",
            head_sha="missing",
            command=[],
            working_directory=str(worktree),
            elapsed_seconds=0.0,
            exit_code=None,
            failure_excerpt=f"failed to obtain git rev-parse HEAD from: {worktree}",
        )

    # Check expected head if specified
    if expected_heads and authority in expected_heads:
        expected = expected_heads[authority]
        if actual_head != expected:
            return AuthorityRunResult(
                authority=authority,
                status="FAIL",
                head_sha=actual_head,
                command=[],
                working_directory=str(worktree),
                elapsed_seconds=0.0,
                exit_code=2,
                failure_excerpt=(
                    f"head mismatch for {authority}: expected {expected}, "
                    f"observed {actual_head}"
                ),
            )

    script_path = worktree / cfg["entrypoint"]
    if not script_path.is_file():
        return AuthorityRunResult(
            authority=authority,
            status="UNAVAILABLE",
            head_sha=actual_head,
            command=[str(script_path)],
            working_directory=str(worktree),
            elapsed_seconds=0.0,
            exit_code=None,
            failure_excerpt=f"canonical preflight entrypoint not found: {script_path}",
        )

    # Build command
    args = (
        tier_overrides.get(authority, cfg["default_args"])
        if tier_overrides
        else cfg["default_args"]
    )
    cmd = [py_exec, str(script_path), *args]

    if expected_heads and authority in expected_heads and cfg["supports_expected_head"]:
        cmd.extend(["--expected-head", expected_heads[authority]])

    start_time = time.monotonic()
    log_file_path: Path | None = None
    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file_path = log_dir / f"{authority}.log"

    try:
        proc = subprocess.run(
            cmd,
            cwd=worktree,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        elapsed = round(time.monotonic() - start_time, 2)
        full_output = (
            f"=== STDOUT ===\n{proc.stdout}\n=== STDERR ===\n{proc.stderr}\n"
        )

        if log_file_path:
            log_file_path.write_text(full_output, encoding="utf-8")

        if proc.returncode == 0:
            return AuthorityRunResult(
                authority=authority,
                status="PASS",
                head_sha=actual_head,
                command=cmd,
                working_directory=str(worktree),
                elapsed_seconds=elapsed,
                exit_code=0,
                log_file=str(log_file_path) if log_file_path else None,
            )
        else:
            # Extract concise failure excerpt (last ~10 lines of stderr/stdout)
            combined = proc.stderr.strip() or proc.stdout.strip()
            lines = combined.splitlines()
            excerpt = "\n".join(lines[-10:]) if len(lines) > 10 else combined
            return AuthorityRunResult(
                authority=authority,
                status="FAIL",
                head_sha=actual_head,
                command=cmd,
                working_directory=str(worktree),
                elapsed_seconds=elapsed,
                exit_code=proc.returncode,
                log_file=str(log_file_path) if log_file_path else None,
                failure_excerpt=excerpt,
            )

    except subprocess.TimeoutExpired:
        elapsed = round(time.monotonic() - start_time, 2)
        if log_file_path:
            log_file_path.write_text(
                f"TIMEOUT after {timeout} seconds\n", encoding="utf-8"
            )
        return AuthorityRunResult(
            authority=authority,
            status="TIMEOUT",
            head_sha=actual_head,
            command=cmd,
            working_directory=str(worktree),
            elapsed_seconds=elapsed,
            exit_code=None,
            log_file=str(log_file_path) if log_file_path else None,
            failure_excerpt=f"execution exceeded {timeout}s timeout limit",
        )
    except Exception as exc:
        elapsed = round(time.monotonic() - start_time, 2)
        return AuthorityRunResult(
            authority=authority,
            status="FAIL",
            head_sha=actual_head,
            command=cmd,
            working_directory=str(worktree),
            elapsed_seconds=elapsed,
            exit_code=1,
            failure_excerpt=f"subprocess execution failed with error: {exc}",
        )


def orchestrate_preflights(
    authorities: Sequence[str] | None = None,
    repo_root: Path | None = None,
    expected_heads: dict[str, str] | None = None,
    tier_overrides: dict[str, list[str]] | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    concurrent_jobs: int = 1,
    log_dir: Path | None = None,
    python_bin: str | None = None,
) -> dict[str, Any]:
    """Orchestrate canonical preflights across specified authorities."""
    selected_authorities = list(authorities or ALL_AUTHORITIES)
    root = (repo_root or Path.cwd()).resolve()

    start_wall = time.monotonic()
    results: list[AuthorityRunResult] = []

    if concurrent_jobs > 1:
        # Run concurrently using thread pool for subprocess management
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=concurrent_jobs
        ) as executor:
            future_to_auth = {
                executor.submit(
                    run_single_preflight,
                    auth,
                    repo_root=root,
                    expected_heads=expected_heads,
                    tier_overrides=tier_overrides,
                    timeout=timeout,
                    log_dir=log_dir,
                    python_bin=python_bin,
                ): auth
                for auth in selected_authorities
            }
            for future in concurrent.futures.as_completed(future_to_auth):
                results.append(future.result())
        # Sort results back to selected_authorities order
        auth_order = {auth: idx for idx, auth in enumerate(selected_authorities)}
        results.sort(key=lambda r: auth_order.get(r.authority, 999))
    else:
        # Serial execution
        for auth in selected_authorities:
            res = run_single_preflight(
                auth,
                repo_root=root,
                expected_heads=expected_heads,
                tier_overrides=tier_overrides,
                timeout=timeout,
                log_dir=log_dir,
                python_bin=python_bin,
            )
            results.append(res)

    total_wall = round(time.monotonic() - start_wall, 2)

    # Classify overall status
    statuses = {r.status for r in results}
    if all(s == "PASS" for s in statuses):
        overall_status = "PASSED"
    elif any(s in ("FAIL", "TIMEOUT") for s in statuses):
        overall_status = "FAILED"
    else:
        overall_status = "PARTIAL"

    # Format concise summary table
    summary_lines = []
    for r in results:
        head_display = r.head_sha[:8] if len(r.head_sha) >= 8 else r.head_sha
        summary_lines.append(
            f"{r.authority:<12} {r.status:<6} {head_display} ({r.elapsed_seconds}s)"
        )
    summary_table = "\n".join(summary_lines)

    result_data: dict[str, Any] = {
        "schema_version": 1,
        "kind": "preflight-orchestration-result",
        "overall_status": overall_status,
        "total_wall_clock_seconds": total_wall,
        "concurrency": concurrent_jobs,
        "summary_table": summary_table,
        "authorities": [asdict(r) for r in results],
    }

    # Verify bounded summary size <= MAX_SUMMARY_BYTES
    dumped = json.dumps(result_data, indent=2)
    if len(dumped.encode("utf-8")) > MAX_SUMMARY_BYTES:
        for auth_dict in result_data["authorities"]:
            if (
                auth_dict.get("failure_excerpt")
                and len(auth_dict["failure_excerpt"]) > 300
            ):
                auth_dict["failure_excerpt"] = (
                    auth_dict["failure_excerpt"][:300] + "... (truncated)"
                )

    return result_data


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "authorities",
        nargs="*",
        default=ALL_AUTHORITIES,
        help=f"authorities to run (default: all {list(ALL_AUTHORITIES)})",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="path to repository workspace root (default: current directory)",
    )
    parser.add_argument(
        "--expected-heads-json",
        help="optional path to JSON mapping authority -> expected SHA",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"timeout in seconds per authority (default: {DEFAULT_TIMEOUT_SECONDS})",
    )
    parser.add_argument(
        "--jobs",
        "-j",
        type=int,
        default=1,
        help="number of concurrent jobs (default: 1 serial)",
    )
    parser.add_argument(
        "--log-dir",
        type=Path,
        default=None,
        help="optional directory to store full stdout/stderr per authority",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="output machine-readable JSON instead of text summary table",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    expected_heads: dict[str, str] | None = None
    if args.expected_heads_json:
        expected_heads = json.loads(
            Path(args.expected_heads_json).read_text(encoding="utf-8")
        )

    res = orchestrate_preflights(
        authorities=args.authorities,
        repo_root=args.repo_root,
        expected_heads=expected_heads,
        timeout=args.timeout,
        concurrent_jobs=args.jobs,
        log_dir=args.log_dir,
    )

    if args.json:
        sys.stdout.write(json.dumps(res, indent=2) + "\n")
    else:
        sys.stdout.write(res["summary_table"] + "\n")
        if res["overall_status"] != "PASSED":
            for a in res["authorities"]:
                if a["status"] != "PASS" and a.get("failure_excerpt"):
                    sys.stderr.write(
                        f"\n[{a['authority']} {a['status']}]:\n{a['failure_excerpt']}\n"
                    )

    return 0 if res["overall_status"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
