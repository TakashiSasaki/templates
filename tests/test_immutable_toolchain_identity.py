from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent_policy import cli, identity
from agent_policy.manifest import build_manifest

ROOT = Path(__file__).resolve().parents[1]
FULL_SHA = "a" * 40
OTHER_SHA = "b" * 40


class FakeDistribution:
    def __init__(self, direct_url: object) -> None:
        self.direct_url = direct_url

    def read_text(self, name: str) -> str | None:
        assert name == "direct_url.json"
        if self.direct_url is None:
            return None
        return json.dumps(self.direct_url)


def vcs_direct_url(*, requested: str, commit_id: str) -> dict[str, object]:
    return {
        "url": "https://github.com/TakashiSasaki/templates.git",
        "vcs_info": {
            "vcs": "git",
            "requested_revision": requested,
            "commit_id": commit_id,
        },
    }


def test_installed_vcs_revision_requires_matching_full_sha_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        identity,
        "distribution",
        lambda _name: FakeDistribution(
            vcs_direct_url(requested=FULL_SHA, commit_id=FULL_SHA)
        ),
    )
    assert identity.installed_vcs_revision() == FULL_SHA

    monkeypatch.setattr(
        identity,
        "distribution",
        lambda _name: FakeDistribution(
            vcs_direct_url(requested="policy", commit_id=FULL_SHA)
        ),
    )
    with pytest.raises(ValueError, match="not requested by full commit SHA"):
        identity.installed_vcs_revision()

    monkeypatch.setattr(
        identity,
        "distribution",
        lambda _name: FakeDistribution(
            vcs_direct_url(requested=FULL_SHA, commit_id=OTHER_SHA)
        ),
    )
    with pytest.raises(ValueError, match="does not match commit identity"):
        identity.installed_vcs_revision()


def test_checkout_revision_accepts_only_full_git_head(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        identity.subprocess,
        "check_output",
        lambda *args, **kwargs: FULL_SHA + "\n",
    )
    assert identity.checkout_revision(tmp_path) == FULL_SHA

    monkeypatch.setattr(
        identity.subprocess,
        "check_output",
        lambda *args, **kwargs: "policy\n",
    )
    with pytest.raises(ValueError, match="not a full lowercase commit SHA"):
        identity.checkout_revision(tmp_path)


def test_resolve_toolchain_revision_prefers_verified_installed_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(identity, "installed_vcs_revision", lambda: FULL_SHA)

    def checkout_must_not_run() -> str:
        raise AssertionError("checkout fallback must not run")

    monkeypatch.setattr(identity, "checkout_revision", checkout_must_not_run)
    assert identity.resolve_toolchain_revision() == FULL_SHA


def test_resolve_toolchain_revision_falls_back_to_checkout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(identity, "installed_vcs_revision", lambda: None)
    monkeypatch.setattr(identity, "checkout_revision", lambda: FULL_SHA)
    assert identity.resolve_toolchain_revision() == FULL_SHA


def test_resolve_toolchain_revision_fails_closed_without_immutable_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(identity, "installed_vcs_revision", lambda: None)
    monkeypatch.setattr(identity, "checkout_revision", lambda: None)
    with pytest.raises(ValueError, match="Unable to determine an immutable toolchain revision"):
        identity.resolve_toolchain_revision()


def test_explicit_and_generated_toolchain_revisions_require_full_sha() -> None:
    assert identity.resolve_toolchain_revision(FULL_SHA) == FULL_SHA
    with pytest.raises(ValueError, match="full lowercase commit SHA"):
        identity.resolve_toolchain_revision("LOCAL-DEVELOPMENT")
    with pytest.raises(ValueError, match="full lowercase commit SHA"):
        build_manifest(
            toolchain_revision="LOCAL-DEVELOPMENT",
            profiles=["core"],
            project_policy_files=["policy/project.md"],
            verification_command=None,
            agents_output_enabled=True,
            agents_output_path="AGENTS.md",
            enabled_skills=[],
        )


def test_cli_parser_rejects_mutable_explicit_toolchain_revision() -> None:
    with pytest.raises(SystemExit):
        cli.parser().parse_args(
            ["adopt", "prepare", "--toolchain-revision", "LOCAL-DEVELOPMENT"]
        )


def test_consumer_state_schemas_require_full_sha() -> None:
    config_schema = json.loads(
        (ROOT / "schemas/agent-policy.schema.json").read_text(encoding="utf-8")
    )
    adoption_schema = json.loads(
        (ROOT / "schemas/adoption-state.schema.json").read_text(encoding="utf-8")
    )
    expected = "^[0-9a-f]{40}$"
    assert (
        config_schema["properties"]["toolchain"]["properties"]["revision"]["pattern"]
        == expected
    )
    assert (
        adoption_schema["properties"]["toolchain"]["properties"]["revision"][
            "pattern"
        ]
        == expected
    )
