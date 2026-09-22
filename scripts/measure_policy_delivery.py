#!/usr/bin/env python3
"""Measure policy presentation without reading or printing instruction bodies.

The report deliberately describes source identities, sizes, and observable host
metadata. It does not claim that a measured file was included in a model
request, and it never emits policy text or session transcripts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import sqlite3
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
GENERATED_PATHS = (
    "AGENTS.md",
    ".review-authority/review-policy.md",
    ".agent-policy.lock",
)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def file_measurement(path: Path, *, role: str) -> dict[str, Any]:
    if not path.is_file():
        return {"path": path.as_posix(), "role": role, "state": "missing"}
    value = path.read_bytes()
    text = value.decode("utf-8", errors="replace")
    return {
        "path": path.as_posix(),
        "role": role,
        "state": "observed",
        "bytes": len(value),
        "lines": len(text.splitlines()),
        "sha256": sha256_bytes(value),
    }


def _git(root: Path, *arguments: str) -> str:
    return subprocess.check_output(
        ["git", *arguments], cwd=root, text=True, stderr=subprocess.STDOUT
    ).strip()


def _version(command: str) -> str | None:
    executable = shutil.which(command)
    if executable is None:
        return None
    try:
        return subprocess.check_output(
            [executable, "--version"], text=True, stderr=subprocess.STDOUT, timeout=5
        ).splitlines()[0]
    except (OSError, subprocess.SubprocessError):
        return None


def _source_path(root: Path, source: str, origin: str, package_root: Path) -> Path:
    if origin == "toolchain":
        return package_root / source
    return root / source


def _rendered_body(rule_body: str) -> str:
    return rule_body.split("\n", 1)[1].strip() if "\n" in rule_body else rule_body


def _configured_output_paths(spec: Any) -> list[tuple[str, str]]:
    """Return the enabled output files, including optional staged details."""
    paths = [(spec.path, f"output:{spec.name}")]
    detail_bundle_path = getattr(spec, "detail_bundle_path", None)
    if detail_bundle_path is not None and detail_bundle_path != spec.path:
        paths.append((detail_bundle_path, f"output:{spec.name}:detail-bundle"))
    return paths


def _executing_source_identity(module_file: Path, package: Path) -> dict[str, Any]:
    files: dict[str, str] = {}
    for path in (
        module_file,
        module_file.parent / "config.py",
        module_file.parent / "policy_loader.py",
        module_file.parent / "renderer.py",
    ):
        if path.is_file():
            files[path.name] = sha256_bytes(path.read_bytes())
    return {
        "evidence": "Observed",
        "module": module_file.as_posix(),
        "package_root": package.as_posix(),
        "source_files_sha256": files,
    }


def _load_context_report(root: Path, config_path: str, context_name: str) -> dict[str, Any]:
    source_path = (root / "src").resolve()
    if source_path.is_dir() and str(source_path) not in sys.path:
        sys.path.insert(0, str(source_path))

    import agent_policy
    from agent_policy.config import load_config, package_root, validate_config
    from agent_policy.policy_loader import load_rules

    module_file = Path(agent_policy.__file__).resolve()
    if source_path.is_dir() and source_path not in module_file.parents:
        raise ValueError(
            "executing agent_policy module is not loaded from the measured repository"
        )

    config = load_config(root, config_path)
    diagnostics = validate_config(root, config)
    if diagnostics:
        messages = "; ".join(item.message for item in diagnostics)
        raise ValueError(f"configuration is invalid: {messages}")
    context = config.contexts.get(context_name)
    if context is None:
        raise ValueError(f"unknown policy context: {context_name}")
    rules = load_rules(
        root,
        list(context.profiles),
        list(context.project_policy_files),
        declared_overrides=context.override_reasons,
        require_explicit_overrides=True,
    )
    package = package_root()
    entries: list[dict[str, Any]] = []
    source_body_bytes = 0
    rendered_rule_bytes = 0
    for rule in rules:
        source_path = _source_path(root, rule.source, rule.origin, package)
        source_bytes = source_path.read_bytes()
        body_bytes = len(rule.body.encode("utf-8"))
        emitted_body = _rendered_body(rule.body)
        source_body_bytes += body_bytes
        rendered_rule_bytes += len(emitted_body.encode("utf-8"))
        entries.append(
            {
                "id": rule.id,
                "title": rule.title,
                "severity": rule.severity,
                "origin": rule.origin,
                "source": rule.source,
                "source_sha256": sha256_bytes(source_bytes),
                "source_body_bytes": body_bytes,
                "source_body_lines": len(rule.body.splitlines()),
            }
        )

    output_measurements = []
    for spec in config.output_specs:
        if not spec.enabled:
            continue
        output_measurements.extend(
            file_measurement(root / relative, role=role)
            for relative, role in _configured_output_paths(spec)
        )

    return {
        "context": context_name,
        "rule_count": len(rules),
        "source_body_bytes": source_body_bytes,
        "rendered_rule_bytes": rendered_rule_bytes,
        "rules": entries,
        "outputs": output_measurements,
        "config_path": config.relative_path,
        "toolchain": dict(config.data["toolchain"]),
        "executing_source": _executing_source_identity(module_file, package),
    }


def _skills_inventory(root: Path) -> list[dict[str, Any]]:
    directory = root / ".agents" / "skills"
    if not directory.is_dir():
        return []
    return [
        file_measurement(path, role="generated-skill")
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    ]


def _log_aggregate(path: Path) -> dict[str, Any]:
    """Return authorized aggregate metadata without selecting transcript contents."""
    uri = f"file:{path.resolve()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        connection.execute("PRAGMA query_only = ON")
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(logs)").fetchall()
        }
        required = {"target", "estimated_bytes"}
        if not required <= columns:
            missing = ", ".join(sorted(required - columns))
            raise ValueError(f"log database is missing aggregate columns: {missing}")
        rows = connection.execute(
            """
            SELECT target, COUNT(*), COALESCE(SUM(estimated_bytes), 0)
            FROM logs
            GROUP BY target
            ORDER BY target
            """
        ).fetchall()
    targets = [
        {"target": target, "events": count, "estimated_bytes": bytes_}
        for target, count, bytes_ in rows
    ]
    aggregate_bytes = json.dumps(
        {"targets": targets}, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    metadata = path.stat()
    return {
        "evidence": "Observed",
        "path": path.as_posix(),
        "database_metadata": {
            "size_bytes": metadata.st_size,
            "mtime_ns": metadata.st_mtime_ns,
        },
        "aggregate_sha256": sha256_bytes(aggregate_bytes),
        "targets": targets,
        "read_scope": "PRAGMA table_info(logs) and target/count/estimated_bytes aggregates only",
        "warning": (
            "Only authorized aggregate columns were selected; transcript bodies were "
            "not selected, exported, or hashed. File metadata may include the physical "
            "database size and modification time."
        ),
    }


def build_report(
    root: Path,
    *,
    config_path: str = ".agent-policy.yml",
    log_db: Path | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    current_head = _git(root, "rev-parse", "HEAD")
    tree = _git(root, "rev-parse", "HEAD^{tree}")
    generated = [
        file_measurement(root / relative, role="generated-projection")
        for relative in GENERATED_PATHS
    ]
    report: dict[str, Any] = {
        "schema_version": 1,
        "evidence_labels": {
            "observed": "Observed",
            "reconstructed": "Reconstructed",
            "estimated": "Estimated",
            "unobserved": "Unobserved",
        },
        "repository": {
            "root": str(root),
            "head": current_head,
            "tree": tree,
            "branch": _git(root, "branch", "--show-current"),
            "dirty": bool(_git(root, "status", "--porcelain")),
        },
        "host": {
            "evidence": "Observed",
            "os": platform.platform(),
            "python": platform.python_version(),
            "architecture": platform.machine(),
            "codex_version": _version("codex"),
            "gh_version": _version("gh"),
            "prompt_assembly": "Unobserved",
            "model_tokenizer": "Unobserved",
            "project_doc_limit": "Unobserved unless supplied by host instrumentation",
            "fallback_filenames": "Unobserved unless supplied by host instrumentation",
        },
        "measurement": {
            "byte_encoding": "UTF-8",
            "line_count": "str.splitlines()",
            "token_counts": "Unobserved; no model tokenizer is assumed",
            "rule_body_attribution": (
                "Mechanical source-body and rendered-body byte totals; boundaries may differ."
            ),
        },
        "coding": _load_context_report(root, config_path, "coding"),
        "generated": generated,
        "skills": _skills_inventory(root),
        "experiment": {
            "condition_a": "current actual configuration",
            "condition_b": "complete current full-text delivery",
            "condition_c": "opt-in staged delivery",
            "fresh_trials_max": 6,
            "concurrent_workers_max": 2,
            "model_behavior": "Unobserved until separately run in fresh isolated sessions",
        },
    }
    if log_db is not None:
        report["authorized_log_aggregate"] = _log_aggregate(log_db)
    return report


def render_markdown(report: dict[str, Any]) -> str:
    coding = report["coding"]
    lines = [
        "# Policy delivery measurement",
        "",
        f"- Repository head: `{report['repository']['head']}`",
        f"- Tree: `{report['repository']['tree']}`",
        f"- Dirty: `{report['repository']['dirty']}`",
        f"- Coding rules: {coding['rule_count']}",
        f"- Source rule-body bytes: {coding['source_body_bytes']}",
        f"- Rendered rule-body bytes: {coding['rendered_rule_bytes']}",
        "- Model prompt inclusion: **Unobserved**",
        "- Actual model token counts: **Unobserved**",
        "",
        "## Generated projections",
        "",
        "| Path | Role | State | Bytes | Lines | SHA-256 |",
        "| --- | --- | --- | ---: | ---: | --- |",
    ]
    for item in report["generated"]:
        lines.append(
            "| {path} | {role} | {state} | {bytes} | {lines} | `{sha256}` |".format(
                path=item["path"],
                role=item["role"],
                state=item["state"],
                bytes=item.get("bytes", "—"),
                lines=item.get("lines", "—"),
                sha256=item.get("sha256", "—"),
            )
        )
    lines.extend(
        [
            "",
            "## Evidence boundary",
            "",
            "This report measures repository files and authorized metadata. It does not "
            "prove that a host included a complete file in a model request. Token counts "
            "remain unavailable unless the host exposes a supported tokenizer or usage event.",
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=ROOT)
    parser.add_argument("--config", default=".agent-policy.yml")
    parser.add_argument("--log-db", type=Path, default=None)
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    args = parser.parse_args(list(argv) if argv is not None else None)

    report = build_report(
        args.repository,
        config_path=args.config,
        log_db=args.log_db,
    )
    if args.format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render_markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
