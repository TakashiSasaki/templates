from __future__ import annotations

import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HELPER_SOURCE = (
    ROOT / "components" / "capability.pwa" / "files" / "scripts" / "pwa_evidence_targets.py"
)
VALIDATOR_SOURCE = (
    ROOT
    / "components"
    / "capability.pwa"
    / "files"
    / ".template-composition"
    / "validators"
    / "validate_pwa_evidence.py"
)
MIGRATION = (
    ROOT
    / "components"
    / "capability.pwa"
    / "files"
    / "docs"
    / "migrations"
    / "pwa-offline-v1-to-v2.md"
)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validator = load_module("validate_pwa_policy_derived_evidence", VALIDATOR_SOURCE)


class PwaPolicyDerivedEvidenceTests(unittest.TestCase):
    def write_json(self, root: Path, relative: str, value: object) -> None:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    def fixture(
        self,
        root: Path,
        behavior: str,
        *,
        mutation_behavior: str = "not-applicable",
    ) -> object:
        scripts = root / "scripts"
        scripts.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(HELPER_SOURCE, scripts / "pwa_evidence_targets.py")
        self.write_json(root, "contracts/pwa-manifest.json", {"mode": "product"})
        self.write_json(root, "contracts/pwa-update.json", {"mode": "product"})
        self.write_json(
            root,
            "contracts/pwa-offline.json",
            {
                "mode": "product",
                "routePolicies": [
                    {"routeId": "home", "offlineReadBehavior": behavior}
                ],
                "mutationBehavior": mutation_behavior,
            },
        )
        module_name = f"pwa_evidence_targets_{behavior}_{mutation_behavior}".replace(
            "-", "_"
        )
        return load_module(module_name, scripts / "pwa_evidence_targets.py")

    def evidence(self, targets: list[dict[str, str]]) -> dict:
        records = []
        requirements = []
        for index, target in enumerate(targets, 1):
            record_id = f"record-{index:02d}"
            records.append(
                {
                    "id": record_id,
                    "target": target,
                    "positiveEvidence": [
                        {
                            "id": f"positive-{index:02d}",
                            "kind": "end-to-end-test",
                            "commandId": "browser-proof",
                        }
                    ],
                    "negativeEvidence": [
                        {
                            "id": f"negative-{index:02d}",
                            "kind": "end-to-end-test",
                            "commandId": "browser-proof",
                        }
                    ],
                }
            )
            requirements.append(
                {
                    "id": f"requirement-{index:02d}",
                    "targets": [target],
                    "recordIds": [record_id],
                    "requiredPositiveProofKinds": ["end-to-end-test"],
                }
            )
        return {
            "mode": "product",
            "commands": [
                {
                    "id": "browser-proof",
                    "execution": {"capabilities": ["browser"]},
                }
            ],
            "records": records,
            "requirements": requirements,
        }

    def test_network_only_policy_does_not_require_cached_content_claims(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            helper = self.fixture(root, "network-unavailable-presentation")
            targets = [dict(target) for target in helper.expected_targets(root)]
            item_ids = {target["itemId"] for target in targets}
            self.assertNotIn("offline-cached-content", item_ids)
            self.assertNotIn("freshness-unverified", item_ids)
            self.assertNotIn("pending-mutation-presentation", item_ids)
            self.assertNotIn("failed-mutation-presentation", item_ids)
            self.assertEqual(len(targets), 6)
            self.write_json(
                root,
                "contracts/implementation-evidence.json",
                self.evidence(targets),
            )
            self.assertEqual(validator.validate(root), [])

    def test_cached_content_policy_activates_cached_freshness_proofs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            helper = self.fixture(root, "cached-content-when-available")
            targets = [dict(target) for target in helper.expected_targets(root)]
            item_ids = {target["itemId"] for target in targets}
            self.assertIn("offline-cached-content", item_ids)
            self.assertIn("freshness-unverified", item_ids)
            self.assertNotIn("pending-mutation-presentation", item_ids)
            self.assertNotIn("failed-mutation-presentation", item_ids)
            self.assertEqual(len(targets), 8)
            self.write_json(
                root,
                "contracts/implementation-evidence.json",
                self.evidence(targets),
            )
            self.assertEqual(validator.validate(root), [])

    def test_queue_until_online_activates_pending_and_failure_presentations(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            helper = self.fixture(
                root,
                "network-unavailable-presentation",
                mutation_behavior="queue-until-online",
            )
            targets = [dict(target) for target in helper.expected_targets(root)]
            item_ids = {target["itemId"] for target in targets}
            self.assertNotIn("offline-cached-content", item_ids)
            self.assertNotIn("freshness-unverified", item_ids)
            self.assertIn("pending-mutation-presentation", item_ids)
            self.assertIn("failed-mutation-presentation", item_ids)
            self.assertEqual(len(targets), 8)
            self.write_json(
                root,
                "contracts/implementation-evidence.json",
                self.evidence(targets),
            )
            self.assertEqual(validator.validate(root), [])

    def test_cached_content_and_queue_policies_compose_all_conditional_families(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            helper = self.fixture(
                root,
                "cached-content-when-available",
                mutation_behavior="queue-until-online",
            )
            targets = [dict(target) for target in helper.expected_targets(root)]
            item_ids = {target["itemId"] for target in targets}
            self.assertTrue(
                {
                    "offline-cached-content",
                    "freshness-unverified",
                    "pending-mutation-presentation",
                    "failed-mutation-presentation",
                }.issubset(item_ids)
            )
            self.assertEqual(len(targets), 10)
            self.write_json(
                root,
                "contracts/implementation-evidence.json",
                self.evidence(targets),
            )
            self.assertEqual(validator.validate(root), [])

    def test_v1_to_v2_migration_explains_required_route_read_decision(self) -> None:
        text = MIGRATION.read_text(encoding="utf-8")
        for expected in (
            "each entry must also choose `offlineReadBehavior`",
            "every `controlledRouteIds` entry",
            '"offlineReadBehavior": "cached-content-when-available"',
            '"offlineReadBehavior": "network-unavailable-presentation"',
            "`cacheableDataClassifications`",
            "do not guess",
            "pendingMutationPresentation",
            "failedMutationPresentation",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, text)


if __name__ == "__main__":
    unittest.main()
