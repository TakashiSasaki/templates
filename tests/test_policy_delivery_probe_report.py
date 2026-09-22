from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts/check_policy_delivery_probe_report.py"


def _load_checker():
    spec = importlib.util.spec_from_file_location("check_policy_delivery_probe_report", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_probe_report_is_consistent() -> None:
    checker = _load_checker()
    result = checker.check_probe_report(ROOT)
    assert result["status"] == "CONSISTENT"
    assert result["policy_baseline"] == "ac95d6ee681ef422c0a8e1f714e94fbc78ff83aa"
    assert result["infrastructure_candidate"] == "3d05429778d091412a754e58e4773687e29116f7"
    assert result["capability_decision"] == "NOT_QUALIFIED"
    assert result["empirical_conclusion"] == "NOT_ESTABLISHED"


def _copy_worktree_files(tmp_path: Path) -> Path:
    (tmp_path / "docs").mkdir(parents=True)
    (tmp_path / "scripts").mkdir(parents=True)
    shutil.copy(ROOT / "docs/policy-delivery-experiment-baseline.json", tmp_path / "docs")
    shutil.copy(ROOT / "docs/policy-delivery-capability-probe.json", tmp_path / "docs")
    shutil.copy(ROOT / "docs/policy-delivery-experiment-report.json", tmp_path / "docs")
    shutil.copy(ROOT / "docs/policy-delivery-experiment-report.md", tmp_path / "docs")
    shutil.copy(ROOT / "docs/policy-delivery-matched-experiment.md", tmp_path / "docs")
    shutil.copy(ROOT / "scripts/run_matched_policy_delivery_experiment.py", tmp_path / "scripts")
    return tmp_path


def test_tampered_baseline_revision_is_rejected(tmp_path: Path) -> None:
    checker = _load_checker()
    shadow = _copy_worktree_files(tmp_path)
    baseline_path = shadow / "docs/policy-delivery-experiment-baseline.json"
    data = json.loads(baseline_path.read_text(encoding="utf-8"))
    data["policy_baseline"]["revision"] = "0" * 40
    baseline_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(checker.ProbeReportConsistencyError, match="policy revision"):
        checker.check_probe_report(shadow)


def test_tampered_infrastructure_revision_is_rejected(tmp_path: Path) -> None:
    checker = _load_checker()
    shadow = _copy_worktree_files(tmp_path)
    probe_path = shadow / "docs/policy-delivery-capability-probe.json"
    data = json.loads(probe_path.read_text(encoding="utf-8"))
    data["infrastructure_candidate_revision"] = "0" * 40
    probe_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(checker.ProbeReportConsistencyError, match="infrastructure revision"):
        checker.check_probe_report(shadow)


def test_tampered_network_enforcement_is_rejected(tmp_path: Path) -> None:
    checker = _load_checker()
    shadow = _copy_worktree_files(tmp_path)
    probe_path = shadow / "docs/policy-delivery-capability-probe.json"
    data = json.loads(probe_path.read_text(encoding="utf-8"))
    data["execution_environment"]["qualified_network_enforcement"]["status"] = "ESTABLISHED"
    probe_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(
        checker.ProbeReportConsistencyError, match="qualified_network_enforcement status"
    ):
        checker.check_probe_report(shadow)


def test_tampered_capability_decision_is_rejected(tmp_path: Path) -> None:
    checker = _load_checker()
    shadow = _copy_worktree_files(tmp_path)
    probe_path = shadow / "docs/policy-delivery-capability-probe.json"
    data = json.loads(probe_path.read_text(encoding="utf-8"))
    data["decision"]["capability"] = "QUALIFIED"
    probe_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(checker.ProbeReportConsistencyError, match="capability decision"):
        checker.check_probe_report(shadow)


def test_tampered_token_accounting_is_rejected(tmp_path: Path) -> None:
    checker = _load_checker()
    shadow = _copy_worktree_files(tmp_path)
    probe_path = shadow / "docs/policy-delivery-capability-probe.json"
    data = json.loads(probe_path.read_text(encoding="utf-8"))
    data["probe_execution"]["observed_token_usage"]["total_tokens"] += 1
    probe_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(checker.ProbeReportConsistencyError, match="total_tokens"):
        checker.check_probe_report(shadow)
