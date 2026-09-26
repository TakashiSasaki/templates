import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from scripts.publication_promotion_intent import build_intent, verify_merged_intent, verify_premerge_intent
from scripts.resolve_publication_sources import render_source_lock


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _idempotency_key(inputs: dict, trusted: dict) -> str:
    return _digest(json.dumps({
        "boundary": "provider-to-integration",
        "stage": "qualification",
        "inputs": inputs,
        "trusted": trusted,
    }, sort_keys=True, separators=(",", ":")).encode())


CONTROLLER = "f" * 40
POLICY = "1" * 40
COMPOSITION = "2" * 40
MODELING = "3" * 40
PROVIDER_POLICY = "4" * 40
BUNDLE_IDENTITY = "5" * 64
BUNDLE_CONTENT = "6" * 64
QUALIFICATION_INPUTS = {
    "integration_revision": "a" * 40,
    "bundle_schema": "4",
    "bundle_identity": BUNDLE_IDENTITY,
    "bundle_content_digest": BUNDLE_CONTENT,
    "composition_revision": COMPOSITION,
    "modeling_revision": MODELING,
    "policy_revision": PROVIDER_POLICY,
}
IDEMPOTENCY = _idempotency_key(
    QUALIFICATION_INPUTS,
    {"controller_revision": CONTROLLER, "policy_revision": POLICY},
)
def _write_json(path: Path, value: dict) -> bytes:
    encoded = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    path.write_bytes(encoded)
    return encoded


class PublicationPromotionIntentTests(unittest.TestCase):
    def _fixture(self, root: Path, producer: str):
        lock_bytes = render_source_lock({
            "modeling": MODELING,
            "composition": COMPOSITION,
            "policy": PROVIDER_POLICY,
        })
        current = root / "current-lock.json"
        candidate = root / "candidate-lock.json"
        current.write_bytes(lock_bytes)
        candidate.write_bytes(lock_bytes)
        source = {
            "schema_version": 1,
            "boundary": "provider-to-integration",
            "stage": "qualification",
            "classification": "NOT_ELIGIBLE",
            "inputs": {
                "integration_revision": producer,
                "modeling_revision": MODELING,
                "composition_revision": COMPOSITION,
                "policy_revision": PROVIDER_POLICY,
                "bundle_schema": "4",
                "bundle_identity": BUNDLE_IDENTITY,
                "bundle_content_digest": BUNDLE_CONTENT,
            },
            "trusted": {
                "controller_revision": CONTROLLER,
                "policy_revision": POLICY,
            },
            "checks": {"required": ["producer"], "results": {"producer": "passed"}},
            "evidence_refs": ["workflow://reconciliation"],
        }
        source["idempotency_key"] = _idempotency_key(source["inputs"], source["trusted"])
        source_path = root / "source-report.json"
        source_bytes = _write_json(source_path, source)
        verified = copy.deepcopy(source)
        verified["verification"] = {
            "schema_version": 1,
            "verifier_revision": CONTROLLER,
            "source_report_digest": _digest(source_bytes),
            "workflow_run_id": 100,
            "workflow_attempt": 1,
            "workflow_head": producer,
            "workflow_name": "Reconcile Integration publication candidate",
            "workflow_event": "workflow_dispatch",
            "workflow_path": ".github/workflows/integration-reconcile.yml",
            "artifact_id": 101,
            "artifact_digest": "sha256:" + "8" * 64,
            "artifact_name": f"publication-bundle-{BUNDLE_IDENTITY}-1-reconciliation",
            "bundle_identity": BUNDLE_IDENTITY,
            "bundle_content_digest": BUNDLE_CONTENT,
            "trusted_checks": {
                "report-shape": "passed",
                "bundle-contract": "passed",
                "bundle-equivalence": "passed",
                "provider-declarations": "passed",
                "identity-binding": "passed",
            },
        }
        verified_path = root / "verified-report.json"
        _write_json(verified_path, verified)
        reconciliation = {
            "schema_version": 1,
            "boundary": "provider-to-integration",
            "stage": "authorization",
            "classification": "AUTO_PROCESSABLE",
            "idempotency_key": source["idempotency_key"],
            "inputs": source["inputs"],
            "trusted": source["trusted"],
            "allowed_mutations": ["publication-promotion-intent.json"],
        }
        reconciliation_path = root / "reconciliation-report.json"
        _write_json(reconciliation_path, reconciliation)
        return current, candidate, source_path, verified_path, reconciliation_path

    def _build(self, root: Path, producer: str):
        current, candidate, source, verified, reconciliation = self._fixture(root, producer)
        intent = build_intent(
            current=current,
            candidate=candidate,
            source_report=source,
            verified_report=verified,
            reconciliation_report=reconciliation,
            producer_revision=producer,
            consumer_base_revision=producer,
            expected_current_lock_digest=_digest(current.read_bytes()),
            qualification_artifact={
                "id": 102,
                "digest": "sha256:" + "9" * 64,
                "name": f"publication-compatibility-{BUNDLE_IDENTITY}-1-reconciliation",
            },
            trusted_controller_revision=CONTROLLER,
            trusted_policy_revision=POLICY,
        )
        return current, candidate, intent

    def test_current_lock_produces_a_bound_marker_only_intent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            producer = "a" * 40
            current, candidate, intent = self._build(root, producer)
            self.assertFalse(intent["lock_update_required"])
            self.assertEqual(intent["base_lock_digest"], intent["selected_lock_digest"])
            self.assertEqual(intent["provider_tuple"], {
                "composition": COMPOSITION,
                "modeling": MODELING,
                "policy": PROVIDER_POLICY,
            })

            intent_path = root / "publication-promotion-intent.json"
            intent_bytes = _write_json(intent_path, intent)
            verified = verify_premerge_intent(
                intent_path=intent_path,
                base_lock=current,
                selected_lock=candidate,
                consumer_base_revision=producer,
                trusted_controller_revision=CONTROLLER,
                trusted_policy_revision=POLICY,
                branch=f"automation/publication-{IDEMPOTENCY}",
                expected_intent_digest=_digest(intent_bytes),
            )
            self.assertEqual(verified["idempotency_key"], IDEMPOTENCY)

            with self.assertRaisesRegex(ValueError, "branch does not match"):
                verify_premerge_intent(
                    intent_path=intent_path,
                    base_lock=current,
                    selected_lock=candidate,
                    consumer_base_revision=producer,
                    trusted_controller_revision=CONTROLLER,
                    trusted_policy_revision=POLICY,
                    branch="automation/publication-" + "0" * 64,
                )

            intent["idempotency_key"] = "0" * 64
            _write_json(intent_path, intent)
            with self.assertRaisesRegex(ValueError, "idempotency key does not bind"):
                verify_premerge_intent(
                    intent_path=intent_path,
                    base_lock=current,
                    selected_lock=candidate,
                    consumer_base_revision=producer,
                    trusted_controller_revision=CONTROLLER,
                    trusted_policy_revision=POLICY,
                    branch=f"automation/publication-{'0' * 64}",
                )

            intent["idempotency_key"] = IDEMPOTENCY
            _write_json(intent_path, intent)
            candidate.write_bytes(render_source_lock({
                "modeling": "a" * 40,
                "composition": COMPOSITION,
                "policy": PROVIDER_POLICY,
            }))
            with self.assertRaisesRegex(ValueError, "selected lock digest is stale"):
                verify_premerge_intent(
                    intent_path=intent_path,
                    base_lock=current,
                    selected_lock=candidate,
                    consumer_base_revision=producer,
                    trusted_controller_revision=CONTROLLER,
                    trusted_policy_revision=POLICY,
                    branch=f"automation/publication-{IDEMPOTENCY}",
                )

    def test_merged_marker_requires_exact_base_lock_and_trust_pins(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            root.mkdir()
            subprocess.run(["git", "init", "-b", "integration", str(root)], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.invalid"], check=True)
            (root / "publication-sources.json").write_bytes(render_source_lock({
                "modeling": MODELING,
                "composition": COMPOSITION,
                "policy": PROVIDER_POLICY,
            }))
            subprocess.run(["git", "-C", str(root), "add", "publication-sources.json"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-m", "base"], check=True, capture_output=True)
            base = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
            current, candidate, intent = self._build(Path(directory), base)
            intent_path = root / "publication-promotion-intent.json"
            intent_path.write_bytes((json.dumps(intent, indent=2, sort_keys=True) + "\n").encode())
            branch = f"automation/publication-{intent['idempotency_key']}"
            subprocess.run(["git", "-C", str(root), "switch", "-c", branch], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(root), "add", "publication-promotion-intent.json"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-m", "intent"], check=True, capture_output=True)
            intent_commit = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
            tree = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD^{tree}"], text=True).strip()
            merge = subprocess.check_output(
                ["git", "-C", str(root), "commit-tree", tree, "-p", base, "-p", intent_commit, "-m", "merge"],
                text=True,
            ).strip()
            subprocess.run(["git", "-C", str(root), "update-ref", "refs/heads/integration", merge], check=True)
            subprocess.run(["git", "-C", str(root), "checkout", "--detach", merge], check=True, capture_output=True)

            result = verify_merged_intent(
                repository_root=root,
                merged_revision=merge,
                intent_path=intent_path,
                trusted_controller_revision=CONTROLLER,
                trusted_policy_revision=POLICY,
                branch=branch,
            )
            self.assertEqual(result["source_integration_revision"], base)

            intent["source_integration_revision"] = "a" * 40
            intent["consumer_base_revision"] = "a" * 40
            intent["qualification_inputs"]["integration_revision"] = "a" * 40
            intent["idempotency_key"] = _idempotency_key(intent["qualification_inputs"], intent["trusted"])
            branch = f"automation/publication-{intent['idempotency_key']}"
            intent_path.write_bytes((json.dumps(intent, indent=2, sort_keys=True) + "\n").encode())
            with self.assertRaisesRegex(ValueError, "first parent"):
                verify_merged_intent(
                    repository_root=root,
                    merged_revision=merge,
                    intent_path=intent_path,
                    trusted_controller_revision=CONTROLLER,
                    trusted_policy_revision=POLICY,
                    branch=branch,
                )

            intent["source_integration_revision"] = base
            intent["consumer_base_revision"] = base
            intent["qualification_inputs"]["integration_revision"] = base
            intent["idempotency_key"] = _idempotency_key(intent["qualification_inputs"], intent["trusted"])
            branch = f"automation/publication-{intent['idempotency_key']}"
            intent_path.write_bytes((json.dumps(intent, indent=2, sort_keys=True) + "\n").encode())
            with self.assertRaisesRegex(ValueError, "trust pins"):
                verify_merged_intent(
                    repository_root=root,
                    merged_revision=merge,
                    intent_path=intent_path,
                    trusted_controller_revision=CONTROLLER,
                    trusted_policy_revision="a" * 40,
                    branch=branch,
                )


if __name__ == "__main__":
    unittest.main()
