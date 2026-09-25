#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tarfile
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def resolve_checkout_revision(repo_root: Path) -> str:
    try:
        rev = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            text=True,
            stderr=subprocess.PIPE,
        ).strip()
    except Exception as exc:
        raise RuntimeError(f"Failed to resolve checkout revision in {repo_root}: {exc}") from exc
    if not rev or len(rev) != 40 or not all(c in "0123456789abcdef" for c in rev):
        raise ValueError(f"Invalid checkout revision '{rev}' in {repo_root}")
    return rev


def _verify_source_and_resources_bound(repo_root: Path) -> None:
    src_dir = (repo_root / "src").resolve()
    if not src_dir.is_dir():
        raise RuntimeError(f"Source checkout missing src directory at {src_dir}")

    if str(src_dir) not in sys.path or sys.path[0] != str(src_dir):
        sys.path.insert(0, str(src_dir))

    import agent_policy
    import agent_policy.config

    agent_policy_path = Path(agent_policy.__file__).resolve()
    if not agent_policy_path.is_relative_to(src_dir):
        raise RuntimeError(
            f"agent_policy imported from {agent_policy_path}, expected under {src_dir}"
        )

    pkg_root = agent_policy.config.package_root().resolve()
    if pkg_root != repo_root.resolve():
        raise RuntimeError(
            f"agent_policy package_root() resolved to {pkg_root}, expected {repo_root.resolve()}"
        )


@contextmanager
def materialize_snapshot(repo_root: Path, revision: str) -> Iterator[Path]:
    if not revision or len(revision) != 40 or not all(c in "0123456789abcdef" for c in revision):
        raise ValueError(f"Invalid candidate revision '{revision}'")

    with tempfile.TemporaryDirectory(prefix="policy-candidate-snapshot-") as temporary:
        archive_path = Path(temporary) / "candidate.tar"
        snapshot_root = Path(temporary) / "tree"
        snapshot_root.mkdir()

        try:
            subprocess.run(
                ["git", "archive", "--format=tar", f"--output={archive_path}", revision],
                cwd=repo_root,
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(
                f"Failed to create Git archive for revision {revision} in {repo_root}: {exc.stderr}"
            ) from exc

        with tarfile.open(archive_path, "r") as archive:
            comment = (
                archive.pax_headers.get("comment")
                if hasattr(archive, "pax_headers")
                else None
            )
            if comment and comment != revision:
                raise RuntimeError(
                    f"Git archive comment {comment} does not match expected revision {revision}"
                )
            archive.extractall(snapshot_root, filter="data")

        (snapshot_root / ".candidate_revision").write_text(revision, encoding="utf-8")
        yield snapshot_root


def _evaluate_candidate(candidate_root: Path, candidate_revision: str) -> None:
    _verify_source_and_resources_bound(candidate_root)
    from agent_policy.commands import check, render

    with tempfile.TemporaryDirectory(prefix="policy-candidate-qualification-") as temporary:
        fixture_root = Path(temporary) / "repo"
        fixture_root.mkdir()
        (fixture_root / ".git").mkdir()

        config_content = (
            "schema_version: 2\n"
            "toolchain:\n"
            "  repository: TakashiSasaki/templates\n"
            f"  revision: {candidate_revision}\n"
            "contexts:\n"
            "  coding:\n"
            "    profiles:\n"
            "      - core\n"
            "      - security-baseline\n"
            "      - pull-request\n"
            "      - progressive-discovery\n"
            "    project_policy:\n"
            "      files: []\n"
            "outputs:\n"
            "  agents:\n"
            "    enabled: true\n"
            "    path: AGENTS.md\n"
            "    context: coding\n"
            "    renderer: agents-md\n"
            "skills:\n"
            "  enabled:\n"
            "    - pr-review\n"
            "    - orchestrate-repository-change\n"
            "    - maintain-progressive-discovery\n"
        )
        (fixture_root / ".agent-policy.yml").write_text(config_content, encoding="utf-8")

        render_diagnostics = render.run(fixture_root, ".agent-policy.yml")
        if render_diagnostics:
            raise RuntimeError(f"Candidate render failed: {render_diagnostics}")

        check_diagnostics = check.run(fixture_root, ".agent-policy.yml")
        if check_diagnostics:
            raise RuntimeError(f"Candidate check failed: {check_diagnostics}")

        agents_content = (fixture_root / "AGENTS.md").read_text(encoding="utf-8")
        expected_provenance = f"TakashiSasaki/templates@{candidate_revision}"
        if expected_provenance not in agents_content:
            raise RuntimeError(
                f"Candidate output missing candidate revision provenance: "
                f"expected {expected_provenance}"
            )
        if not (fixture_root / ".agent-policy.lock").is_file():
            raise RuntimeError("Candidate qualification missing lockfile")


_PROBE_SCRIPT = r"""
from __future__ import annotations
import sys
from pathlib import Path

snapshot_root = Path(sys.argv[1]).resolve()
candidate_revision = sys.argv[2]

marker_file = snapshot_root / ".candidate_revision"
if not marker_file.is_file():
    raise RuntimeError(f"Snapshot missing .candidate_revision marker at {snapshot_root}")
recorded_revision = marker_file.read_text(encoding="utf-8").strip()
if recorded_revision != candidate_revision:
    raise RuntimeError(
        f"Snapshot revision mismatch: recorded '{recorded_revision}' "
        f"!= candidate '{candidate_revision}'"
    )

src_dir = snapshot_root / "src"
if not src_dir.is_dir():
    raise RuntimeError(f"Snapshot missing src directory at {src_dir}")

sys.path.insert(0, str(src_dir))

import agent_policy
import agent_policy.config
from agent_policy.commands import check, render
import tempfile

agent_policy_path = Path(agent_policy.__file__).resolve()
if not agent_policy_path.is_relative_to(src_dir):
    raise RuntimeError(
        f"agent_policy imported from {agent_policy_path}, expected under {src_dir}"
    )

pkg_root = agent_policy.config.package_root().resolve()
if pkg_root != snapshot_root.resolve():
    raise RuntimeError(
        f"agent_policy package_root() resolved to {pkg_root}, expected {snapshot_root.resolve()}"
    )

with tempfile.TemporaryDirectory(prefix="policy-candidate-eval-") as temporary:
    fixture_root = Path(temporary) / "repo"
    fixture_root.mkdir()
    (fixture_root / ".git").mkdir()

    config_content = (
        "schema_version: 2\n"
        "toolchain:\n"
        "  repository: TakashiSasaki/templates\n"
        f"  revision: {candidate_revision}\n"
        "contexts:\n"
        "  coding:\n"
        "    profiles:\n"
        "      - core\n"
        "      - security-baseline\n"
        "      - pull-request\n"
        "      - progressive-discovery\n"
        "    project_policy:\n"
        "      files: []\n"
        "outputs:\n"
        "  agents:\n"
        "    enabled: true\n"
        "    path: AGENTS.md\n"
        "    context: coding\n"
        "    renderer: agents-md\n"
        "skills:\n"
        "  enabled:\n"
        "    - pr-review\n"
        "    - orchestrate-repository-change\n"
        "    - maintain-progressive-discovery\n"
    )
    (fixture_root / ".agent-policy.yml").write_text(config_content, encoding="utf-8")

    render_diagnostics = render.run(fixture_root, ".agent-policy.yml")
    if render_diagnostics:
        raise RuntimeError(f"Candidate render failed: {render_diagnostics}")

    check_diagnostics = check.run(fixture_root, ".agent-policy.yml")
    if check_diagnostics:
        raise RuntimeError(f"Candidate check failed: {check_diagnostics}")

    agents_content = (fixture_root / "AGENTS.md").read_text(encoding="utf-8")
    expected_provenance = f"TakashiSasaki/templates@{candidate_revision}"
    if expected_provenance not in agents_content:
        raise RuntimeError(
            f"Candidate output missing candidate revision provenance: "
            f"expected {expected_provenance}"
        )
    if not (fixture_root / ".agent-policy.lock").is_file():
        raise RuntimeError("Candidate qualification missing lockfile")
"""


def _run_snapshot_qualification(snapshot_root: Path, candidate_revision: str) -> None:
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("PIP_") and not key.startswith("PYTHON")
    }
    env["PIP_CONFIG_FILE"] = os.devnull
    env["PYTHONNOUSERSITE"] = "1"

    proc = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            _PROBE_SCRIPT,
            str(snapshot_root),
            candidate_revision,
        ],
        cwd=snapshot_root,
        env=env,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        error_msg = proc.stderr.strip() or proc.stdout.strip()
        raise RuntimeError(
            f"Candidate qualification failed in snapshot {snapshot_root}: {error_msg}"
        )


def qualify_candidate() -> str:
    candidate_revision = resolve_checkout_revision(ROOT)
    with materialize_snapshot(ROOT, candidate_revision) as snapshot_root:
        _run_snapshot_qualification(snapshot_root, candidate_revision)
    return candidate_revision


def worktree_status(repo_root: Path) -> str:
    try:
        status = subprocess.check_output(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"],
            cwd=repo_root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        return "dirty" if status else "clean"
    except Exception:
        return "unknown"


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Qualify candidate Policy package internally.")
    parser.parse_args(arguments)
    try:
        candidate_revision = qualify_candidate()
        status = worktree_status(ROOT)
        print(
            f"POLICY_CANDIDATE_QUALIFICATION_PASS revision={candidate_revision} "
            f"evaluated=snapshot worktree={status}"
        )
        return 0
    except Exception as exc:
        print(f"POLICY_CANDIDATE_QUALIFICATION_FAIL error={exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

