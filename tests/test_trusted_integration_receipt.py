import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from io import BytesIO
import zipfile

from scripts.acquire_trusted_integration_receipt import ReceiptError, _validate_report, acquire


class TrustedIntegrationReceiptTests(unittest.TestCase):
    def report(self):
        bundle_identity = "a" * 64
        bundle_digest = "b" * 64
        workflow_name = "Notify Site after Integration adoption"
        return {
            "schema_version": 1,
            "boundary": "provider-to-integration",
            "stage": "qualification",
            "classification": "NOT_ELIGIBLE",
            "reason_codes": ["QUALIFICATION_PASSED", "TRUSTED_BUNDLE_EQUIVALENT", "AUTHORIZATION_NOT_GRANTED"],
            "affected_authorities": [],
            "inputs": {
                "integration_revision": "c" * 40,
                "bundle_identity": bundle_identity,
                "bundle_content_digest": bundle_digest,
            },
            "trusted": {"policy_revision": "d" * 40, "controller_revision": "e" * 40},
            "requirements": {"required": [], "supported": [], "missing": [], "unsupported": [], "fallbacks": {}},
            "checks": {"required": [], "results": {}, "not_run": []},
            "evidence_refs": [
                f"workflow://{workflow_name}#3/1",
                f"bundle://{bundle_identity}",
                f"trusted-bundle-equivalence://{bundle_identity}",
            ],
            "allowed_mutations": [],
            "next_action": "verify activation",
            "idempotency_key": "f" * 64,
            "verification": {
                "schema_version": 1,
                "verifier_revision": "e" * 40,
                "source_report_digest": "1" * 64,
                "workflow_run_id": 3,
                "workflow_attempt": 1,
                "workflow_head": "2" * 40,
                "workflow_name": workflow_name,
                "workflow_event": "pull_request",
                "workflow_path": ".github/workflows/integration-promotion-notify.yml",
                "artifact_id": 2,
                "artifact_digest": "sha256:" + "3" * 64,
                "artifact_name": f"publication-bundle-{bundle_identity}-1-promoted",
                "bundle_identity": bundle_identity,
                "bundle_content_digest": bundle_digest,
                "trusted_checks": {
                    "report-shape": "passed",
                    "bundle-contract": "passed",
                    "bundle-equivalence": "passed",
                    "provider-declarations": "passed",
                    "identity-binding": "passed",
                },
            },
        }

    def kwargs(self):
        identity = "a" * 64
        return {
            "receipt_artifact_id": 1,
            "receipt_artifact_digest": "sha256:" + "4" * 64,
            "receipt_artifact_name": f"publication-verification-{identity}-1-promoted",
            "bundle_artifact_id": 2,
            "bundle_artifact_digest": "sha256:" + "3" * 64,
            "bundle_artifact_name": f"publication-bundle-{identity}-1-promoted",
            "run_id": 3,
            "attempt": 1,
            "workflow_head": "2" * 40,
            "workflow_name": "Notify Site after Integration adoption",
            "workflow_event": "pull_request",
            "workflow_path": ".github/workflows/integration-promotion-notify.yml",
            "bundle_identity": identity,
            "bundle_content_digest": "b" * 64,
            "integration_revision": "c" * 40,
            "expected_policy_revision": None,
            "expected_controller_revision": "e" * 40,
        }

    def test_exact_receipt_is_accepted(self):
        _validate_report(self.report(), **self.kwargs())

    def test_bundle_artifact_substitution_is_rejected(self):
        report = self.report()
        report["verification"]["artifact_id"] = 99
        with self.assertRaises(ReceiptError):
            _validate_report(report, **self.kwargs())

    @staticmethod
    def zip_bytes(*members):
        archive = BytesIO()
        with zipfile.ZipFile(archive, "w") as zipped:
            for name, payload in members:
                zipped.writestr(name, payload)
        return archive.getvalue()

    def dispatch_fixture(self):
        report = self.report()
        source_report = b'{"boundary":"provider-to-integration","result":"qualified"}\n'
        report["verification"]["source_report_digest"] = hashlib.sha256(source_report).hexdigest()
        identity = "a" * 64
        receipt_zip = self.zip_bytes(
            ("verified-report.json", json.dumps(report, sort_keys=True).encode())
        )
        qualification_zip = self.zip_bytes(("compatibility-report.json", source_report))
        receipt_digest = "sha256:" + hashlib.sha256(receipt_zip).hexdigest()
        qualification_digest = "sha256:" + hashlib.sha256(qualification_zip).hexdigest()
        qualification_name = f"publication-compatibility-{identity}-1-promoted"
        pr = {
            "number": 1099,
            "state": "closed",
            "merged": True,
            "merged_at": "2026-09-29T00:00:00Z",
            "merge_commit_sha": "c" * 40,
            "base": {"ref": "integration", "repo": {"full_name": "TakashiSasaki/templates"}},
            "head": {
                "ref": "automation/publication-" + "f" * 64,
                "sha": "2" * 40,
                "repo": {"full_name": "TakashiSasaki/templates"},
            },
        }
        metadata = {
            "id": 5,
            "digest": qualification_digest,
            "name": qualification_name,
            "expired": False,
            "workflow_run": {"id": 3, "head_sha": "2" * 40},
        }
        run = {
            "id": 3,
            "run_attempt": 1,
            "head_sha": "2" * 40,
            "head_repository": {"full_name": "TakashiSasaki/templates"},
            "name": "Notify Site after Integration adoption",
            "event": "pull_request",
            "path": ".github/workflows/integration-promotion-notify.yml",
            "status": "completed",
            "conclusion": "success",
        }
        receipt_identity = report["verification"]["bundle_identity"]
        receipt_name = f"publication-verification-{receipt_identity}-1-promoted"
        api_values = {
            "repos/TakashiSasaki/templates/actions/artifacts/1": {
                "id": 1,
                "digest": receipt_digest,
                "name": receipt_name,
                "expired": False,
                "workflow_run": {"id": 3, "head_sha": "2" * 40},
            },
            "repos/TakashiSasaki/templates/actions/runs/3/attempts/1": run,
            "repos/TakashiSasaki/templates/pulls/1099": pr,
            "repos/TakashiSasaki/templates/actions/artifacts/5": metadata,
        }
        archives = {1: receipt_zip, 5: qualification_zip}
        args = self.kwargs()
        args.update(
            receipt_artifact_digest=receipt_digest,
            receipt_artifact_name=receipt_name,
            source_pr=1099,
            qualification_artifact_id=5,
            qualification_artifact_digest=qualification_digest,
            qualification_artifact_name=qualification_name,
        )
        return report, source_report, pr, metadata, api_values, archives, args

    def run_dispatch_acquisition(self, mutate=None, *, qualification_archive=None):
        _, _, pr, metadata, api_values, archives, args = self.dispatch_fixture()
        if mutate:
            mutate(pr, metadata, args)
        if qualification_archive is not None:
            archives[5] = qualification_archive
        def api_call(path):
            return api_values[path]
        def download(repository, artifact_id, output):
            output.write_bytes(archives[artifact_id])
        with tempfile.TemporaryDirectory() as directory:
            args["output"] = Path(directory) / "trusted-receipt.json"
            return acquire(
                repository="TakashiSasaki/templates",
                require_dispatch_provenance=True,
                api_call=api_call,
                archive_download=download,
                **args,
            )

    def test_exact_source_pr_and_qualification_report_are_bound_to_receipt(self):
        self.run_dispatch_acquisition()

    def test_wrong_source_pr_number_is_rejected(self):
        def mutate(pr, metadata, args):
            pr["number"] = 1098
        with self.assertRaisesRegex(ReceiptError, "exact merged pull request"):
            self.run_dispatch_acquisition(mutate)

    def test_source_pr_wrong_head_is_rejected(self):
        def mutate(pr, metadata, args):
            pr["head"]["sha"] = "9" * 40
        with self.assertRaisesRegex(ReceiptError, "does not identify"):
            self.run_dispatch_acquisition(mutate)

    def test_source_pr_wrong_merge_commit_is_rejected(self):
        def mutate(pr, metadata, args):
            pr["merge_commit_sha"] = "9" * 40
        with self.assertRaisesRegex(ReceiptError, "does not identify"):
            self.run_dispatch_acquisition(mutate)

    def test_source_pr_from_another_repository_is_rejected(self):
        def mutate(pr, metadata, args):
            pr["head"]["repo"]["full_name"] = "attacker/fork"
        with self.assertRaisesRegex(ReceiptError, "same repository"):
            self.run_dispatch_acquisition(mutate)

    def test_qualification_artifact_from_another_run_is_rejected(self):
        def mutate(pr, metadata, args):
            metadata["workflow_run"]["id"] = 4
        with self.assertRaisesRegex(ReceiptError, "metadata binding"):
            self.run_dispatch_acquisition(mutate)

    def test_expired_qualification_artifact_is_rejected(self):
        def mutate(pr, metadata, args):
            metadata["expired"] = True
        with self.assertRaisesRegex(ReceiptError, "metadata binding"):
            self.run_dispatch_acquisition(mutate)

    def test_wrong_qualification_artifact_name_is_rejected(self):
        def mutate(pr, metadata, args):
            metadata["name"] = "publication-compatibility-substituted-1-promoted"
            args["qualification_artifact_name"] = metadata["name"]
        with self.assertRaisesRegex(ReceiptError, "metadata binding"):
            self.run_dispatch_acquisition(mutate)

    def test_wrong_qualification_artifact_digest_is_rejected(self):
        def mutate(pr, metadata, args):
            args["qualification_artifact_digest"] = "sha256:" + "9" * 64
        with self.assertRaisesRegex(ReceiptError, "metadata binding"):
            self.run_dispatch_acquisition(mutate)

    def test_wrong_downloaded_qualification_archive_digest_is_rejected(self):
        _, _, _, _, _, archives, _ = self.dispatch_fixture()
        with self.assertRaisesRegex(ReceiptError, "qualification artifact digest"):
            self.run_dispatch_acquisition(qualification_archive=archives[5] + b"tamper")

    def test_non_exact_qualification_archive_inventory_is_rejected(self):
        _, _, _, metadata, _, _, _ = self.dispatch_fixture()
        source = b'{"result":"qualified"}\n'
        archive = self.zip_bytes(("compatibility-report.json", source), ("extra.json", b"{}"))
        digest = "sha256:" + hashlib.sha256(archive).hexdigest()
        def mutate(pr, actual_metadata, args):
            actual_metadata["digest"] = digest
            args["qualification_artifact_digest"] = digest
        with self.assertRaisesRegex(ReceiptError, "inventory is not exact"):
            self.run_dispatch_acquisition(mutate, qualification_archive=archive)

    def test_report_bytes_must_match_trusted_receipt_digest(self):
        _, _, _, _, _, archives, _ = self.dispatch_fixture()
        source = b'{"result":"different"}\n'
        archive = self.zip_bytes(("compatibility-report.json", source))
        digest = "sha256:" + hashlib.sha256(archive).hexdigest()
        def mutate(pr, metadata, args):
            metadata["digest"] = digest
            args["qualification_artifact_digest"] = digest
        with self.assertRaisesRegex(ReceiptError, "source_report_digest"):
            self.run_dispatch_acquisition(mutate, qualification_archive=archive)


if __name__ == "__main__":
    unittest.main()
