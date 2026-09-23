#!/usr/bin/env python3
"""Maintainer review stack entrypoint with fixed-source verification and safe execution.

Orchestrates read-only observation, common input assembly, bound review planning,
artifact rendering, side-effect-free preview, and authorized publication.
Default operation is strictly read-only preview.
"""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent


def _load_sibling(name: str, filename: str) -> Any:
    path = SCRIPT_DIR / filename
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load sibling module {filename} from {SCRIPT_DIR}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        if sys.modules.get(name) is module:
            sys.modules.pop(name, None)
        raise
    return module


renderer = _load_sibling("templates_render_review_artifacts", "render_review_artifacts.py")
publisher = _load_sibling("templates_publish_review_artifacts", "publish_review_artifacts.py")
observer = _load_sibling("templates_observe_pr_state", "observe_pr_state.py")
live_adapter = _load_sibling("templates_live_review_adapter", "live_review_adapter.py")

DEFAULT_REPOSITORY = "TakashiSasaki/templates"
FULL_SHA = re.compile(r"[0-9a-f]{40}")
MAX_SUMMARY_BYTES = 8192


class MaintainerWorkflowError(RuntimeError):
    """Raised when the maintainer workflow encounters an invariant violation."""


def _json_load(path: Path | str) -> dict[str, Any]:
    if str(path) == "-":
        return json.loads(sys.stdin.read())
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _resolve_toolchain_revision_and_blob(
    repository_root: Path, candidate_head: str
) -> tuple[str, str]:
    try:
        blob_sha = subprocess.check_output(
            ["git", "rev-parse", "--verify", f"{candidate_head}:.agent-policy.yml"],
            cwd=repository_root,
            stderr=subprocess.PIPE,
            text=True,
        ).strip()
        raw_bytes = subprocess.check_output(
            ["git", "show", f"{candidate_head}:.agent-policy.yml"],
            cwd=repository_root,
            stderr=subprocess.PIPE,
        )
        doc = publisher._load_consumer_yaml(raw_bytes.decode("utf-8"))
        rev = str(doc["toolchain"]["revision"])
        return rev, blob_sha
    except Exception as exc:
        raise MaintainerWorkflowError(
            f"cannot resolve toolchain.revision at candidate head {candidate_head}: {exc}"
        ) from exc


def _resolve_trusted_manifest_planner(
    repository_root: Path, trusted_base_sha: str
) -> tuple[str, str]:
    try:
        manifest_raw = subprocess.check_output(
            ["git", "show", f"{trusted_base_sha}:{renderer.TRUSTED_SOURCE_MANIFEST_PATH}"],
            cwd=repository_root,
            stderr=subprocess.PIPE,
            text=True,
        )
        manifest_data = json.loads(manifest_raw)
        planner_revision = str(manifest_data["revision"])
        planner_entry = next(
            (
                item
                for item in manifest_data.get("closure", [])
                if item.get("path") == renderer.PLANNER_PATH
            ),
            None,
        )
        if not planner_entry:
            raise MaintainerWorkflowError(
                f"manifest at {trusted_base_sha} does not contain {renderer.PLANNER_PATH}"
            )
        planner_blob = str(planner_entry["blob_sha"])
        return planner_revision, planner_blob
    except Exception as exc:
        raise MaintainerWorkflowError(
            f"cannot resolve trusted planner manifest at {trusted_base_sha}: {exc}"
        ) from exc


def assemble_review_artifacts_input(
    *,
    repository: str,
    target_pr: int,
    candidate_head: str,
    candidate_base: str,
    trusted_base_sha: str,
    repository_root: Path,
    effective_base_sha: str | None = None,
    stack_members: list[dict[str, Any]] | None = None,
    observed_snapshot: dict[str, Any] | None = None,
    pr_body_text: str = "Human PR description\n",
    gate_status: str = "not_evaluated",
    review_readiness: dict[str, Any] | None = None,
    closure_audit: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Assemble the canonical repository-change-review-artifacts version 1 input structure."""
    if not FULL_SHA.fullmatch(candidate_head):
        raise MaintainerWorkflowError(f"invalid candidate head SHA: {candidate_head}")
    if not FULL_SHA.fullmatch(candidate_base):
        raise MaintainerWorkflowError(f"invalid candidate base SHA: {candidate_base}")
    if not FULL_SHA.fullmatch(trusted_base_sha):
        raise MaintainerWorkflowError(f"invalid trusted base SHA: {trusted_base_sha}")

    effective_base = effective_base_sha or candidate_base
    if not FULL_SHA.fullmatch(effective_base):
        raise MaintainerWorkflowError(f"invalid effective base SHA: {effective_base}")

    toolchain_rev, toolchain_blob = _resolve_toolchain_revision_and_blob(
        repository_root, candidate_head
    )
    planner_revision, planner_blob = _resolve_trusted_manifest_planner(
        repository_root, trusted_base_sha
    )

    planner_source = {
        "repository": repository,
        "revision": planner_revision,
        "path": renderer.PLANNER_PATH,
        "blob_sha": planner_blob,
        "trusted": True,
    }

    members = stack_members or [
        {
            "id": f"pr-{target_pr}",
            "authority": "policy",
            "head_sha": candidate_head,
            "base_sha": candidate_base,
            "pull_request": {
                "id": f"PR_kwDO_{target_pr}",
                "number": target_pr,
                "provider_identity": {
                    "provider": "github",
                    "repository_id": 1,
                    "resource_id": target_pr,
                },
                "provider_path": f"/repos/{repository}/pulls/{target_pr}",
            },
        }
    ]

    candidate = {
        "repository": repository,
        "authority": "policy",
        "branch": "policy",
        "pull_request": {
            "id": f"PR_kwDO_{target_pr}",
            "number": target_pr,
            "provider_identity": {
                "provider": "github",
                "repository_id": 1,
                "resource_id": target_pr,
            },
            "provider_path": f"/repos/{repository}/pulls/{target_pr}",
        },
        "head_sha": candidate_head,
        "base_sha": candidate_base,
        "effective_base_sha": effective_base,
        "members": members,
    }

    revision_bindings = [
        {
            "role": "consumer_actual_toolchain",
            "status": "bound",
            "revision": toolchain_rev,
            "source": {
                "locator": f"{repository}@{candidate_head}:.agent-policy.yml#toolchain.revision",
                "candidate_head_sha": candidate_head,
                "path": ".agent-policy.yml",
                "field": "toolchain.revision",
                "blob_sha": toolchain_blob,
            },
        },
        {
            "role": "prospective_canonical_candidate",
            "status": "bound",
            "revision": candidate_head,
            "source": {
                "locator": f"{repository}@{candidate_head}",
                "kind": "candidate_head",
            },
        },
        {
            "role": "trusted_maintainer_source",
            "status": "bound",
            "revision": planner_revision,
            "source": {
                "locator": f"{repository}@{planner_revision}:{renderer.PLANNER_PATH}",
                "repository": repository,
                "revision": planner_revision,
                "path": renderer.PLANNER_PATH,
                "blob_sha": planner_blob,
                "trusted": True,
            },
        },
        {
            "role": "publication_provider",
            "status": "not_applicable",
            "reason": "provider_unbound_during_preview",
        },
        {
            "role": "site_integration_lock",
            "status": "not_applicable",
            "reason": "policy_authority_does_not_own_site_lock",
        },
    ]

    norm_candidate = renderer._normalize_candidate(
        {"repository": repository, "candidate": candidate}
    )
    _, revision_digest = renderer._normalize_revision_bindings(
        {"revision_bindings": revision_bindings},
        norm_candidate,
        repository_root=repository_root,
    )

    work = {
        "objective_ref": "maintainer_pr_landing",
        "next_safe_action": "preview_maintainer_stack",
        "stopping_boundary": "stop after the whole-stack Codex review request",
        "blockers": [],
        "unresolved_finding_refs": [],
        "evidence_gap": "none",
        "closure_audit": closure_audit or [],
        "review_readiness": review_readiness
        or {
            "state": "ready",
            "known_material_findings_complete": True,
            "finding_families": [],
            "planned_candidate_mutations": [],
            "remaining_material_gaps": [],
            "reasons": [],
            "exception": None,
            "review_acquisition_allowed": True,
        },
    }
    norm_work = renderer._normalize_work({"work": work})

    input_binding = {"evidence_set": "evidence-1"}
    contract = {"revision": "contract-1", "scope": "maintainer-stack"}
    change = {
        "impact": "bounded",
        "invariants": ["maintainer-stacked-landing"],
        "affected_members": [f"pr-{target_pr}"],
        "contract_changed": False,
        "trust_boundary_changed": False,
        "topology_changed": False,
        "cross_member_interaction_changed": False,
    }

    planner_binding = {
        **input_binding,
        "artifact_binding": renderer._artifact_binding(
            {"input_binding": input_binding},
            norm_candidate,
            revision_digest,
            planner_source,
        ),
        "planner_source": copy.deepcopy(planner_source),
    }

    _, planner_packet, planner_result = renderer._planner_packet(
        {
            "objective": "maintainer_pr_landing",
            "purpose": "fix_verification",
            "contract": contract,
            "change": change,
            "planner": {
                "source": planner_source,
                "options": {},
                "discovery": {"requests_complete": True, "reviews_complete": True},
            },
            "work": norm_work,
        },
        norm_candidate,
        planner_binding,
        work=norm_work,
    )

    if observed_snapshot is not None:
        snapshot = observed_snapshot
    else:
        snapshot_candidate = {
            "repository": repository,
            "number": target_pr,
            "id": f"PR_kwDO_{target_pr}",
            "provider_identity": {
                "provider": "github",
                "repository_id": 1,
                "resource_id": target_pr,
            },
            "expected_head_sha": candidate_head,
            "expected_base_sha": candidate_base,
            "dependencies": [],
        }
        obs_endpoint = {
            "provider_identity": snapshot_candidate["provider_identity"],
            "head_sha": candidate_head,
            "base_sha": candidate_base,
            "dependencies": [],
        }
        snapshot = observer.build_snapshot(
            candidate=snapshot_candidate,
            observed_start=obs_endpoint,
            observed_end=obs_endpoint,
            surfaces={
                "metadata": {"complete": True, "records": []},
                "checks": {"complete": True, "records": []},
                "reviews": {"complete": True, "records": []},
                "comments": {"complete": True, "records": []},
                "threads": {"complete": True, "records": []},
                "reactions": {"complete": True, "records": []},
            },
            requested_surfaces=[
                "metadata",
                "checks",
                "reviews",
                "comments",
                "threads",
                "reactions",
            ],
            observation={"retrieved_at": "2026-09-22T12:00:00Z"},
        )

    observed = {
        "complete": True,
        "source": "live_review_adapter",
        "observed_at": "2026-09-22T12:00:00Z",
        "facts": {
            "ci": {
                "status": "success",
                "head_sha": candidate_head,
                "applicable_to": {
                    "head_sha": candidate_head,
                    "base_sha": candidate_base,
                    "effective_base_sha": effective_base,
                },
            },
            "review": {"status": "pending"},
        },
        "snapshot": snapshot,
        "pr_body": {
            "revision": renderer.semantic_digest(pr_body_text),
            "body": pr_body_text,
        },
    }

    gate_binding = {
        "repository": repository,
        "pull_request_id": f"PR_kwDO_{target_pr}",
        "candidate_head_sha": candidate_head,
        "base_sha": candidate_base,
        "effective_base_sha": effective_base,
        "revision_bindings_digest": revision_digest,
        "planner_input_digest": renderer.semantic_digest(planner_packet),
        "planner_result_digest": renderer.semantic_digest(planner_result),
    }

    gate = {
        "status": gate_status,
        "source": {
            "repository": repository,
            "authority": "policy",
            "revision": trusted_base_sha,
            "path": "skills/pr-merge-gate/SKILL.md",
            "trusted": True,
        },
        "input_binding": gate_binding,
        "input_binding_digest": renderer.semantic_digest(gate_binding),
        "evidence": {"exact_head": candidate_head},
    }

    input_data = {
        "schema_version": 1,
        "kind": renderer.INPUT_KIND,
        "repository": repository,
        "objective": "maintainer_pr_landing",
        "purpose": "fix_verification",
        "contract": contract,
        "candidate": candidate,
        "change": change,
        "input_binding": input_binding,
        "observed": observed,
        "revision_bindings": revision_bindings,
        "planner": {
            "source": planner_source,
            "packet": planner_packet,
            "result": planner_result,
        },
        "gate": gate,
        "work": norm_work,
        "judgments": [],
    }
    return input_data


def execute_maintainer_stack(
    *,
    input_data: dict[str, Any],
    trusted_base_sha: str,
    repository_root: Path,
    output_dir: Path,
    apply: bool = False,
    authorize: bool = False,
    serialized_writer: bool = False,
    token: str | None = None,
    api_url: str = "https://api.github.com",
) -> dict[str, Any]:
    """Normalize, render, and preview/publish maintainer artifacts from input data."""
    if apply and (not authorize or not serialized_writer):
        raise MaintainerWorkflowError(
            "remote apply requires explicit --authorize and --serialized-writer"
        )
    output_dir.mkdir(parents=True, exist_ok=True)

    normalized = renderer.normalize(
        input_data,
        trusted_base_sha=trusted_base_sha,
        repository_root=repository_root,
    )

    rendered = renderer.render(normalized)
    for filename, content in rendered.files.items():
        (output_dir / filename).write_text(content, encoding="utf-8")

    (output_dir / "manifest.json").write_text(
        json.dumps(rendered.manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    remote = None
    if apply:
        if not authorize or not serialized_writer:
            raise MaintainerWorkflowError(
                "remote apply requires explicit --authorize and --serialized-writer"
            )
        if not token:
            token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        if not token:
            raise MaintainerWorkflowError("remote apply requires GitHub token")

        remote = publisher.GitHubProvider(
            token,
            api_url=api_url,
            live_revalidator=live_adapter.resolve,
        )

    pub_result = publisher.publish(
        normalized,
        remote,
        apply=apply,
        authorized=authorize,
        serialized_writer=serialized_writer,
    )

    result_dict = pub_result.as_dict()
    (output_dir / "publication-result.json").write_text(
        json.dumps(result_dict, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    # Produce bounded model summary (<= 8192 bytes)
    summary = {
        "status": pub_result.status,
        "planner_action": normalized.planner_result.get("action"),
        "operations": pub_result.operations,
        "candidate": {
            "repository": normalized.data["repository"],
            "pull_request_number": normalized.data["candidate"]["pull_request"]["number"],
            "head_sha": normalized.data["candidate"]["head_sha"],
            "base_sha": normalized.data["candidate"]["base_sha"],
            "effective_base_sha": normalized.data["candidate"]["effective_base_sha"],
        },
        "output_directory": str(output_dir),
        "rendered_files": list(rendered.files.keys()),
        "reasons": pub_result.reasons,
    }
    encoded = json.dumps(summary, indent=2, ensure_ascii=False)
    if len(encoded.encode("utf-8")) > MAX_SUMMARY_BYTES:
        summary["operations"] = summary["operations"][:2]
        encoded = json.dumps(summary, indent=2, ensure_ascii=False)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", default=DEFAULT_REPOSITORY, help="repository full name")
    parser.add_argument("--pr", type=int, help="target pull request number")
    parser.add_argument("--head-sha", help="candidate head commit SHA")
    parser.add_argument("--base-sha", help="candidate base commit SHA")
    parser.add_argument("--trusted-base-sha", required=True, help="trusted base commit SHA")
    parser.add_argument("--effective-base-sha", help="effective base commit SHA")
    parser.add_argument("--input", help="path to input JSON, or '-' for stdin")
    parser.add_argument("--output-dir", type=Path, help="directory to store rendered artifacts")
    parser.add_argument("--gate-status", default="not_evaluated", help="explicit gate status")
    parser.add_argument("--apply", action="store_true", help="permit remote writes")
    parser.add_argument("--authorize", action="store_true", help="authorize remote writes")
    parser.add_argument("--serialized-writer", action="store_true", help="assert serialized writer")
    parser.add_argument("--token", help="GitHub token")
    parser.add_argument("--api-url", default="https://api.github.com")
    parser.add_argument(
        "--repository-root",
        type=Path,
        help="path to repository root (default: discovered from current working directory)",
    )
    parser.add_argument(
        "--source-manifest",
        help="optional explicit path to source reference JSON",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.repository_root:
        repo_root = args.repository_root.resolve()
    else:
        try:
            top_level = subprocess.check_output(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=os.getcwd(),
                text=True,
                stderr=subprocess.PIPE,
            ).strip()
            repo_root = Path(top_level).resolve()
        except Exception:
            repo_root = SCRIPT_DIR.parents[2].resolve()

    try:
        if args.input:
            input_data = _json_load(args.input)
        else:
            if not args.pr:
                raise MaintainerWorkflowError("--pr is required when --input is not supplied")
            head = args.head_sha or subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=repo_root, text=True
            ).strip()
            base = args.base_sha or args.trusted_base_sha

            input_data = assemble_review_artifacts_input(
                repository=args.repository,
                target_pr=args.pr,
                candidate_head=head,
                candidate_base=base,
                trusted_base_sha=args.trusted_base_sha,
                repository_root=repo_root,
                effective_base_sha=args.effective_base_sha,
                gate_status=args.gate_status,
            )

        output_dir = args.output_dir or Path(tempfile.mkdtemp(prefix="maintainer_artifacts_"))
        summary = execute_maintainer_stack(
            input_data=input_data,
            trusted_base_sha=args.trusted_base_sha,
            repository_root=repo_root,
            output_dir=output_dir,
            apply=args.apply,
            authorize=args.authorize,
            serialized_writer=args.serialized_writer,
            token=args.token,
            api_url=args.api_url,
        )
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0 if summary["status"] in {"preview", "published", "reconciled", "duplicate"} else 1
    except Exception as exc:
        print(f"ERROR MAINTAINER_REVIEW_STACK: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
