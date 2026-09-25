#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SUPPORTED_FILE_MODES = {"100644", "100755"}
SYMLINK_MODE = "120000"
GITLINK_MODE = "160000"


def _git_env() -> dict[str, str]:
    """Environment explicitly disabling Git replacement object semantics."""
    env = os.environ.copy()
    env["GIT_NO_REPLACE_OBJECTS"] = "1"
    return env


def _is_valid_oid(oid: str) -> bool:
    """Verify that oid is a valid hexadecimal object ID (SHA-1 40-char or SHA-256 64-char)."""
    return len(oid) in (40, 64) and all(c in "0123456789abcdef" for c in oid)


def _validate_commit_structural(repo_root: Path, revision: str) -> tuple[str, str]:
    """Establish that revision names an exact expected commit object under no-replacement semantics.

    Returns (commit_oid, tree_oid).
    Fails closed if the object does not exist, is not a commit, or tree cannot be resolved.
    """
    if not revision or not isinstance(revision, str):
        raise ValueError(f"Invalid candidate revision '{revision}'")

    env = _git_env()

    # 1. Resolve exact commit OID with replacement refs disabled
    try:
        commit_oid = subprocess.check_output(
            ["git", "--no-replace-objects", "rev-parse", "--verify", f"{revision}^{{commit}}"],
            cwd=repo_root,
            text=True,
            stderr=subprocess.PIPE,
            env=env,
        ).strip()
    except Exception as exc:
        raise RuntimeError(
            f"Revision '{revision}' does not resolve to a commit in {repo_root}: {exc}"
        ) from exc

    if not _is_valid_oid(commit_oid):
        raise ValueError(f"Malformed commit object ID '{commit_oid}' for revision '{revision}'")

    # 2. Verify object type is strictly 'commit'
    try:
        obj_type = subprocess.check_output(
            ["git", "--no-replace-objects", "cat-file", "-t", commit_oid],
            cwd=repo_root,
            text=True,
            stderr=subprocess.PIPE,
            env=env,
        ).strip()
    except Exception as exc:
        raise RuntimeError(
            f"Failed to inspect object type for '{commit_oid}' in {repo_root}: {exc}"
        ) from exc

    if obj_type != "commit":
        raise RuntimeError(f"Object '{commit_oid}' is of type '{obj_type}', expected 'commit'")

    # 3. Resolve exact root tree OID with replacement refs disabled
    try:
        tree_oid = subprocess.check_output(
            ["git", "--no-replace-objects", "rev-parse", "--verify", f"{commit_oid}^{{tree}}"],
            cwd=repo_root,
            text=True,
            stderr=subprocess.PIPE,
            env=env,
        ).strip()
    except Exception as exc:
        raise RuntimeError(
            f"Failed to resolve tree for commit '{commit_oid}' in {repo_root}: {exc}"
        ) from exc

    if not _is_valid_oid(tree_oid):
        raise ValueError(f"Malformed tree object ID '{tree_oid}' for commit '{commit_oid}'")

    # 4. Verify tree object type is strictly 'tree'
    try:
        tree_type = subprocess.check_output(
            ["git", "--no-replace-objects", "cat-file", "-t", tree_oid],
            cwd=repo_root,
            text=True,
            stderr=subprocess.PIPE,
            env=env,
        ).strip()
    except Exception as exc:
        raise RuntimeError(
            f"Failed to inspect tree type for '{tree_oid}' in {repo_root}: {exc}"
        ) from exc

    if tree_type != "tree":
        raise RuntimeError(f"Object '{tree_oid}' is of type '{tree_type}', expected 'tree'")

    return commit_oid, tree_oid


def resolve_checkout_revision(repo_root: Path) -> str:
    """Resolve and structurally validate the checkout commit under no-replacement semantics."""
    try:
        commit_oid, _ = _validate_commit_structural(repo_root, "HEAD")
    except Exception as exc:
        raise RuntimeError(f"Failed to resolve checkout revision in {repo_root}: {exc}") from exc
    return commit_oid


class _TreeEntry:
    def __init__(self, mode: str, type_: str, oid: str, path: str, dest: Path) -> None:
        self.mode = mode
        self.type_ = type_
        self.oid = oid
        self.path = path
        self.dest = dest


def _read_tree_entries(repo_root: Path, tree_oid: str, snapshot_root: Path) -> list[_TreeEntry]:
    env = _git_env()
    try:
        output = subprocess.check_output(
            ["git", "--no-replace-objects", "ls-tree", "-r", "-z", "--full-tree", tree_oid],
            cwd=repo_root,
            env=env,
            stderr=subprocess.PIPE,
        )
    except Exception as exc:
        raise RuntimeError(
            f"Failed to list tree entries for {tree_oid} in {repo_root}: {exc}"
        ) from exc

    entries: list[_TreeEntry] = []
    records = output.split(b"\0")
    for record in records:
        if not record:
            continue
        try:
            meta, path_bytes = record.split(b"\t", 1)
            mode, type_, oid = meta.decode("ascii").split()
            rel_path = path_bytes.decode("utf-8", errors="surrogateescape")
        except Exception as exc:
            raise RuntimeError(f"Malformed ls-tree entry: {record!r}") from exc

        # Strict path safety validation
        if "\n" in rel_path or "\r" in rel_path:
            raise RuntimeError(f"Unsafe newline in candidate path: {rel_path!r}")
        path_obj = Path(rel_path)
        if path_obj.is_absolute() or any(part in ("", ".", "..") for part in path_obj.parts):
            raise RuntimeError(f"Unsafe path in candidate tree: {rel_path!r}")
        dest = (snapshot_root / rel_path).resolve()
        if not dest.is_relative_to(snapshot_root.resolve()):
            raise RuntimeError(f"Path traversal detected: {rel_path!r}")

        # Strict file mode validation
        if mode == SYMLINK_MODE:
            raise RuntimeError(
                f"Candidate contains unsupported symlink at '{rel_path}' (mode {mode}); "
                "Policy candidate qualification rejects symlinks fail-closed"
            )
        if mode == GITLINK_MODE:
            raise RuntimeError(
                f"Candidate contains unsupported gitlink/submodule at '{rel_path}' (mode {mode}); "
                "Policy candidate qualification does not support submodule-backed closures"
            )
        if mode not in SUPPORTED_FILE_MODES or type_ != "blob":
            supported = ", ".join(sorted(SUPPORTED_FILE_MODES))
            raise RuntimeError(
                f"Candidate contains unsupported object at '{rel_path}' "
                f"(mode {mode}, type {type_}); only regular files ({supported}) are supported"
            )
        if not _is_valid_oid(oid):
            raise ValueError(f"Malformed blob object ID '{oid}' for '{rel_path}'")

        entries.append(_TreeEntry(mode=mode, type_=type_, oid=oid, path=rel_path, dest=dest))

    return entries


def _materialize_blobs(repo_root: Path, entries: list[_TreeEntry]) -> None:
    if not entries:
        return

    env = _git_env()
    unique_oids = list(dict.fromkeys(entry.oid for entry in entries))

    proc = subprocess.Popen(
        ["git", "--no-replace-objects", "cat-file", "--batch"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=repo_root,
        env=env,
    )
    blob_map: dict[str, bytes] = {}
    try:
        assert proc.stdin is not None
        assert proc.stdout is not None
        for oid in unique_oids:
            proc.stdin.write(f"{oid}\n".encode("ascii"))
            proc.stdin.flush()
            header_line = proc.stdout.readline().decode("ascii", errors="replace")
            header_parts = header_line.strip().split()
            if len(header_parts) != 3 or header_parts[0] != oid or header_parts[1] != "blob":
                raise RuntimeError(
                    f"Unexpected cat-file header for blob {oid}: {header_line.strip()}"
                )
            size = int(header_parts[2])
            data = proc.stdout.read(size)
            if len(data) != size:
                raise RuntimeError(
                    f"Truncated blob read for {oid}: expected {size} bytes, got {len(data)}"
                )
            trailing = proc.stdout.read(1)
            if trailing != b"\n":
                raise RuntimeError(f"Expected newline after blob {oid}, got {trailing!r}")
            blob_map[oid] = data
        proc.stdin.close()
        ret = proc.wait()
        if ret != 0:
            stderr = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
            raise RuntimeError(f"git cat-file --batch failed (code {ret}): {stderr}")
    except Exception:
        proc.kill()
        proc.wait()
        raise

    for entry in entries:
        entry.dest.parent.mkdir(parents=True, exist_ok=True)
        entry.dest.write_bytes(blob_map[entry.oid])
        if entry.mode == "100755":
            entry.dest.chmod(0o755)
        else:
            entry.dest.chmod(0o644)


def _verify_materialized_files(repo_root: Path, entries: list[_TreeEntry]) -> None:
    """Verify that every materialized regular file matches its expected tree-entry blob OID.

    Uses Git-native object hashing with --no-filters and replacement objects disabled.
    """
    if not entries:
        return

    env = _git_env()
    stdin_paths = "\n".join(str(entry.dest) for entry in entries) + "\n"

    try:
        result = subprocess.run(
            ["git", "--no-replace-objects", "hash-object", "--no-filters", "--stdin-paths"],
            input=stdin_paths,
            text=True,
            capture_output=True,
            cwd=repo_root,
            env=env,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"Failed to recompute blob hashes for materialized snapshot: {exc.stderr}"
        ) from exc

    computed_hashes = result.stdout.splitlines()
    if len(computed_hashes) != len(entries):
        raise RuntimeError(
            f"Hash verification count mismatch: computed {len(computed_hashes)} hashes "
            f"for {len(entries)} entries"
        )

    for entry, computed_oid in zip(entries, computed_hashes, strict=True):
        clean_computed = computed_oid.strip()
        if clean_computed != entry.oid:
            raise RuntimeError(
                f"Materialized file '{entry.path}' blob OID mismatch: "
                f"computed {clean_computed} != expected {entry.oid}"
            )
        st_mode = entry.dest.stat().st_mode
        if entry.mode == "100755" and not (st_mode & 0o111):
            raise RuntimeError(
                f"Materialized executable file '{entry.path}' missing execute permissions: "
                f"mode={oct(st_mode)}"
            )


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
def materialize_snapshot(
    repo_root: Path,
    revision: str,
    _post_write_hook: Callable[[Path], None] | None = None,
) -> Iterator[Path]:
    if not revision or not _is_valid_oid(revision):
        raise ValueError(f"Invalid candidate revision '{revision}'")

    commit_oid, tree_oid = _validate_commit_structural(repo_root, revision)
    if revision != commit_oid:
        raise ValueError(
            f"Candidate revision '{revision}' does not match commit object ID '{commit_oid}'"
        )

    with tempfile.TemporaryDirectory(prefix="policy-candidate-snapshot-") as temporary:
        snapshot_root = Path(temporary) / "tree"
        snapshot_root.mkdir()

        # 1. Parse all tree entries directly from the Git tree object
        entries = _read_tree_entries(repo_root, tree_oid, snapshot_root)

        # 2. Materialize raw blob bytes
        _materialize_blobs(repo_root, entries)

        # Optional test hook for tampering verification
        if _post_write_hook is not None:
            _post_write_hook(snapshot_root)

        # 3. Re-verify all materialized files against expected blob OIDs
        _verify_materialized_files(repo_root, entries)

        # 4. Record internal subprocess handoff metadata (not provenance authority)
        (snapshot_root / ".candidate_revision").write_text(commit_oid, encoding="utf-8")
        (snapshot_root / ".candidate_tree").write_text(tree_oid, encoding="utf-8")

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
