#!/usr/bin/env python3
"""Run the bounded evaluator evidence specification."""

import json
import sys

from policy_delivery_evidence_spec import run_model_checks

REQUIRED_COUNTEREXAMPLES = {
    "missing_requested_regression",
    "missing_next_action",
    "missing_compliance",
    "stale_candidate_binding",
}


def main() -> int:
    result = run_model_checks()
    print(json.dumps(result, indent=2, sort_keys=True))
    if result["violations"] or not result["positive_state_passes"]:
        return 1
    if set(result["counterexamples"]) != REQUIRED_COUNTEREXAMPLES:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
