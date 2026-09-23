from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "measure_maintainer_efficiency.py"


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    import sys

    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


measurement_module = _load_module("measure_maintainer_efficiency", SCRIPT_PATH)


def test_maintainer_efficiency_measurement_structure_and_invariants() -> None:
    report = measurement_module.run_maintainer_efficiency_measurement(ROOT)

    assert report["schema_version"] == 1
    assert report["kind"] == "maintainer-efficiency-measurement"

    comparison = report["comparison"]
    baseline = comparison["baseline_adhoc_polling"]
    new_flow = comparison["new_bounded_entrypoint_adapter"]

    # Mechanical return reductions
    assert baseline["model_returns"] == 4
    assert new_flow["model_returns"] == 1
    assert new_flow["stop_attempt"] == 3
    assert new_flow["unchanged_suppression_count"] == 1

    # Bounded bytes
    assert new_flow["caller_facing_max_summary_bytes"] <= 8192
    assert (
        new_flow["caller_facing_summary_bytes_total"]
        < new_flow["full_persisted_snapshot_bytes_total"]
    )

    # Invariants on token savings accounting (MUST NOT claim token savings without observation)
    token_accounting = report["token_savings_accounting"]
    assert token_accounting["token_savings_claimed"] is False
    assert token_accounting["token_savings_status"] == "proxy_unobserved"
    assert "proxy" in token_accounting["justification"].lower()

    # Efficiency deltas
    deltas = report["efficiency_deltas"]
    assert deltas["model_return_reduction_ratio"] == 0.75
    assert deltas["missed_change_count"] == 0
    assert deltas["unchanged_poll_suppressions"] == 1
    assert deltas["elapsed_ms"] >= 0.0


def test_measure_maintainer_efficiency_cli_main() -> None:
    exit_code = measurement_module.main(["--json"])
    assert exit_code == 0
