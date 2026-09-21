#!/usr/bin/env python3
"""Run the bounded evaluator evidence specification."""

import json
import sys

from policy_delivery_evidence_spec import run_model_checks, run_mutation_checks

REQUIRED_COUNTEREXAMPLES = {
    "missing_requested_regression",
    "missing_next_action",
    "missing_compliance",
    "missing_full_suite",
    "stale_candidate_binding",
}


def main() -> int:
    result = run_model_checks()
    mutations = run_mutation_checks()
    result["mutation_checks"] = mutations
    print(json.dumps(result, indent=2, sort_keys=True))
    if result["violations"] or not result["positive_state_passes"]:
        return 1
    if set(result["counterexamples"]) != REQUIRED_COUNTEREXAMPLES:
        return 1
    if not mutations["all_detected"]:
        return 1
    if any(not passed for passed in result["witness_results"].values()):
        return 1
    if result["reachable_invariant_violations"]:
        return 1
    if result["review_invariant_violations"] or not result["review_witness_passes"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
