#!/usr/bin/env python3
"""Run existing real-consumer tests as a bounded pre-qualification spine."""
from __future__ import annotations
import sys
from pathlib import Path
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
TESTS = (
    'test_selected_component_validation.SelectedComponentValidationTests.test_minimal_skill_runs_only_selected_component_validators',
    'test_selected_component_validation.SelectedComponentValidationTests.test_tampered_managed_validator_halts_before_dispatch',
    'test_selected_component_validation.SelectedComponentValidationTests.test_registry_cannot_dispatch_entrypoint_owned_by_another_component',
    'test_composer_cli_dispatch.ComposerDispatchTests.test_flag_first_initial_and_update_dispatch_match_command_first_behavior',
)


def main() -> int:
    suite = unittest.defaultTestLoader.loadTestsFromNames(TESTS)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() and not result.skipped else 1


if __name__ == '__main__':
    raise SystemExit(main())
