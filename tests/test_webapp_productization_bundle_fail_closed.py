from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import test_webapp_productization_acceptance as productization_acceptance


class WebappProductizationBundleFailClosedTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = productization_acceptance.WebappProductizationAcceptanceTests(
            methodName="runTest"
        )

    def test_bundle_revision_and_artifact_digest_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target, revision = self.fixture.create_product_candidate(Path(temp_dir))

            mismatch = self.fixture.run_target(
                target,
                ".template-composition/validators/validate_release_bundle.py",
                ".",
                "--expected-revision",
                "f" * 40,
            )
            self.assertNotEqual(mismatch.returncode, 0)
            self.assertIn(
                "bundle subject does not match expected revision",
                mismatch.stderr,
            )

            routes_path = target / "contracts/routes.json"
            original_routes = routes_path.read_bytes()
            routes_path.write_bytes(original_routes + b"\n")
            drift = self.fixture.run_target(
                target,
                ".template-composition/validators/validate_release_bundle.py",
                ".",
                "--expected-revision",
                revision,
            )
            self.assertNotEqual(drift.returncode, 0)
            self.assertIn(
                "bundle artifact routes: sha256 does not match current bytes",
                drift.stderr,
            )

            routes_path.write_bytes(original_routes)
            self.fixture.assert_validator_passes(
                target,
                ".template-composition/validators/validate_release_bundle.py",
                ".",
                "--expected-revision",
                revision,
            )


if __name__ == "__main__":
    unittest.main()
