import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/publication-reconcile.yml"
NORMALIZER = ROOT / "scripts/normalize_integration_site_dispatch.py"
EVENT_TYPE = "publication.integration-promoted"


def valid_event():
    return {
        "action": EVENT_TYPE,
        "client_payload": {
            "schema_version": 1,
            "boundary": "integration-to-site",
            "release": {
                "integration_revision": "a" * 40,
                "bundle": {
                    "schema": "4",
                    "identity": "b" * 64,
                    "content_digest": "c" * 64,
                    "artifact": {
                        "id": "11018626853",
                        "digest": "sha256:" + "d" * 64,
                        "name": "publication-bundle-v4",
                    },
                },
                "workflow": {
                    "run_id": "36536060040",
                    "attempt": "1",
                    "head": "e" * 40,
                    "name": "Notify Site after Integration adoption",
                    "event": "pull_request",
                },
                "qualification_artifact": {
                    "id": "11018217633",
                    "digest": "sha256:" + "f" * 64,
                    "name": "publication-qualification-v4",
                },
                "verified_receipt": {
                    "digest": "1" * 64,
                    "artifact": {
                        "id": "11019100564",
                        "digest": "sha256:" + "2" * 64,
                        "name": "publication-verification-v4",
                    },
                },
                "source_pr": "1099",
            },
        },
    }


class IntegrationPromotionEnvelopeTests(unittest.TestCase):
    def run_normalizer(self, event_name, event=None, manual=None):
        with tempfile.TemporaryDirectory() as directory:
            event_path = Path(directory) / "event.json"
            output_path = Path(directory) / "output.txt"
            event_path.write_text(json.dumps(event or {}), encoding="utf-8")
            environment = {
                **os.environ,
                "GITHUB_EVENT_NAME": event_name,
                "GITHUB_EVENT_PATH": str(event_path),
                "GITHUB_OUTPUT": str(output_path),
            }
            environment.update(manual or {})
            result = subprocess.run(
                [sys.executable, str(NORMALIZER)],
                capture_output=True,
                text=True,
                env=environment,
                check=False,
            )
            output = output_path.read_text(encoding="utf-8") if output_path.exists() else ""
            return result, output

    def test_workflow_consumes_only_the_versioned_nested_repository_event(self):
        workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
        events = workflow.get("on", workflow.get(True))
        self.assertEqual(
            events["repository_dispatch"]["types"],
            ["publication.integration-promoted"],
        )
        self.assertIn("workflow_dispatch", events)
        self.assertEqual(
            set(events["workflow_dispatch"]["inputs"]),
            {
                "integration_revision",
                "bundle_schema",
                "bundle_identity",
                "content_digest",
                "artifact_id",
                "run_id",
                "attempt",
                "artifact_name",
                "artifact_digest",
                "verified_receipt_artifact_id",
                "verified_receipt_artifact_digest",
                "verified_receipt_artifact_name",
                "verified_receipt_digest",
                "workflow_head",
                "workflow_name",
                "workflow_event",
            },
        )

        classify = workflow["jobs"]["classify"]
        steps = classify["steps"]
        normalizer = next(
            step for step in steps
            if step.get("name") == "Validate and normalize the Integration promotion event"
        )
        self.assertEqual(normalizer["id"], "handoff")
        self.assertEqual(normalizer["run"], "python3 scripts/normalize_integration_site_dispatch.py")
        self.assertLess(
            next(index for index, step in enumerate(steps) if step is normalizer),
            next(
                index for index, step in enumerate(steps)
                if step.get("name") == "Bind the exact dispatch identities"
            ),
        )

        workflow_text = WORKFLOW.read_text(encoding="utf-8")
        self.assertNotIn("github.event.client_payload.", workflow_text)
        self.assertIn("steps.handoff.outputs.integration_revision", workflow_text)
        self.assertIn("steps.handoff.outputs.verified_receipt_artifact_id", workflow_text)
        for output in ("integration_revision", "bundle_schema", "bundle_identity", "content_digest"):
            self.assertEqual(
                classify["outputs"][output],
                f"${{{{ steps.handoff.outputs.{output} }}}}",
            )

        receipt = next(
            step for step in steps
            if step.get("name") == "Acquire the trusted Integration promotion receipt"
        )
        self.assertEqual(
            receipt["env"]["QUALIFICATION_ARTIFACT_ID"],
            "${{ steps.handoff.outputs.qualification_artifact_id }}",
        )
        self.assertEqual(
            receipt["env"]["QUALIFICATION_ARTIFACT_DIGEST"],
            "${{ steps.handoff.outputs.qualification_artifact_digest }}",
        )
        self.assertEqual(
            receipt["env"]["QUALIFICATION_ARTIFACT_NAME"],
            "${{ steps.handoff.outputs.qualification_artifact_name }}",
        )
        self.assertEqual(receipt["env"]["SOURCE_PR"], "${{ steps.handoff.outputs.source_pr }}")
        self.assertIn('if [ "$GITHUB_EVENT_NAME" = repository_dispatch ]', receipt["run"])
        self.assertIn("--require-dispatch-provenance", receipt["run"])
        self.assertIn('--source-pr "$SOURCE_PR"', receipt["run"])
        self.assertIn('--qualification-artifact-id "$QUALIFICATION_ARTIFACT_ID"', receipt["run"])
        self.assertLess(
            next(index for index, step in enumerate(steps) if step is receipt),
            next(
                index for index, step in enumerate(steps)
                if step.get("name") == "Acquire the exact qualified Integration Bundle"
            ),
        )
        workflow_text = WORKFLOW.read_text(encoding="utf-8")
        self.assertNotRegex(workflow_text, r"(?m)^\s*gh\s+pr\s+merge(?:\s|$)")
        self.assertNotRegex(workflow_text, r"(?m)^\s*gh\s+pr\s+auto-merge(?:\s|$)")
        for deploy_marker in ("deploy-pages", "upload-pages-artifact", "pages: write"):
            with self.subTest(deploy_marker=deploy_marker):
                self.assertNotIn(deploy_marker, workflow_text)

    def test_valid_envelope_preserves_and_normalizes_all_handoff_identities(self):
        result, output = self.run_normalizer("repository_dispatch", valid_event())
        self.assertEqual(result.returncode, 0, result.stderr)
        normalized = dict(line.split("=", 1) for line in output.splitlines())
        self.assertEqual(normalized["integration_revision"], "a" * 40)
        self.assertEqual(normalized["bundle_schema"], "4")
        self.assertEqual(normalized["bundle_identity"], "b" * 64)
        self.assertEqual(normalized["content_digest"], "c" * 64)
        self.assertEqual(normalized["artifact_id"], "11018626853")
        self.assertEqual(normalized["artifact_digest"], "sha256:" + "d" * 64)
        self.assertEqual(normalized["run_id"], "36536060040")
        self.assertEqual(normalized["attempt"], "1")
        self.assertEqual(normalized["workflow_head"], "e" * 40)
        self.assertEqual(normalized["qualification_artifact_id"], "11018217633")
        self.assertEqual(normalized["qualification_artifact_digest"], "sha256:" + "f" * 64)
        self.assertEqual(normalized["qualification_artifact_name"], "publication-qualification-v4")
        self.assertEqual(normalized["verified_receipt_digest"], "1" * 64)
        self.assertEqual(normalized["verified_receipt_artifact_id"], "11019100564")
        self.assertEqual(normalized["verified_receipt_artifact_digest"], "sha256:" + "2" * 64)
        self.assertEqual(normalized["verified_receipt_artifact_name"], "publication-verification-v4")
        self.assertEqual(normalized["source_pr"], "1099")
        self.assertEqual(
            set(normalized),
            {
                "integration_revision", "bundle_schema", "bundle_identity", "content_digest",
                "artifact_id", "artifact_digest", "artifact_name", "run_id", "attempt",
                "workflow_head", "workflow_name", "workflow_event", "qualification_artifact_id",
                "qualification_artifact_digest", "qualification_artifact_name",
                "verified_receipt_digest", "verified_receipt_artifact_id",
                "verified_receipt_artifact_digest", "verified_receipt_artifact_name", "source_pr",
            },
        )

    def test_malformed_or_legacy_flat_repository_payload_fails_closed(self):
        mutations = (
            lambda event: event["client_payload"].pop("release"),
            lambda event: event["client_payload"].update(extra="unexpected"),
            lambda event: event["client_payload"].update(schema_version=2),
            lambda event: event["client_payload"]["release"].pop("verified_receipt"),
            lambda event: event["client_payload"]["release"].update(integration_revision="A" * 40),
            lambda event: event["client_payload"]["release"]["bundle"]["artifact"].update(digest="sha256:bad"),
            lambda event: event.update(client_payload={"boundary": "integration-to-site", "integration_revision": "a" * 40}),
            lambda event: event.update(action="publication.reconcile"),
        )
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                event = copy.deepcopy(valid_event())
                mutate(event)
                result, output = self.run_normalizer(
                    "repository_dispatch",
                    event,
                    {"MANUAL_INTEGRATION_REVISION": "a" * 40},
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(output, "")

    def test_manual_workflow_dispatch_keeps_the_existing_flat_inputs(self):
        manual = {
            "MANUAL_INTEGRATION_REVISION": "a" * 40,
            "MANUAL_BUNDLE_SCHEMA": "4",
            "MANUAL_BUNDLE_IDENTITY": "b" * 64,
            "MANUAL_CONTENT_DIGEST": "c" * 64,
            "MANUAL_ARTIFACT_ID": "",
            "MANUAL_ARTIFACT_DIGEST": "",
            "MANUAL_ARTIFACT_NAME": "",
            "MANUAL_RUN_ID": "",
            "MANUAL_ATTEMPT": "",
            "MANUAL_WORKFLOW_HEAD": "",
            "MANUAL_WORKFLOW_NAME": "",
            "MANUAL_WORKFLOW_EVENT": "",
            "MANUAL_VERIFIED_RECEIPT_ARTIFACT_ID": "",
            "MANUAL_VERIFIED_RECEIPT_ARTIFACT_DIGEST": "",
            "MANUAL_VERIFIED_RECEIPT_ARTIFACT_NAME": "",
            "MANUAL_VERIFIED_RECEIPT_DIGEST": "",
        }
        result, output = self.run_normalizer("workflow_dispatch", {"inputs": {}}, manual)
        self.assertEqual(result.returncode, 0, result.stderr)
        normalized = dict(line.split("=", 1) for line in output.splitlines())
        self.assertEqual(normalized["integration_revision"], "a" * 40)
        self.assertEqual(normalized["bundle_schema"], "4")
        self.assertEqual(normalized["bundle_identity"], "b" * 64)
        self.assertEqual(normalized["content_digest"], "c" * 64)
        self.assertEqual(normalized["artifact_id"], "")
        self.assertEqual(normalized["verified_receipt_artifact_id"], "")
        self.assertEqual(normalized["source_pr"], "")


if __name__ == "__main__":
    unittest.main()
