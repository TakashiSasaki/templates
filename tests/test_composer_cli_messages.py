from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from composer_cli_messages import consumer_message, remediate_payload  # noqa: E402


class ComposerCliMessageTests(unittest.TestCase):
    def test_source_transition_messages_preserve_reason_and_add_next_action(self) -> None:
        old_revision = "1" * 40
        new_revision = "2" * 40
        unavailable = consumer_message(
            {
                "code": "OLD_SOURCE_REVISION_UNAVAILABLE",
                "message": f"old composition source revision is not available in the local source history: {old_revision}",
            }
        )
        self.assertIn(old_revision, unavailable)
        self.assertIn("Make that locked revision available", unavailable)
        self.assertIn("do not bypass the ancestry check", unavailable)

        non_descendant = consumer_message(
            {
                "code": "SOURCE_REVISION_NOT_DESCENDANT",
                "message": (
                    f"target composition source revision {new_revision} is not a descendant "
                    f"of old revision {old_revision}"
                ),
            }
        )
        self.assertIn(old_revision, non_descendant)
        self.assertIn(new_revision, non_descendant)
        self.assertIn("locked source revision itself or a descendant", non_descendant)
        self.assertNotIn("ordinary update", non_descendant)

    def test_recovery_messages_require_matching_operation_and_exact_source(self) -> None:
        required = consumer_message(
            {
                "code": "RECOVERY_REQUIRED",
                "message": "interrupted managed-state transaction is present",
            }
        )
        self.assertIn("matching `apply --mode update` or `apply --mode upgrade`", required)
        self.assertIn("exact Composition source revision", required)
        self.assertIn("do not start a new plan", required)

        revision = "a" * 40
        mismatch = consumer_message(
            {
                "code": "RECOVERY_SOURCE_MISMATCH",
                "message": f"recovery requires the exact source revision recorded by the transaction: {revision}",
            }
        )
        self.assertIn(revision, mismatch)
        self.assertIn("Check out that exact Composition revision", mismatch)
        self.assertIn("upgrade, recovery must omit --config", mismatch)

        operation = consumer_message(
            {
                "code": "RECOVERY_OPERATION_MISMATCH",
                "message": "existing transaction operation is upgrade, not update",
            }
        )
        self.assertIn("operation recorded", operation)
        self.assertIn("instead of changing or deleting the marker", operation)

    def test_local_modification_and_compatibility_boundaries_are_fail_closed_and_actionable(self) -> None:
        local = consumer_message(
            {
                "code": "LOCAL_MODIFICATION",
                "message": "locally modified managed material cannot be replaced",
                "destination": "docs/architecture.md",
                "ownership": "managed",
            }
        )
        self.assertIn("docs/architecture.md", local)
        self.assertIn("will not merge, overwrite, or delete", local)
        self.assertIn("rerun `plan`", local)

        version = consumer_message(
            {
                "code": "COMPONENT_VERSION_UPGRADE_REQUIRED",
                "message": "component version changed",
                "component": "artifact.skill-core",
            }
        )
        self.assertIn("artifact.skill-core", version)
        self.assertIn("`--mode upgrade`", version)
        self.assertIn("explicit --config", version)

        owner = consumer_message(
            {
                "code": "FILE_OWNER_TRANSITION_UPGRADE_REQUIRED",
                "message": "material owner changes",
                "destination": "shared.txt",
            }
        )
        self.assertIn("current upgrade also does not infer owner migration", owner)
        self.assertIn("source-side migration design", owner)

        ownership = consumer_message(
            {
                "code": "OWNERSHIP_TRANSITION_NOT_SUPPORTED",
                "message": "explicit upgrade does not infer ownership migration",
                "destination": "seed.txt",
            }
        )
        self.assertIn("Explicit upgrade cannot infer", ownership)
        self.assertIn("rather than editing lock metadata", ownership)

    def test_config_boundary_messages_distinguish_update_new_upgrade_and_recovery(self) -> None:
        update = consumer_message(
            {
                "code": "UPDATE_CONFIG_NOT_ALLOWED",
                "message": "update does not accept --config",
            }
        )
        self.assertIn("preserves normalized lock-v2 intent", update)
        self.assertIn("use `--mode upgrade`", update)

        new_upgrade = consumer_message(
            {
                "code": "UPGRADE_CONFIG_REQUIRED",
                "message": "upgrade requires --config",
            }
        )
        self.assertIn("new upgrade requires --config", new_upgrade)
        self.assertIn("recovery omits --config", new_upgrade)

        recovery = consumer_message(
            {
                "code": "RECOVERY_CONFIG_NOT_ALLOWED",
                "message": "do not supply --config",
            }
        )
        self.assertIn("Remove --config", recovery)
        self.assertIn("`apply --mode upgrade`", recovery)

    def test_payload_remediation_updates_top_level_and_both_conflict_views(self) -> None:
        conflict = {
            "code": "LOCAL_MODIFICATION",
            "message": "locally modified managed material cannot be replaced",
            "destination": "managed.txt",
            "ownership": "managed",
        }
        source = {
            "status": "conflict",
            "code": "MANAGED_LOCK_REQUIRED",
            "message": "managed operation requires lock",
            "conflicts": [conflict],
            "files": {"conflict": [conflict]},
        }
        result = remediate_payload(source)
        self.assertIn("Run `inspect`", result["message"])
        self.assertIn("will not merge, overwrite, or delete", result["conflicts"][0]["message"])
        self.assertIn("will not merge, overwrite, or delete", result["files"]["conflict"][0]["message"])
        self.assertEqual(source["message"], "managed operation requires lock")
        self.assertEqual(source["conflicts"][0]["message"], "locally modified managed material cannot be replaced")


if __name__ == "__main__":
    unittest.main()
