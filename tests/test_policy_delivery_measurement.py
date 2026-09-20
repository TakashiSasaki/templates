from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from scripts.measure_policy_delivery import build_report, render_markdown


def test_measurement_uses_effective_policy_loader_without_emitting_bodies() -> None:
    root = Path(__file__).resolve().parents[1]
    report = build_report(root)

    assert report["coding"]["rule_count"] > 0
    assert report["coding"]["rules"]
    assert all("body" not in rule for rule in report["coding"]["rules"])
    assert report["host"]["prompt_assembly"] == "Unobserved"
    assert report["measurement"]["token_counts"] == "Unobserved; no model tokenizer is assumed"


def test_markdown_report_is_bounded_and_labels_unobserved_measurements() -> None:
    root = Path(__file__).resolve().parents[1]
    markdown = render_markdown(build_report(root))

    assert "Model prompt inclusion: **Unobserved**" in markdown
    assert "Actual model token counts: **Unobserved**" in markdown
    assert "Test material invariants" not in markdown
    assert "# Policy delivery measurement" in markdown


def test_log_aggregation_reads_metadata_without_exposing_body(tmp_path: Path) -> None:
    database = tmp_path / "logs.sqlite"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE logs (target TEXT, estimated_bytes INTEGER, feedback_log_body TEXT)"
        )
        connection.executemany(
            "INSERT INTO logs VALUES (?, ?, ?)",
            [("alpha", 10, "secret body"), ("alpha", 20, "another body")],
        )

    root = Path(__file__).resolve().parents[1]
    report = build_report(root, log_db=database)
    aggregate = report["authorized_log_aggregate"]

    assert aggregate["targets"] == [
        {"target": "alpha", "events": 2, "estimated_bytes": 30}
    ]
    assert "secret body" not in json.dumps(aggregate)
    assert "transcript bodies were not read or emitted" in aggregate["warning"]
