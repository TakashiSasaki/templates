#!/usr/bin/env python3
"""Fetch a qualified Site Pages artifact for a PR base revision.

This is a diagnostic accelerator only. It never substitutes for the canonical
PR build or merge qualification. Missing reusable evidence is reported with
exit status 3 so callers can defer to canonical CI; malformed or inconsistent
evidence fails closed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile
import zipfile

from scripts.site_build_artifact import (
    ArtifactError,
    MANIFEST,
    WORKFLOW,
    identity_key,
    validate_and_extract,
)


class NoArtifact(ArtifactError):
    """No qualified reusable base artifact is currently available."""


def api(path: str) -> dict:
    return json.loads(subprocess.check_output(["gh", "api", path], text=True))


def list_all(path: str, key: str) -> list[dict]:
    result: list[dict] = []
    separator = "&" if "?" in path else "?"
    for page in range(1, 101):
        items = api(f"{path}{separator}per_page=100&page={page}")[key]
        result.extend(items)
        if len(items) < 100:
            return result
    raise ArtifactError("GitHub pagination limit exceeded")


def candidate_runs(runs: list[dict], *, repository: str, base_sha: str,
                   current_run: int) -> list[dict]:
    allowed_events = {"pull_request", "schedule", "workflow_dispatch"}
    return sorted(
        (
            run
            for run in runs
            if run.get("id") != current_run
            and run.get("path") == WORKFLOW
            and run.get("head_sha") == base_sha
            and run.get("event") in allowed_events
            and run.get("head_repository", {}).get("full_name") == repository
        ),
        key=lambda run: (run.get("run_number", 0), run.get("run_attempt", 0)),
        reverse=True,
    )


def select_artifact(run: dict, jobs: list[dict], artifacts: list[dict], *, base_sha: str) -> dict | None:
    builds = [job for job in jobs if job.get("name") in {"build", "build / build"}]
    if len(builds) != 1:
        return None
    build = builds[0]
    if build.get("status") != "completed" or build.get("conclusion") != "success":
        return None
    matches = [artifact for artifact in artifacts if artifact.get("name") == "github-pages" and not artifact.get("expired")]
    if len(matches) != 1:
        return None
    artifact = matches[0]
    binding = artifact.get("workflow_run", {})
    if binding.get("id") != run.get("id") or binding.get("head_sha") != base_sha:
        raise ArtifactError("base artifact is bound to a different run or Site revision")
    digest = artifact.get("digest", "")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        raise ArtifactError("base artifact has no immutable digest")
    return artifact


def read_expected_inputs(archive: Path, *, digest: str, repository: str, base_sha: str) -> dict:
    with archive.open("rb") as source:
        actual = "sha256:" + hashlib.file_digest(source, "sha256").hexdigest()
    if actual != digest:
        raise ArtifactError("base artifact archive digest mismatch")
    with zipfile.ZipFile(archive) as bundle:
        if bundle.namelist() != ["artifact.tar"]:
            raise ArtifactError("expected exactly one Pages artifact.tar")
        with bundle.open("artifact.tar") as source, tempfile.NamedTemporaryFile() as output:
            shutil.copyfileobj(source, output)
            output.flush()
            with tarfile.open(output.name) as pages:
                members = pages.getmembers()
                manifest_members = [member for member in members if member.isfile() and member.name == MANIFEST]
                if len(manifest_members) != 1:
                    raise ArtifactError(f"missing artifact {MANIFEST}")
                manifest = json.load(pages.extractfile(manifest_members[0]))
    if not isinstance(manifest, dict) or set(manifest) != {"inputs", "identity"}:
        raise ArtifactError("invalid artifact build input manifest")
    expected = manifest.get("inputs")
    if not isinstance(expected, dict) or manifest.get("identity") != identity_key(expected):
        raise ArtifactError("invalid artifact build input identity")
    if expected.get("repository") != repository or expected.get("site") != base_sha:
        raise ArtifactError("artifact inputs are not bound to the requested PR base")
    if expected.get("staging") or expected.get("staging_ids") or expected.get("deployment_timestamp"):
        raise ArtifactError("focused lane requires an ordinary non-staged base artifact")
    return expected


def fetch_base_artifact(*, repository: str, base_sha: str, current_run: int,
                        target: Path) -> dict:
    runs = list_all(
        f"repos/{repository}/actions/workflows/build-pages.yml/runs?head_sha={base_sha}",
        "workflow_runs",
    )
    for run in candidate_runs(runs, repository=repository, base_sha=base_sha, current_run=current_run):
        jobs = list_all(f"repos/{repository}/actions/runs/{run['id']}/jobs?filter=latest", "jobs")
        artifacts = list_all(f"repos/{repository}/actions/runs/{run['id']}/artifacts", "artifacts")
        artifact = select_artifact(run, jobs, artifacts, base_sha=base_sha)
        if not artifact:
            continue
        with tempfile.TemporaryDirectory() as tempdir:
            archive = Path(tempdir) / "pages.zip"
            with archive.open("wb") as output:
                subprocess.run(
                    ["gh", "api", f"repos/{repository}/actions/artifacts/{artifact['id']}/zip"],
                    stdout=output,
                    check=True,
                )
            expected = read_expected_inputs(
                archive,
                digest=artifact["digest"],
                repository=repository,
                base_sha=base_sha,
            )
            target.parent.mkdir(parents=True, exist_ok=True)
            validate_and_extract(archive, expected, artifact["digest"], target)
        return {
            "producer_run": run["id"],
            "artifact_id": artifact["id"],
            "digest": artifact["digest"],
            "site": expected["site"],
            "composition": expected["composition"],
            "policy": expected["policy"],
        }
    raise NoArtifact("no successful unexpired canonical Pages artifact exists for the PR base SHA")


def write_github_output(path: Path, evidence: dict) -> None:
    with path.open("a", encoding="utf-8") as output:
        output.write("available=true\n")
        output.write(f"producer_run={evidence['producer_run']}\n")
        output.write(f"artifact_id={evidence['artifact_id']}\n")
        output.write(f"artifact_digest={evidence['digest']}\n")
        output.write(f"composition_revision={evidence['composition']}\n")
        output.write(f"policy_revision={evidence['policy']}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--base-sha", default=os.environ.get("BASE_SHA", ""))
    parser.add_argument("--current-run", type=int, default=int(os.environ.get("GITHUB_RUN_ID", "0") or 0))
    parser.add_argument("--target", type=Path, default=Path("build/site"))
    parser.add_argument("--metadata", type=Path, default=Path("build/focused-audience-base-artifact.json"))
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repository):
        print("invalid repository", file=os.sys.stderr)
        return 1
    if not re.fullmatch(r"[0-9a-f]{40}", args.base_sha):
        print("invalid base SHA", file=os.sys.stderr)
        return 1
    try:
        evidence = fetch_base_artifact(
            repository=args.repository,
            base_sha=args.base_sha,
            current_run=args.current_run,
            target=args.target,
        )
    except NoArtifact as exc:
        print(str(exc), file=os.sys.stderr)
        return 3
    except (ArtifactError, OSError, subprocess.CalledProcessError, ValueError, zipfile.BadZipFile, tarfile.TarError) as exc:
        print(f"focused audience base artifact validation failed: {exc}", file=os.sys.stderr)
        return 1
    args.metadata.parent.mkdir(parents=True, exist_ok=True)
    args.metadata.write_text(json.dumps(evidence, sort_keys=True) + "\n", encoding="utf-8")
    if args.github_output:
        write_github_output(args.github_output, evidence)
    print(json.dumps(evidence, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
