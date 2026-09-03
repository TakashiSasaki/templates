from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts import generate_agent_bootstrap as bootstrap


class AgentBootstrapPolicyMigrationRoutingTests(unittest.TestCase):
    def build_manifest(self) -> dict[str, object]:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_lock = root / "publication-sources.json"
            source_lock.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "repository": "TakashiSasaki/templates",
                        "publications": {
                            "composition": {"revision": "a" * 40},
                            "policy": {"revision": "b" * 40},
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            composition_release = root / "composition-installer.json"
            composition_release.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "channel": "stable",
                        "installer": {
                            "repository": "TakashiSasaki/templates",
                            "revision": "c" * 40,
                            "path": "scripts/install_composition_skill.py",
                            "sha256": "d" * 64,
                        },
                        "skill_source": {
                            "repository": "TakashiSasaki/templates",
                            "revision": "e" * 40,
                            "path": "skills/composition",
                        },
                        "toolchain": {
                            "repository": "TakashiSasaki/templates",
                            "revision": "f" * 40,
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            policy_release = root / "policy-installer.json"
            policy_release.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "installer": {
                            "repository": "TakashiSasaki/templates",
                            "revision": "1" * 40,
                            "path": "scripts/install_agent_policy_skill.py",
                        },
                        "skill_source": {
                            "repository": "TakashiSasaki/templates",
                            "revision": "2" * 40,
                            "path": "skills/agent-policy",
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            return bootstrap.build_manifest(
                source_lock,
                composition_release,
                policy_release,
            )

    def test_migration_routing_preserves_primary_selection_and_explicit_finalize(self) -> None:
        workflow = self.build_manifest()["policy_workflow"]
        self.assertEqual(
            workflow["unmanaged_apply_with_primary_instructions_argv"],
            [
                "{python}",
                "{skill_target}/scripts/bootstrap.py",
                "--repository",
                "{repository}",
                "--primary-instructions",
                "{primary_instructions}",
                "--apply",
            ],
        )
        self.assertEqual(
            workflow["primary_instructions_selection_source"],
            "unmanaged-inspect-output",
        )
        self.assertEqual(
            workflow["unmanaged_apply_outcomes"],
            {
                "fresh": "managed-and-validated",
                "migration": "prepared-and-previewed-finalization-pending",
            },
        )
        self.assertEqual(
            workflow["migration_finalization"],
            {
                "automatic": False,
                "requires_separate_explicit_instruction": True,
                "finalize_argv": [
                    "{python}",
                    "{skill_target}/scripts/run.py",
                    "--repository",
                    "{repository}",
                    "adopt",
                    "finalize",
                    "--apply",
                ],
                "post_finalize_verification_commands": ["validate", "check"],
            },
        )


if __name__ == "__main__":
    unittest.main()
