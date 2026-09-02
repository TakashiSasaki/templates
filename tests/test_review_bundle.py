from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_policy import cli
from agent_policy.commands import render, review_bundle

TEST_REVISION = "a" * 40
LOCAL_POLICY = """---
id: project.review-local
severity: mandatory
overridable: true
order: 1000
---
# Review-local repository rule

Apply this local rule during review.
"""
SEMANTIC_OUTPUT = ".review-authority/review-policy.md"


def _write_repository(repository: Path) -> None:
    repository.mkdir()
    (repository / "policy").mkdir()
    (repository / "policy/review-local.md").write_text(LOCAL_POLICY, encoding="utf-8")
    (repository / ".agent-policy.yml").write_text(
        f"""schema_version: 2
toolchain:
  repository: TakashiSasaki/templates
  revision: {TEST_REVISION}
contexts:
  review:
    profiles:
      - core
      - security-baseline
      - review
    project_policy:
      files:
        - policy/review-local.md
outputs:
  review-authority:
    enabled: true
    path: {SEMANTIC_OUTPUT}
    context: review
    renderer: policy-context-md
skills:
  enabled:
    - pr-review
""",
        encoding="utf-8",
    )
    assert render.run(repository, ".agent-policy.yml") == []


def _has_error(diagnostics: list[object]) -> bool:
    return any(getattr(item, "level", None) == "error" for item in diagnostics)


def test_review_bundle_materializes_only_procedure_and_semantic_authority(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "trusted-base"
    _write_repository(repository)
    bundle = tmp_path / "review-bundle"

    diagnostics = review_bundle.materialize(
        repository,
        ".agent-policy.yml",
        bundle,
        SEMANTIC_OUTPUT,
    )
    assert not _has_error(diagnostics)
    assert "manifest_sha256=" in diagnostics[0].message

    actual_files = {
        path.relative_to(bundle).as_posix()
        for path in bundle.rglob("*")
        if path.is_file()
    }
    assert actual_files == {
        "manifest.json",
        "procedure/SKILL.md",
        "procedure/references/github-pull-request-review-api.md",
        "semantic/review-policy.md",
    }

    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["bundle_format"] == 1
    assert manifest["semantic"]["renderer"] == "policy-context-md"
    assert manifest["semantic"]["bundle_path"] == "semantic/review-policy.md"
    assert "adapter" not in manifest
    assert "analysis_status" not in manifest
    assert "comments" not in manifest
    assert "unanchored_findings" not in manifest

    diagnostics = review_bundle.verify(
        repository,
        ".agent-policy.yml",
        bundle,
        SEMANTIC_OUTPUT,
    )
    assert not _has_error(diagnostics)
    assert "manifest_sha256=" in diagnostics[0].message


def test_review_bundle_verification_fails_closed_on_inventory_drift(tmp_path: Path) -> None:
    repository = tmp_path / "trusted-base"
    _write_repository(repository)
    bundle = tmp_path / "review-bundle"
    assert not _has_error(
        review_bundle.materialize(
            repository,
            ".agent-policy.yml",
            bundle,
            SEMANTIC_OUTPUT,
        )
    )

    (bundle / "unexpected.txt").write_text("drift\n", encoding="utf-8")
    diagnostics = review_bundle.verify(
        repository,
        ".agent-policy.yml",
        bundle,
        SEMANTIC_OUTPUT,
    )

    assert _has_error(diagnostics)
    assert "inventory" in diagnostics[0].message


def test_review_bundle_materialize_never_clobbers_existing_destination(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "trusted-base"
    _write_repository(repository)
    bundle = tmp_path / "review-bundle"
    bundle.mkdir()
    sentinel = bundle / "sentinel.txt"
    sentinel.write_text("keep\n", encoding="utf-8")

    diagnostics = review_bundle.materialize(
        repository,
        ".agent-policy.yml",
        bundle,
        SEMANTIC_OUTPUT,
    )

    assert _has_error(diagnostics)
    assert "must not already exist" in diagnostics[0].message
    assert sentinel.read_text(encoding="utf-8") == "keep\n"
    assert set(path.name for path in bundle.iterdir()) == {"sentinel.txt"}


def test_review_bundle_materialize_cleans_owned_partial_destination_for_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "trusted-base"
    _write_repository(repository)
    bundle = tmp_path / "review-bundle"
    original_write = review_bundle._write_bundle_tree
    calls = 0

    def fail_during_publication(root: Path, expected: dict[str, bytes]) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            (root / "manifest.json").write_bytes(b"partial")
            raise OSError("simulated publication failure")
        original_write(root, expected)

    monkeypatch.setattr(review_bundle, "_write_bundle_tree", fail_during_publication)
    diagnostics = review_bundle.materialize(
        repository,
        ".agent-policy.yml",
        bundle,
        SEMANTIC_OUTPUT,
    )

    assert _has_error(diagnostics)
    assert "simulated publication failure" in diagnostics[0].message
    assert not bundle.exists()

    monkeypatch.setattr(review_bundle, "_write_bundle_tree", original_write)
    retry = review_bundle.materialize(
        repository,
        ".agent-policy.yml",
        bundle,
        SEMANTIC_OUTPUT,
    )
    assert not _has_error(retry)


def test_review_bundle_rejects_destination_overlap_in_both_directions(tmp_path: Path) -> None:
    repository = tmp_path / "trusted-base"
    _write_repository(repository)

    inside = review_bundle.materialize(
        repository,
        ".agent-policy.yml",
        repository / "bundle",
        SEMANTIC_OUTPUT,
    )
    ancestor = review_bundle.materialize(
        repository,
        ".agent-policy.yml",
        tmp_path,
        SEMANTIC_OUTPUT,
    )

    assert _has_error(inside)
    assert _has_error(ancestor)
    assert "overlap" in inside[0].message
    assert "overlap" in ancestor[0].message


def test_review_bundle_requires_pr_review_enabled_in_trusted_config(tmp_path: Path) -> None:
    repository = tmp_path / "trusted-base"
    _write_repository(repository)
    config = repository / ".agent-policy.yml"
    config.write_text(
        config.read_text(encoding="utf-8").replace(
            "  enabled:\n    - pr-review\n",
            "  enabled: []\n",
        ),
        encoding="utf-8",
    )
    assert render.run(repository, ".agent-policy.yml") == []

    diagnostics = review_bundle.materialize(
        repository,
        ".agent-policy.yml",
        tmp_path / "bundle",
        SEMANTIC_OUTPUT,
    )

    assert _has_error(diagnostics)
    assert "does not enable pr-review" in diagnostics[0].message


def test_review_bundle_rejects_provider_specific_semantic_renderer(tmp_path: Path) -> None:
    repository = tmp_path / "trusted-base"
    _write_repository(repository)
    config = repository / ".agent-policy.yml"
    config.write_text(
        config.read_text(encoding="utf-8").replace(
            "renderer: policy-context-md",
            "renderer: github-review-json-v1",
        ),
        encoding="utf-8",
    )
    assert render.run(repository, ".agent-policy.yml") == []

    diagnostics = review_bundle.materialize(
        repository,
        ".agent-policy.yml",
        tmp_path / "bundle",
        SEMANTIC_OUTPUT,
    )

    assert _has_error(diagnostics)
    assert "must use policy-context-md" in diagnostics[0].message


def test_review_bundle_direct_api_rejects_mutable_checkout(tmp_path: Path) -> None:
    repository = tmp_path / "mutable-checkout"
    _write_repository(repository)
    (repository / ".git").mkdir()

    diagnostics = review_bundle.materialize(
        repository,
        ".agent-policy.yml",
        tmp_path / "bundle",
        SEMANTIC_OUTPUT,
    )

    assert _has_error(diagnostics)
    assert "must not contain .git metadata" in diagnostics[0].message


def test_review_bundle_cli_requires_trusted_snapshot_mode(
    tmp_path: Path,
    capsys: object,
) -> None:
    repository = tmp_path / "mutable-checkout"
    repository.mkdir()
    (repository / ".git").mkdir()

    result = cli.main(
        [
            "--repository",
            str(repository),
            "review-bundle",
            "--semantic-output",
            SEMANTIC_OUTPUT,
            "materialize",
            "--destination",
            str(tmp_path / "bundle"),
        ]
    )

    assert result == 2
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    assert "review-bundle requires trusted review snapshot mode" in captured.err
