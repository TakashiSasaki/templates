from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/verify_trusted_review_candidate.py"


def load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "verify_trusted_review_candidate",
        SCRIPT,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


verifier = load_script()


def expected_probe() -> dict[str, object]:
    return {
        "validate": [],
        "render": [],
        "check": [],
        "materialize": ["REVIEW_BUNDLE_MATERIALIZED"],
        "verify": ["REVIEW_BUNDLE_VERIFIED"],
        "files": [
            "manifest.json",
            "procedure/SKILL.md",
            "procedure/references/github-pull-request-review-api.md",
            "semantic/review-policy.md",
        ],
        "manifest_bundle_format": 1,
        "manifest_has_adapter": False,
        "manifest_has_result_fields": False,
        "semantic_has_local_rule": True,
        "semantic_has_shared_review": True,
        "procedure_has_identity_refresh": True,
        "procedure_stops_before_merge": True,
    }


def test_candidate_verifier_closes_required_trusted_review_surface() -> None:
    required = set(verifier.TRUSTED_REVIEW_REQUIRED_PATHS)
    assert required == {
        "skills/agent-policy/SKILL.md",
        "skills/agent-policy/scripts/review_base.py",
        "skills/agent-policy/scripts/run.py",
        "skills/agent-policy/scripts/runtime_image.py",
        "skills/pr-review/SKILL.md",
        "skills/pr-review/references/github-pull-request-review-api.md",
        "src/agent_policy/commands/review_bundle.py",
        "templates/policy-context.md.j2",
    }
    verifier.verify_candidate_tree_contract(ROOT)


def test_candidate_probe_contract_is_provider_neutral_and_closed() -> None:
    verifier.verify_probe(expected_probe())

    adapter = expected_probe()
    adapter["manifest_has_adapter"] = True
    with pytest.raises(ValueError, match="end-to-end authority probe failed"):
        verifier.verify_probe(adapter)

    result_schema = expected_probe()
    result_schema["manifest_has_result_fields"] = True
    with pytest.raises(ValueError, match="end-to-end authority probe failed"):
        verifier.verify_probe(result_schema)

    extra_file = expected_probe()
    extra_file["files"] = [*extra_file["files"], "provider.json"]  # type: ignore[index]
    with pytest.raises(ValueError, match="end-to-end authority probe failed"):
        verifier.verify_probe(extra_file)


def test_candidate_revision_resolution_requires_one_full_sha(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(verifier, "git_text", lambda *_args: "not-a-sha")
    with pytest.raises(ValueError, match="full lowercase commit SHA"):
        verifier.resolve_candidate_revision("candidate")

    revision = "a" * 40
    monkeypatch.setattr(verifier, "git_text", lambda *_args: revision)
    assert verifier.resolve_candidate_revision("candidate") == revision


def test_candidate_verifier_does_not_treat_publication_as_verification(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    release = json.loads((ROOT / "release/toolchain.json").read_text(encoding="utf-8"))
    installer = json.loads(
        (ROOT / "release/skill-installer.json").read_text(encoding="utf-8")
    )
    runtime = json.loads(
        (ROOT / "skills/agent-policy/runtime-manifest.json").read_text(encoding="utf-8")
    )

    assert release["toolchain"] == runtime["toolchain"]
    assert installer["skill_source"]["revision"] != ""

    revision = "a" * 40
    monkeypatch.setattr(verifier, "verify_candidate", lambda _git_ref: revision)
    assert verifier.main(["--git-ref", "candidate"]) == 0
    output = capsys.readouterr().out
    assert f"Trusted review runtime candidate verified at {revision}." in output
    assert "Stable publication is intentionally unchanged" in output
    assert "a later Skill source must embed a runtime-manifest pinning this candidate" in output
    assert "a later installer publication must pin that Skill source" in output
