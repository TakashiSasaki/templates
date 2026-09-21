from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts/check_policy_delivery_evidence.py"


def _load():
    spec = importlib.util.spec_from_file_location("policy_delivery_evidence_consistency", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_canonical_manifest_and_projection_are_consistent() -> None:
    checker = _load()
    result = checker.check()
    assert result["candidate_revision"] == "04c8c69404eb728b18e6b10496a6d6508c6aa276"
    assert len(result["smoke_result_identity"]) == 64


def test_stale_document_projection_is_rejected(tmp_path: Path) -> None:
    checker = _load()
    documentation = ROOT / "docs/policy-delivery-matched-experiment.md"
    copy = tmp_path / documentation.name
    content = documentation.read_text(encoding="utf-8")
    current = json.loads(
        (ROOT / "docs/policy-delivery-clean-consumer-smoke-final.json").read_text(
            encoding="utf-8"
        )
    )["candidate"]["evaluator_source"]["sha256"]
    copy.write_text(content.replace(current, "0" * 64), encoding="utf-8")
    with pytest.raises(checker.EvidenceConsistencyError, match="projection is stale"):
        checker.check(documentation_path=copy)


def test_manifest_identity_cannot_be_changed_without_recomputing_it(tmp_path: Path) -> None:
    checker = _load()
    source = ROOT / "docs/policy-delivery-clean-consumer-smoke-final.json"
    manifest = json.loads(source.read_text(encoding="utf-8"))
    manifest["smoke_result_identity"] = "0" * 64
    copy = tmp_path / source.name
    copy.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(
        checker.EvidenceConsistencyError,
        match="smoke_result_identity",
    ):
        checker.check(manifest_path=copy)


def test_source_hash_drift_is_rejected(tmp_path: Path) -> None:
    checker = _load()
    source = ROOT / "docs/policy-delivery-clean-consumer-smoke-final.json"
    manifest = json.loads(source.read_text(encoding="utf-8"))
    manifest["candidate"]["evidence_checker"]["sha256"] = "0" * 64
    copy = tmp_path / source.name
    copy.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(checker.EvidenceConsistencyError, match="evidence checker hash"):
        checker.check(manifest_path=copy)


def test_qualification_metrics_must_match_the_executable_specification(
    tmp_path: Path,
) -> None:
    checker = _load()
    source = ROOT / "docs/policy-delivery-clean-consumer-smoke-final.json"
    manifest = json.loads(source.read_text(encoding="utf-8"))
    manifest["qualification"]["command_domain_case_count"] += 1
    copy = tmp_path / source.name
    copy.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(checker.EvidenceConsistencyError, match="qualification metrics"):
        checker.check(manifest_path=copy)
