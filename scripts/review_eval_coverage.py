#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASE_ROOT = ROOT / "review-evals" / "cases"
RISK_DOMAINS = (
    "identity-and-authority",
    "namespace-and-indirection",
    "state-mutation-and-recovery",
    "concurrency-and-temporal-consistency",
    "privileged-execution",
    "persistence-and-integrity",
    "external-interaction",
    "resource-behavior",
    "build-provenance-and-ci",
    "consumer-and-execution-paths",
)
CASE_KINDS = ("empirical", "semantic-transposition", "control")
DISPOSITIONS = (
    "blocking-finding",
    "completed-no-blocking-finding",
    "incomplete-review",
)


def load_cases(case_root: Path) -> list[dict[str, Any]]:
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(case_root.rglob("*.json"))
    ]


def build_coverage_matrix(cases: list[dict[str, Any]]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for domain in RISK_DOMAINS:
        domain_cases = [case for case in cases if domain in case["risk_domains"]]
        kinds = Counter(case["kind"] for case in domain_cases)
        dispositions = Counter(
            case["expected_review"]["disposition"] for case in domain_cases
        )
        gaps: list[str] = []

        if not domain_cases:
            gaps.append("no-cases")
        for kind in CASE_KINDS:
            if kinds[kind] == 0:
                gaps.append(f"no-{kind}")
        for disposition in DISPOSITIONS:
            if dispositions[disposition] == 0:
                gaps.append(f"no-{disposition}")

        rows.append(
            {
                "domain": domain,
                "total": len(domain_cases),
                "kinds": {kind: kinds[kind] for kind in CASE_KINDS},
                "dispositions": {
                    disposition: dispositions[disposition]
                    for disposition in DISPOSITIONS
                },
                "case_ids": sorted(case["id"] for case in domain_cases),
                "coverage_observations": gaps,
            }
        )

    return {
        "schema_version": 1,
        "case_count": len(cases),
        "domains": rows,
    }


def render_markdown(matrix: dict[str, Any]) -> str:
    lines = [
        "| Risk domain | Total | Empirical | Transposition | Control | "
        "Blocking | Clean | Incomplete | Coverage observations |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in matrix["domains"]:
        kinds = row["kinds"]
        dispositions = row["dispositions"]
        observations = ", ".join(row["coverage_observations"]) or "—"
        lines.append(
            "| {domain} | {total} | {empirical} | {transposition} | {control} | "
            "{blocking} | {clean} | {incomplete} | {observations} |".format(
                domain=row["domain"],
                total=row["total"],
                empirical=kinds["empirical"],
                transposition=kinds["semantic-transposition"],
                control=kinds["control"],
                blocking=dispositions["blocking-finding"],
                clean=dispositions["completed-no-blocking-finding"],
                incomplete=dispositions["incomplete-review"],
                observations=observations,
            )
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Summarize reviewer-evaluation corpus coverage without creating an "
            "acceptance gate."
        )
    )
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASE_ROOT)
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    args = parser.parse_args()

    matrix = build_coverage_matrix(load_cases(args.cases))
    if args.format == "json":
        print(json.dumps(matrix, indent=2, sort_keys=True))
    else:
        print(render_markdown(matrix), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
