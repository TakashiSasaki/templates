from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.advance_publication_source import (
    AdvancePlan,
    PublicationAdvanceError,
    apply_plan,
    plan_advance,
)


class AdvancePublicationSourceGuardTests(unittest.TestCase):
    def test_unknown_provider_is_rejected_before_checkout_or_mutation(self) -> None:
        with self.assertRaisesRegex(PublicationAdvanceError, "provider must be exactly"):
            plan_advance(
                site_root=Path("does-not-exist"),
                provider="webapp",
                provider_root=Path("does-not-exist"),
                composition_root=Path("does-not-exist"),
                policy_root=Path("does-not-exist"),
                target_revision="1" * 40,
                expected_current="2" * 40,
            )

    def test_apply_plan_replaces_machine_projections_before_authority_lock(self) -> None:
        plan = AdvancePlan(
            provider="composition",
            current_revision="1" * 40,
            target_revision="2" * 40,
            revisions={"composition": "2" * 40, "policy": "3" * 40},
            source_lock_bytes=b"lock\n",
            agent_manifest_bytes=b"agent\n",
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch(
                "scripts.advance_publication_source.replace_regular_file"
            ) as replace:
                apply_plan(root, plan)

        self.assertEqual(
            [call.args[0].relative_to(root).as_posix() for call in replace.call_args_list],
            ["agent.json", "assets/agent.json", "publication-sources.json"],
        )
        self.assertEqual(replace.call_args_list[-1].args[1], b"lock\n")


if __name__ == "__main__":
    unittest.main()
