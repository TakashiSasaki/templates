from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from scripts import trusted_review_freeze_provider as provider

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github/workflows/trusted-review-bootstrap.yml"
ACTION_PATH = ROOT / ".github/actions/trusted-review-freeze-role/action.yml"
SHA256 = "a" * 64


def load_yaml(path: Path) -> dict[str, object]:
    value = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    assert isinstance(value, dict)
    return value


def test_trusted_bootstrap_workflow_has_only_explicit_default_branch_dispatch() -> None:
    workflow = load_yaml(WORKFLOW_PATH)
    assert set(workflow["on"]) == {"workflow_dispatch"}
    job = workflow["jobs"]["bootstrap"]
    assert job["if"] == "github.repository_id == '1315875002' && github.ref == 'refs/heads/site'"
    assert job["permissions"] == {
        "contents": "read",
        "pull-requests": "read",
        "id-token": "write",
        "attestations": "write",
        "packages": "write",
    }
    steps = job["steps"]
    checkout = steps[0]
    assert checkout["with"]["ref"] == "${{ github.workflow_sha }}"
    assert checkout["with"]["persist-credentials"] == "false"
    assert "target_head" not in checkout["with"]["ref"]

    source = WORKFLOW_PATH.read_text(encoding="utf-8")
    for forbidden in (
        "pull_request_target",
        "workflow_run:",
        "pull_request:",
        "github.event.pull_request.title",
        "github.event.pull_request.body",
        "github.event.pull_request.head.ref",
        "artifact-metadata: write",
    ):
        assert forbidden not in source
    assert "pull-requests: write" not in source
    assert "create-storage-record: false" in source
    assert "${{ inputs.pr_number }}" in source
    assert "${{ steps.initialize.outputs.target_head }}" in source
    assert "TARGET_HEAD: ${{ steps.initialize.outputs.target_head }}" in source
    assert '--head "$TARGET_HEAD"' in source
    provider_source = (ROOT / "scripts/trusted_review_freeze_provider.py").read_text(
        encoding="utf-8"
    )
    assert '"--require-authenticated-provider"' in provider_source
    initialize = source.index(
        "name: Verify the observation and initialize from the exact target base"
    )
    login = source.index("name: Authenticate Docker to GHCR with the run-scoped token")
    materialize = source.index("name: Materialize the bootstrap image candidate")
    assert initialize < login < materialize


@pytest.mark.parametrize("actor", ["maintainer", "github-actions[bot]"])
def test_docker_login_reads_token_from_stdin(actor: str) -> None:
    seen: list[tuple[list[str], dict[str, object]]] = []

    def run(command: list[str], **kwargs: object) -> SimpleNamespace:
        seen.append((command, kwargs))
        return SimpleNamespace(stdout="")

    provider._docker_login("secret-token", actor=actor, runner=run)
    command, kwargs = seen[0]
    assert command == [
        "docker",
        "login",
        "ghcr.io",
        "--username",
        actor,
        "--password-stdin",
    ]
    assert kwargs["input"] == "secret-token\n"
    assert "secret-token" not in " ".join(command)


@pytest.mark.parametrize("actor", ["github-actions[app]", "github-actions[bot]extra"])
def test_docker_login_rejects_noncanonical_actor(actor: str) -> None:
    seen: list[list[str]] = []

    def run(command: list[str], **_kwargs: object) -> SimpleNamespace:
        seen.append(command)
        return SimpleNamespace(stdout="")

    with pytest.raises(provider.TrustedFreezeError, match="login actor is invalid"):
        provider._docker_login("secret-token", actor=actor, runner=run)
    assert not seen


def test_all_external_actions_are_full_sha_pinned() -> None:
    sources = [WORKFLOW_PATH.read_text(encoding="utf-8"), ACTION_PATH.read_text(encoding="utf-8")]
    references = re.findall(r"(?m)^\s*uses:\s*([^\s]+)", "\n".join(sources))
    external = [reference for reference in references if not reference.startswith("./")]
    assert external
    assert all(re.search(r"@[0-9a-f]{40}(?:\s|$)", reference) for reference in external)


def test_final_aggregate_is_pulled_and_protected_before_evidence_is_attested() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    image_attest = workflow.index("name: Attest the aggregate authority image")
    protect = workflow.index("name: Protect the final attested authority image")
    evidence = workflow.index("name: Record post-freeze protected-view verification")
    evidence_attest = workflow.index("name: Attest the exact aggregate freeze evidence bytes")
    handoff = workflow.index(
        "name: Generate the authenticated bootstrap handoff and reviewer packet"
    )
    output_attest = workflow.index("name: Verify both output-file attestations")
    destroy = workflow.index("name: Destroy producer-local protected authority paths")
    verify = workflow.index("name: Hydrate and verify the durable handoff in a fresh reviewer root")
    assert image_attest < protect < evidence < evidence_attest < handoff < verify
    assert output_attest < destroy < verify
    assert "cleanup-producer-views" in workflow
    assert "hydrate-handoff" in workflow
    assert "--output-root \"$WORK_ROOT/fresh-reviewer\"" in workflow
    assert "--local-view \"$WORK_ROOT/output/reviewer-local-view.json\"" in workflow
    upload_step = workflow.split("name: Upload the review handoff packet", 1)[1]
    assert "output/reviewer-local-view.json" not in upload_step
    assert '--manifest-digest "$MANIFEST_DIGEST"' in workflow
    assert '--freeze-evidence "$WORK_ROOT/evidence/freeze-evidence.json"' in workflow


def test_freeze_provider_fetches_only_attested_base_and_resolves_installer_from_base() -> None:
    source = (ROOT / "scripts/trusted_review_freeze_provider.py").read_text(encoding="utf-8")
    initialize = source.split("def _initialize_from_observation(", maxsplit=1)[1].split(
        "\ndef _protect_aggregate(", maxsplit=1
    )[0]
    assert "_verified_observation(observation_path)" in initialize
    assert "base_sha," in initialize
    assert "installer_revision," in initialize
    assert '"fetch",\n            "--no-tags"' in initialize
    assert "            base_sha,\n        ]," in initialize
    assert "            installer_revision,\n        ]," in initialize
    assert '            "head",\n' not in initialize
    assert "extract_immutable_installer" in initialize
    assert "--materialize-run-image" not in initialize


def test_metadata_digest_is_strict_and_emitted_as_one_safe_output(tmp_path: Path) -> None:
    metadata = tmp_path / "metadata.json"
    output = tmp_path / "github-output"
    output.write_text("", encoding="utf-8")
    metadata.write_text('{"containerimage.digest":"sha256:' + SHA256 + '"}', encoding="utf-8")
    provider._metadata_digest(metadata, output)
    assert output.read_text(encoding="utf-8") == f"digest=sha256:{SHA256}\n"

    metadata.write_text(
        '{"containerimage.digest":"sha256:' + SHA256 + '\\nother=x"}', encoding="utf-8"
    )
    with pytest.raises(provider.TrustedFreezeError, match="malformed"):
        provider._metadata_digest(metadata, output)


def test_image_manifest_verification_is_digest_addressed_and_checks_oci_media_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[list[str]] = []

    def run(command: list[str], **_kwargs: object) -> SimpleNamespace:
        seen.append(command)
        return SimpleNamespace(stdout='{"mediaType":"application/vnd.oci.image.manifest.v1+json"}')

    monkeypatch.setattr(provider.subprocess, "run", run)
    provider._verify_image_manifest(f"sha256:{SHA256}")
    assert seen[0][-1] == f"{provider.OCI_REPOSITORY}@sha256:{SHA256}"

    monkeypatch.setattr(
        provider.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            stdout='{"mediaType":"application/vnd.oci.image.index.v1+json"}'
        ),
    )
    with pytest.raises(provider.TrustedFreezeError, match="single-platform OCI"):
        provider._verify_image_manifest(f"sha256:{SHA256}")
