from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from generated_release_bundle_producer_fixture import (  # noqa: E402
    _install_release_bundle_producer,
)
from generated_release_evidence_producer_fixture import (  # noqa: E402
    _install_release_evidence_producer,
)
from test_generated_release_evidence_production import (  # noqa: E402
    _commit_generated_repository,
)
from test_generated_repository_conformance import (  # noqa: E402
    _generated_repository,
    _is_template_maintainer_source,
    _load_json,
    _run_generated_python,
    _write_json,
)


@unittest.skipUnless(
    _is_template_maintainer_source(),
    "template-maintainer-only generated release bundle production suite",
)
class GeneratedReleaseBundleProductionTests(unittest.TestCase):
    def prepare_approved_release(self, root: Path) -> str:
        _install_release_evidence_producer(root)
        _install_release_bundle_producer(root)
        revision = _commit_generated_repository(root)
        release = _run_generated_python(
            root,
            "-I",
            "product/produce_release_evidence.py",
            "--revision",
            revision,
        )
        self.assertEqual(
            0,
            release.returncode,
            f"stdout:\n{release.stdout}\nstderr:\n{release.stderr}",
        )
        return revision

    def run_bundle(
        self,
        root: Path,
        revision: str,
        *arguments: str,
    ):
        return _run_generated_python(
            root,
            "-I",
            "product/produce_release_bundle.py",
            "--revision",
            revision,
            *arguments,
        )

    def assert_bundle_validates(self, root: Path, revision: str) -> None:
        commands = (
            (
                "-B",
                "scripts/validate_release_bundle.py",
                "--expected-revision",
                revision,
            ),
            (
                "-B",
                "-m",
                "scripts.validate_release_bundle",
                "--expected-revision",
                revision,
            ),
        )
        for command in commands:
            with self.subTest(command=command):
                result = _run_generated_python(root, *command)
                self.assertEqual(
                    0,
                    result.returncode,
                    f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
                )

    def test_reviewed_producer_materializes_exact_digest_closed_bundle(
        self,
    ) -> None:
        with _generated_repository() as root:
            revision = self.prepare_approved_release(root)

            result = self.run_bundle(root, revision)

            self.assertEqual(
                0,
                result.returncode,
                f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
            )
            self.assertIn("generated release bundle:", result.stdout)

            manifest = _load_json(root / "contracts/manifest.json")
            bundle_path = root / "contracts/release-bundle.json"
            bundle = _load_json(bundle_path)
            index = _load_json(root / "product/release-bundle-index.json")
            record_id = index["currentRecordId"]
            record_path = (
                root / f"product/release-bundle-records/{record_id}.json"
            )

            self.assertEqual("product", bundle["mode"])
            self.assertEqual(revision, bundle["subject"]["revision"])
            self.assertEqual("ready", bundle["handoff"]["status"])
            self.assertEqual(record_id, bundle["provenance"]["id"])
            self.assertEqual(
                f"product/release-bundle-records/{record_id}.json",
                bundle["provenance"]["locator"],
            )
            self.assertEqual(bundle_path.read_bytes(), record_path.read_bytes())

            expected_entries = [
                entry
                for entry in manifest["contracts"]
                if entry["id"] != "release_bundle"
            ]
            self.assertEqual(
                [entry["id"] for entry in expected_entries],
                [artifact["contractId"] for artifact in bundle["artifacts"]],
            )
            for entry, artifact in zip(
                expected_entries,
                bundle["artifacts"],
                strict=True,
            ):
                self.assertEqual(entry["document"], artifact["path"])
                self.assertEqual(
                    hashlib.sha256(
                        (root / entry["document"]).read_bytes()
                    ).hexdigest(),
                    artifact["sha256"],
                )

            self.assertEqual(1, len(index["records"]))
            self.assertEqual("current", index["records"][0]["status"])
            self.assertEqual(
                hashlib.sha256(record_path.read_bytes()).hexdigest(),
                index["records"][0]["bundleSha256"],
            )
            self.assert_bundle_validates(root, revision)

        self.assertEqual(
            "template",
            _load_json(ROOT / "contracts/release-bundle.json")["mode"],
        )
        self.assertFalse((ROOT / "product").exists())

    def test_changed_active_contract_makes_current_bundle_stale(self) -> None:
        with _generated_repository() as root:
            revision = self.prepare_approved_release(root)
            self.assertEqual(0, self.run_bundle(root, revision).returncode)

            surfaces_path = root / "contracts/surfaces.json"
            surfaces = _load_json(surfaces_path)
            surfaces["surfaces"][0]["purpose"] += " Changed after bundling."
            _write_json(surfaces_path, surfaces)

            validation = _run_generated_python(
                root,
                "-B",
                "scripts/validate_release_bundle.py",
                "--expected-revision",
                revision,
            )

            self.assertEqual(1, validation.returncode)
            self.assertIn(
                "release bundle artifact surfaces: sha256 does not match current bytes",
                validation.stderr,
            )

    def test_changed_release_evidence_bytes_make_current_bundle_stale(self) -> None:
        with _generated_repository() as root:
            revision = self.prepare_approved_release(root)
            self.assertEqual(0, self.run_bundle(root, revision).returncode)

            release_path = root / "contracts/release-evidence.json"
            release = _load_json(release_path)
            release["decision"]["description"] += " Retained wording changed."
            _write_json(release_path, release)

            validation = _run_generated_python(
                root,
                "-B",
                "scripts/validate_release_bundle.py",
                "--expected-revision",
                revision,
            )

            self.assertEqual(1, validation.returncode)
            self.assertIn(
                "release bundle artifact release_evidence: sha256 does not match current bytes",
                validation.stderr,
            )

    def test_bundle_rejects_a_different_candidate_revision(self) -> None:
        with _generated_repository() as root:
            revision = self.prepare_approved_release(root)
            self.assertEqual(0, self.run_bundle(root, revision).returncode)
            other_revision = "f" * 40
            self.assertNotEqual(revision, other_revision)

            validation = _run_generated_python(
                root,
                "-B",
                "scripts/validate_release_bundle.py",
                "--expected-revision",
                other_revision,
            )

            self.assertEqual(1, validation.returncode)
            self.assertIn(
                "revision does not match expected revision",
                validation.stderr,
            )

    def test_rejected_release_cannot_create_a_ready_bundle(self) -> None:
        with _generated_repository() as root:
            _install_release_evidence_producer(root)
            _install_release_bundle_producer(root)
            inventory_path = root / "product/conformance-targets.json"
            inventory = _load_json(inventory_path)
            first_target = next(iter(inventory["targets"].values()))
            first_target["positive"] = False
            _write_json(inventory_path, inventory)
            revision = _commit_generated_repository(root)

            release = _run_generated_python(
                root,
                "-I",
                "product/produce_release_evidence.py",
                "--revision",
                revision,
            )
            self.assertEqual(1, release.returncode)

            bundle_result = self.run_bundle(root, revision)

            self.assertEqual(2, bundle_result.returncode)
            self.assertIn(
                "approved release evidence is required",
                bundle_result.stderr,
            )
            self.assertEqual(
                "template",
                _load_json(root / "contracts/release-bundle.json")["mode"],
            )
            self.assertFalse(
                (root / "product/release-bundle-index.json").exists()
            )
            self.assertFalse(
                (root / "product/release-bundle-records").exists()
            )

    def test_retry_appends_a_distinct_record_and_supersedes_current(
        self,
    ) -> None:
        with _generated_repository() as root:
            revision = self.prepare_approved_release(root)
            first = self.run_bundle(root, revision)
            self.assertEqual(0, first.returncode, first.stderr)
            first_index = _load_json(
                root / "product/release-bundle-index.json"
            )
            first_id = first_index["currentRecordId"]
            first_path = (
                root / f"product/release-bundle-records/{first_id}.json"
            )
            first_bytes = first_path.read_bytes()

            second = self.run_bundle(root, revision)

            self.assertEqual(0, second.returncode, second.stderr)
            second_index = _load_json(
                root / "product/release-bundle-index.json"
            )
            second_id = second_index["currentRecordId"]
            self.assertNotEqual(first_id, second_id)
            self.assertEqual(first_bytes, first_path.read_bytes())

            records = {
                record["id"]: record for record in second_index["records"]
            }
            self.assertEqual("superseded", records[first_id]["status"])
            self.assertEqual(second_id, records[first_id]["supersededBy"])
            self.assertEqual("current", records[second_id]["status"])
            second_path = (
                root / f"product/release-bundle-records/{second_id}.json"
            )
            self.assertEqual(
                second_path.read_bytes(),
                (root / "contracts/release-bundle.json").read_bytes(),
            )
            self.assert_bundle_validates(root, revision)

    def test_exact_retained_bundle_can_be_reactivated_but_stale_one_cannot(
        self,
    ) -> None:
        with _generated_repository() as root:
            revision = self.prepare_approved_release(root)
            self.assertEqual(0, self.run_bundle(root, revision).returncode)
            first_index = _load_json(
                root / "product/release-bundle-index.json"
            )
            first_id = first_index["currentRecordId"]
            first_path = (
                root / f"product/release-bundle-records/{first_id}.json"
            )
            first_bytes = first_path.read_bytes()

            self.assertEqual(0, self.run_bundle(root, revision).returncode)
            second_index = _load_json(
                root / "product/release-bundle-index.json"
            )
            second_id = second_index["currentRecordId"]

            activation = self.run_bundle(
                root,
                revision,
                "--activate-record",
                first_id,
            )

            self.assertEqual(
                0,
                activation.returncode,
                f"stdout:\n{activation.stdout}\nstderr:\n{activation.stderr}",
            )
            activated_index = _load_json(
                root / "product/release-bundle-index.json"
            )
            self.assertEqual(first_id, activated_index["currentRecordId"])
            self.assertEqual(
                first_bytes,
                (root / "contracts/release-bundle.json").read_bytes(),
            )
            self.assert_bundle_validates(root, revision)

            release_path = root / "contracts/release-evidence.json"
            release = _load_json(release_path)
            release["decision"]["description"] += " Current policy bytes changed."
            _write_json(release_path, release)
            current_before = (
                root / "contracts/release-bundle.json"
            ).read_bytes()
            index_before = (
                root / "product/release-bundle-index.json"
            ).read_bytes()

            stale_activation = self.run_bundle(
                root,
                revision,
                "--activate-record",
                second_id,
            )

            self.assertEqual(2, stale_activation.returncode)
            self.assertIn(
                "retained release bundle is not accepted by current policy; new evidence is required",
                stale_activation.stderr,
            )
            self.assertEqual(
                current_before,
                (root / "contracts/release-bundle.json").read_bytes(),
            )
            self.assertEqual(
                index_before,
                (root / "product/release-bundle-index.json").read_bytes(),
            )


class GeneratedReleaseBundleProductionScopeTests(unittest.TestCase):
    def test_generated_bundle_production_suite_is_template_maintainer_only(
        self,
    ) -> None:
        source_is_template = _is_template_maintainer_source()
        suite_is_skipped = bool(
            getattr(
                GeneratedReleaseBundleProductionTests,
                "__unittest_skip__",
                False,
            )
        )
        self.assertEqual(not source_is_template, suite_is_skipped)
        if suite_is_skipped:
            self.assertEqual(
                "template-maintainer-only generated release bundle production suite",
                getattr(
                    GeneratedReleaseBundleProductionTests,
                    "__unittest_skip_why__",
                ),
            )


if __name__ == "__main__":
    unittest.main()
