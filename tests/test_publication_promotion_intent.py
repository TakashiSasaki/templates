import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from scripts.publication_promotion_intent import (
    build_intent,
    verify_existing_promotion_pr,
    verify_live_consumer_base,
    verify_merged_intent,
    verify_merged_pr_intent,
    verify_merged_pr_provenance,
    verify_premerge_intent,
    verify_target_intent,
)
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
REPOSITORY = "TakashiSasaki/templates"
RECONCILIATION_PATH = ".github/workflows/integration-reconcile.yml"
SITE_DISPATCH_PATH = ".github/workflows/provider-publication-dispatch.yml"
SITE_HEAD = "3e4c9a0cbbde2e6fa2e83d53e34614e44b060b60"
SITE_RECONCILIATION_SHA = "5aaf7409299cae00a33cab740f8755ff91f353ed"
OBSERVED_PRODUCER = "9831ddcb90a98a727401303bf5e5d391fb2d2f01"
OBSERVED_POLICY_PIN = "aa6f9ac4822cbbb9b7bb6940525d54ad690d76d3"
OBSERVED_COMPOSITION = "d4d0e35485ea0c2030e902f462374f6fb8f8588a"
OBSERVED_MODELING = "202afe0206d673b2e2195a2df271d76862f9323a"
OBSERVED_BUNDLE_IDENTITY = "169ac2c58e6b49788ac3a79903e9002c639d22ee2fa12d6c3bc349db99d59dc8"
OBSERVED_BUNDLE_CONTENT = "278b359096053a670a74a39cebf1efe285c99602bee4df08322ef0ae4d46d441"
OBSERVED_BUNDLE_ARTIFACT = {
    "id": 10932459512,
    "digest": "sha256:9032520e6c481b95fab06bd8fb07fcd996a5bdd1180b15743add2760d5fd4d2c",
    "name": f"publication-bundle-{OBSERVED_BUNDLE_IDENTITY}-1-reconciliation",
}
OBSERVED_QUALIFICATION_ARTIFACT = {
    "id": 10932866361,
    "digest": "sha256:64d4ea1b2eda1618b578810dbd5a1fb0015fe19d4e969896b51ddf12f1bd103a",
    "name": f"publication-compatibility-{OBSERVED_BUNDLE_IDENTITY}-1-reconciliation",
}


def _direct_run_context(producer: str, *, event: str = "workflow_dispatch") -> dict:
    return {
        "repository": REPOSITORY,
        "workflow_run_id": 100,
        "workflow_attempt": 1,
        "workflow_head": producer,
        "workflow_name": "Reconcile Integration publication candidate",
        "workflow_event": event,
        "run_workflow_path": RECONCILIATION_PATH,
    }


def _direct_reconciliation_implementation(producer: str) -> dict:
    return {
        "workflow_repository": REPOSITORY,
        "workflow_file_path": RECONCILIATION_PATH,
        "workflow_ref": f"{REPOSITORY}/{RECONCILIATION_PATH}@refs/heads/integration",
        "workflow_sha": producer,
    }


def _observed_site_run_context() -> dict:
    return {
        "repository": REPOSITORY,
        "workflow_run_id": 36322246692,
        "workflow_attempt": 1,
        "workflow_head": SITE_HEAD,
        "workflow_name": "Dispatch provider qualification to Integration",
        "workflow_event": "workflow_dispatch",
        "run_workflow_path": SITE_DISPATCH_PATH,
    }


def _observed_reconciliation_implementation() -> dict:
    workflow_ref = (
        f"{REPOSITORY}/{RECONCILIATION_PATH}@{SITE_RECONCILIATION_SHA}"
    )
    return {
        "workflow_repository": REPOSITORY,
        "workflow_file_path": RECONCILIATION_PATH,
        "workflow_ref": workflow_ref,
        "workflow_sha": SITE_RECONCILIATION_SHA,
    }


def _write_json(path: Path, value: dict) -> bytes:
    encoded = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    path.write_bytes(encoded)
    return encoded


class PublicationPromotionIntentTests(unittest.TestCase):
    def _fixture(
        self,
        root: Path,
        producer: str,
        *,
        run_context: dict | None = None,
        providers: dict | None = None,
        trusted_controller: str = CONTROLLER,
        trusted_policy: str = POLICY,
        bundle_identity: str = BUNDLE_IDENTITY,
        bundle_content: str = BUNDLE_CONTENT,
        bundle_artifact: dict | None = None,
        report_input_changes: dict | None = None,
        report_trust_changes: dict | None = None,
        verified_input_changes: dict | None = None,
        verification_changes: dict | None = None,
    ):
        run_context = run_context or _direct_run_context(producer)
        providers = providers or {
            "modeling": MODELING,
            "composition": COMPOSITION,
            "policy": PROVIDER_POLICY,
        }
        lock_bytes = render_source_lock(providers)
        current = root / "current-lock.json"
        candidate = root / "candidate-lock.json"
        current.write_bytes(lock_bytes)
        candidate.write_bytes(lock_bytes)
        bundle_artifact = bundle_artifact or {
            "id": 101,
            "digest": "sha256:" + "8" * 64,
            "name": f"publication-bundle-{bundle_identity}-{run_context['workflow_attempt']}-reconciliation",
        }
        source = {
            "schema_version": 1,
            "boundary": "provider-to-integration",
            "stage": "qualification",
            "classification": "NOT_ELIGIBLE",
            "inputs": {
                "integration_revision": producer,
                "modeling_revision": providers["modeling"],
                "composition_revision": providers["composition"],
                "policy_revision": providers["policy"],
                "bundle_schema": "4",
                "bundle_identity": bundle_identity,
                "bundle_content_digest": bundle_content,
            },
            "trusted": {
                "controller_revision": trusted_controller,
                "policy_revision": trusted_policy,
            },
            "checks": {"required": ["producer"], "results": {"producer": "passed"}},
            "evidence_refs": ["workflow://reconciliation"],
        }
        source["inputs"].update(report_input_changes or {})
        source["trusted"].update(report_trust_changes or {})
        source["idempotency_key"] = _idempotency_key(source["inputs"], source["trusted"])
        source_path = root / "source-report.json"
        source_bytes = _write_json(source_path, source)
        verified = copy.deepcopy(source)
        verified["inputs"].update(verified_input_changes or {})
        verified["verification"] = {
            "schema_version": 1,
            "verifier_revision": trusted_controller,
            "source_report_digest": _digest(source_bytes),
            "workflow_run_id": run_context["workflow_run_id"],
            "workflow_attempt": run_context["workflow_attempt"],
            "workflow_head": run_context["workflow_head"],
            "workflow_name": run_context["workflow_name"],
            "workflow_event": run_context["workflow_event"],
            "workflow_path": run_context["run_workflow_path"],
            "artifact_id": bundle_artifact["id"],
            "artifact_digest": bundle_artifact["digest"],
            "artifact_name": bundle_artifact["name"],
            "bundle_identity": bundle_identity,
            "bundle_content_digest": bundle_content,
            "trusted_checks": {
                "report-shape": "passed",
                "bundle-contract": "passed",
                "bundle-equivalence": "passed",
                "provider-declarations": "passed",
                "identity-binding": "passed",
            },
        }
        verified["verification"].update(verification_changes or {})
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

    def _build(
        self,
        root: Path,
        producer: str,
        *,
        run_context: dict | None = None,
        reconciliation_implementation: dict | None = None,
        providers: dict | None = None,
        trusted_controller: str = CONTROLLER,
        trusted_policy: str = POLICY,
        bundle_identity: str = BUNDLE_IDENTITY,
        bundle_content: str = BUNDLE_CONTENT,
        bundle_artifact: dict | None = None,
        qualification_artifact: dict | None = None,
        report_input_changes: dict | None = None,
        report_trust_changes: dict | None = None,
        verified_input_changes: dict | None = None,
        verification_changes: dict | None = None,
    ):
        run_context = run_context or _direct_run_context(producer)
        reconciliation_implementation = reconciliation_implementation or _direct_reconciliation_implementation(
            run_context["workflow_head"]
        )
        current, candidate, source, verified, reconciliation = self._fixture(
            root,
            producer,
            run_context=run_context,
            providers=providers,
            trusted_controller=trusted_controller,
            trusted_policy=trusted_policy,
            bundle_identity=bundle_identity,
            bundle_content=bundle_content,
            bundle_artifact=bundle_artifact,
            report_input_changes=report_input_changes,
            report_trust_changes=report_trust_changes,
            verified_input_changes=verified_input_changes,
            verification_changes=verification_changes,
        )
        qualification_artifact = qualification_artifact or {
            "id": 102,
            "digest": "sha256:" + "9" * 64,
            "name": f"publication-compatibility-{bundle_identity}-{run_context['workflow_attempt']}-reconciliation",
        }
        intent = build_intent(
            current=current,
            candidate=candidate,
            source_report=source,
            verified_report=verified,
            reconciliation_report=reconciliation,
            producer_revision=producer,
            consumer_base_revision=producer,
            expected_current_lock_digest=_digest(current.read_bytes()),
            qualification_artifact=qualification_artifact,
            trusted_controller_revision=trusted_controller,
            trusted_policy_revision=trusted_policy,
            runtime_run_context=run_context,
            reconciliation_implementation=reconciliation_implementation,
        )
        return current, candidate, intent

    def _new_git_repo(self, directory: str):
        root = Path(directory) / "merged-repo"
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
        return root, base

    def _merge_intent(self, root: Path, base: str, intent_bytes: bytes, kind: str = "regular"):
        intent_path = root / "publication-promotion-intent.json"
        if kind == "symlink":
            (root / "outside-intent.json").write_bytes(intent_bytes)
            intent_path.symlink_to("outside-intent.json")
        elif kind == "tree":
            intent_path.mkdir()
            (intent_path / "nested").write_bytes(intent_bytes)
        else:
            intent_path.write_bytes(intent_bytes)
            if kind == "executable":
                intent_path.chmod(0o755)
        if kind == "symlink":
            subprocess.run(["git", "-C", str(root), "add", "publication-promotion-intent.json"], check=True)
        else:
            subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(root), "commit", "-m", "intent"], check=True, capture_output=True)
        intent_commit = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
        tree = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD^{tree}"], text=True).strip()
        merge = subprocess.check_output(
            ["git", "-C", str(root), "commit-tree", tree, "-p", base, "-p", intent_commit, "-m", "merge"],
            text=True,
        ).strip()
        subprocess.run(["git", "-C", str(root), "update-ref", "refs/heads/integration", merge], check=True)
        subprocess.run(["git", "-C", str(root), "checkout", "--detach", merge], check=True, capture_output=True)
        return merge

    def _merged_fixture(self, directory: str, kind: str = "regular", intent_mutator=None):
        root, base = self._new_git_repo(directory)
        _, _, intent = self._build(Path(directory), base)
        if intent_mutator is not None:
            intent_mutator(intent)
        intent_bytes = _write_json(Path(directory) / "intent-fixture.json", intent)
        merge = self._merge_intent(root, base, intent_bytes, kind)
        branch = f"automation/publication-{intent['idempotency_key']}"
        return root, base, merge, intent, intent_bytes, branch

    def _existing_pr_fixture(self, directory: str):
        root, base = self._new_git_repo(directory)
        _, _, intent = self._build(Path(directory), base)
        intent_path = root / "publication-promotion-intent.json"
        intent_bytes = _write_json(intent_path, intent)
        subprocess.run(["git", "-C", str(root), "add", str(intent_path)], check=True)
        expected_tree = subprocess.check_output(["git", "-C", str(root), "write-tree"], text=True).strip()
        subprocess.run(["git", "-C", str(root), "commit", "-m", "intent"], check=True, capture_output=True)
        head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
        branch = f"automation/publication-{intent['idempotency_key']}"
        remote_head_ref = f"refs/remotes/origin/{branch}"
        subprocess.run(["git", "-C", str(root), "update-ref", remote_head_ref, head], check=True)
        repository = "TakashiSasaki/templates"
        pr = {
            "number": 17,
            "state": "open",
            "merged_at": None,
            "title": "chore(integration): record trusted publication intent",
            "body": (
                f"Guarded deterministic Integration publication promotion. Consumer base: {base}. "
                f"Idempotency key: {intent['idempotency_key']}."
            ),
            "base": {
                "ref": "integration",
                "sha": base,
                "repo": {"full_name": repository},
            },
            "head": {
                "ref": branch,
                "sha": head,
                "repo": {"full_name": repository},
            },
        }
        return root, base, head, expected_tree, intent, intent_bytes, branch, remote_head_ref, repository, pr

    def test_merged_pr_provenance_accepts_same_repository_automation_branch(self):
        with tempfile.TemporaryDirectory() as directory:
            root, _, merged, intent, _, branch = self._merged_fixture(directory)
            event_path = root / "event.json"
            _write_json(event_path, {
                "pull_request": {
                    "merged": True,
                    "merge_commit_sha": merged,
                    "base": {"ref": "integration"},
                    "head": {
                        "ref": branch,
                        "repo": {"full_name": "TakashiSasaki/templates"},
                    },
                },
            })

            result = verify_merged_pr_intent(
                event_path=event_path,
                target_repository="TakashiSasaki/templates",
                repository_root=root,
                merged_revision=merged,
                trusted_controller_revision=CONTROLLER,
                trusted_policy_revision=POLICY,
            )
            self.assertEqual(result["idempotency_key"], intent["idempotency_key"])

    def test_merged_pr_rejects_fork_with_identical_intent_branch_and_key(self):
        with tempfile.TemporaryDirectory() as directory:
            root, _, merged, intent, intent_bytes, branch = self._merged_fixture(directory)
            # The committed bytes and branch key are valid and identical; provenance
            # must reject the fork before those content bindings can authorize it.
            self.assertEqual(_digest(intent_bytes), _digest(_write_json(root / "same-intent.json", intent)))
            self.assertEqual(branch, f"automation/publication-{intent['idempotency_key']}")
            valid_content = verify_merged_intent(
                repository_root=root,
                merged_revision=merged,
                trusted_controller_revision=CONTROLLER,
                trusted_policy_revision=POLICY,
                branch=branch,
            )
            self.assertEqual(valid_content, intent)
            event_path = root / "fork-event.json"
            _write_json(event_path, {
                "pull_request": {
                    "merged": True,
                    "merge_commit_sha": merged,
                    "base": {"ref": "integration"},
                    "head": {
                        "ref": branch,
                        "repo": {"full_name": "attacker/templates"},
                    },
                },
            })

            with self.assertRaisesRegex(ValueError, "not the exact target repository"):
                verify_merged_pr_intent(
                    event_path=event_path,
                    target_repository="TakashiSasaki/templates",
                    repository_root=root,
                    merged_revision=merged,
                    trusted_controller_revision=CONTROLLER,
                    trusted_policy_revision=POLICY,
                )

    def test_merged_pr_provenance_rejects_missing_or_null_head_repository(self):
        base = {
            "merged": True,
            "merge_commit_sha": "a" * 40,
            "base": {"ref": "integration"},
            "head": {
                "ref": "automation/publication-" + "b" * 64,
                "repo": {"full_name": "TakashiSasaki/templates"},
            },
        }
        variants = []
        missing_repo = copy.deepcopy(base)
        del missing_repo["head"]["repo"]
        variants.append(("missing repo", missing_repo))
        null_repo = copy.deepcopy(base)
        null_repo["head"]["repo"] = None
        variants.append(("deleted source repository", null_repo))
        missing_full_name = copy.deepcopy(base)
        del missing_full_name["head"]["repo"]["full_name"]
        variants.append(("missing full_name", missing_full_name))
        null_full_name = copy.deepcopy(base)
        null_full_name["head"]["repo"]["full_name"] = None
        variants.append(("null full_name", null_full_name))

        for label, pull_request in variants:
            with self.subTest(provenance=label), self.assertRaises(ValueError):
                verify_merged_pr_provenance(
                    pull_request=pull_request,
                    target_repository="TakashiSasaki/templates",
                    merged_revision="a" * 40,
                )

    def test_current_lock_produces_a_bound_marker_only_intent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            producer = "a" * 40
            run_context = _direct_run_context(producer)
            implementation = _direct_reconciliation_implementation(producer)
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
                runtime_run_context=run_context,
                reconciliation_implementation=implementation,
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
                    runtime_run_context=run_context,
                    reconciliation_implementation=implementation,
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
                    runtime_run_context=run_context,
                    reconciliation_implementation=implementation,
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
                    runtime_run_context=run_context,
                    reconciliation_implementation=implementation,
                )

    def test_observed_site_reusable_topology_builds_and_verifies_intent(self):
        # The pre-fix builder compared the caller's run path directly to the
        # reusable implementation path and rejected this otherwise trusted run.
        run_context = _observed_site_run_context()
        implementation = _observed_reconciliation_implementation()
        providers = {
            "modeling": OBSERVED_MODELING,
            "composition": OBSERVED_COMPOSITION,
            "policy": OBSERVED_POLICY_PIN,
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            current, candidate, intent = self._build(
                root,
                OBSERVED_PRODUCER,
                run_context=run_context,
                reconciliation_implementation=implementation,
                providers=providers,
                trusted_controller=OBSERVED_PRODUCER,
                trusted_policy=OBSERVED_POLICY_PIN,
                bundle_identity=OBSERVED_BUNDLE_IDENTITY,
                bundle_content=OBSERVED_BUNDLE_CONTENT,
                bundle_artifact=OBSERVED_BUNDLE_ARTIFACT,
                qualification_artifact=OBSERVED_QUALIFICATION_ARTIFACT,
            )
            self.assertEqual(intent["run_provenance"]["invocation_mode"], "site-reusable")
            self.assertEqual(
                intent["run_provenance"]["run_workflow_path"],
                SITE_DISPATCH_PATH,
            )
            self.assertEqual(
                intent["reconciliation_implementation"]["workflow_file_path"],
                RECONCILIATION_PATH,
            )
            self.assertFalse(intent["lock_update_required"])

            for field, value in (
                ("workflow_run_id", run_context["workflow_run_id"] + 1),
                ("workflow_attempt", run_context["workflow_attempt"] + 1),
                ("workflow_head", "4" * 40),
                ("workflow_name", "Unrelated workflow"),
                ("workflow_event", "repository_dispatch"),
                ("workflow_path", RECONCILIATION_PATH),
            ):
                with self.subTest(trusted_receipt=field), tempfile.TemporaryDirectory() as mismatch_dir:
                    with self.assertRaises(ValueError):
                        self._build(
                            Path(mismatch_dir),
                            OBSERVED_PRODUCER,
                            run_context=run_context,
                            reconciliation_implementation=implementation,
                            providers=providers,
                            trusted_controller=OBSERVED_PRODUCER,
                            trusted_policy=OBSERVED_POLICY_PIN,
                            bundle_identity=OBSERVED_BUNDLE_IDENTITY,
                            bundle_content=OBSERVED_BUNDLE_CONTENT,
                            bundle_artifact=OBSERVED_BUNDLE_ARTIFACT,
                            qualification_artifact=OBSERVED_QUALIFICATION_ARTIFACT,
                            verification_changes={field: value},
                        )

            intent_path = root / "publication-promotion-intent.json"
            encoded = _write_json(intent_path, intent)
            verified = verify_premerge_intent(
                intent_path=intent_path,
                base_lock=current,
                selected_lock=candidate,
                consumer_base_revision=OBSERVED_PRODUCER,
                trusted_controller_revision=OBSERVED_PRODUCER,
                trusted_policy_revision=OBSERVED_POLICY_PIN,
                branch=f"automation/publication-{intent['idempotency_key']}",
                runtime_run_context=run_context,
                reconciliation_implementation=implementation,
                expected_intent_digest=_digest(encoded),
            )
            self.assertEqual(verified["run_provenance"], intent["run_provenance"])
            targeted = verify_target_intent(
                intent_path=intent_path,
                runtime_run_context=run_context,
                reconciliation_implementation=implementation,
                expected_intent_digest=_digest(encoded),
            )
            self.assertEqual(targeted["reconciliation_implementation"], implementation)

            changed_run_contexts = []
            for field, value in (
                ("repository", "attacker/templates"),
                ("workflow_run_id", run_context["workflow_run_id"] + 1),
                ("workflow_attempt", run_context["workflow_attempt"] + 1),
                ("workflow_head", "4" * 40),
                ("workflow_name", "Unrelated workflow"),
                ("workflow_event", "repository_dispatch"),
                ("run_workflow_path", ".github/workflows/integration-qualification.yml"),
            ):
                changed = copy.deepcopy(run_context)
                changed[field] = value
                changed_run_contexts.append((field, changed))
            for field, changed in changed_run_contexts:
                with self.subTest(run_provenance=field), self.assertRaises(ValueError):
                    verify_target_intent(
                        intent_path=intent_path,
                        runtime_run_context=changed,
                        reconciliation_implementation=implementation,
                    )

            changed_implementations = []
            for field, value in (
                ("workflow_repository", "attacker/templates"),
                ("workflow_file_path", ".github/workflows/other.yml"),
                ("workflow_sha", "0" * 40),
                (
                    "workflow_ref",
                    f"{REPOSITORY}/{RECONCILIATION_PATH}@refs/heads/integration",
                ),
            ):
                changed = copy.deepcopy(implementation)
                changed[field] = value
                changed_implementations.append((field, changed))
            for field, changed in changed_implementations:
                with self.subTest(reconciliation_implementation=field), self.assertRaises(ValueError):
                    verify_target_intent(
                        intent_path=intent_path,
                        runtime_run_context=run_context,
                        reconciliation_implementation=changed,
                    )

            with self.assertRaisesRegex(ValueError, "incomplete or malformed"):
                verify_target_intent(
                    intent_path=intent_path,
                    runtime_run_context={
                        key: value for key, value in run_context.items()
                        if key != "run_workflow_path"
                    },
                    reconciliation_implementation=implementation,
                )
            with self.assertRaisesRegex(ValueError, "incomplete or malformed"):
                verify_target_intent(
                    intent_path=intent_path,
                    runtime_run_context=run_context,
                    reconciliation_implementation={
                        key: value for key, value in implementation.items()
                        if key != "workflow_sha"
                    },
                )

            tampered = copy.deepcopy(intent)
            tampered["run_provenance"]["workflow_head"] = SITE_RECONCILIATION_SHA
            _write_json(intent_path, tampered)
            with self.assertRaises(ValueError):
                verify_target_intent(
                    intent_path=intent_path,
                    runtime_run_context=run_context,
                    reconciliation_implementation=implementation,
                    expected_intent_digest=_digest(encoded),
                )

    def test_direct_workflow_dispatch_and_repository_dispatch_build_and_verify(self):
        producer = "a" * 40
        for event in ("workflow_dispatch", "repository_dispatch"):
            with self.subTest(event=event), tempfile.TemporaryDirectory() as directory:
                run_context = _direct_run_context(producer, event=event)
                implementation = _direct_reconciliation_implementation(producer)
                current, candidate, intent = self._build(
                    Path(directory),
                    producer,
                    run_context=run_context,
                    reconciliation_implementation=implementation,
                )
                intent_path = Path(directory) / "publication-promotion-intent.json"
                encoded = _write_json(intent_path, intent)
                verified = verify_premerge_intent(
                    intent_path=intent_path,
                    base_lock=current,
                    selected_lock=candidate,
                    consumer_base_revision=producer,
                    trusted_controller_revision=CONTROLLER,
                    trusted_policy_revision=POLICY,
                    branch=f"automation/publication-{intent['idempotency_key']}",
                    runtime_run_context=run_context,
                    reconciliation_implementation=implementation,
                    expected_intent_digest=_digest(encoded),
                )
                self.assertEqual(verified["run_provenance"]["invocation_mode"], "direct")
                self.assertEqual(
                    verify_target_intent(
                        intent_path=intent_path,
                        runtime_run_context=run_context,
                        reconciliation_implementation=implementation,
                        expected_intent_digest=_digest(encoded),
                    ),
                    intent,
                )

    def test_source_verified_and_trusted_input_disagreements_are_rejected(self):
        cases = (
            (
                "source and verified report disagreement",
                {"verified_input_changes": {"policy_revision": "0" * 40}},
                "source and verified qualification inputs disagree",
            ),
            (
                "wrong producer",
                {"report_input_changes": {"integration_revision": "0" * 40}},
                "qualification producer does not match",
            ),
            (
                "wrong Bundle identity",
                {"report_input_changes": {"bundle_identity": "0" * 64}},
                "Bundle identity differs",
            ),
            (
                "wrong Bundle digest",
                {"report_input_changes": {"bundle_content_digest": "0" * 64}},
                "Bundle content digest differs",
            ),
            (
                "wrong controller pin",
                {"report_trust_changes": {"controller_revision": "0" * 40}},
                "controller identity does not match",
            ),
            (
                "wrong Policy pin",
                {"report_trust_changes": {"policy_revision": "0" * 40}},
                "Policy identity does not match",
            ),
        )
        for label, changes, error in cases:
            with self.subTest(binding=label), tempfile.TemporaryDirectory() as directory:
                with self.assertRaisesRegex(ValueError, error):
                    self._build(Path(directory), "a" * 40, **changes)

        invalid_artifacts = (
            (
                "qualification artifact digest",
                {"id": 102, "digest": "invalid", "name": f"publication-compatibility-{BUNDLE_IDENTITY}-1-reconciliation"},
                "digest is malformed",
            ),
            (
                "qualification artifact namespace",
                {"id": 102, "digest": "sha256:" + "9" * 64, "name": "unrelated-artifact"},
                "outside the reconciliation namespace",
            ),
        )
        for label, artifact, error in invalid_artifacts:
            with self.subTest(binding=label), tempfile.TemporaryDirectory() as directory:
                with self.assertRaisesRegex(ValueError, error):
                    self._build(
                        Path(directory),
                        "a" * 40,
                        qualification_artifact=artifact,
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
            original_branch = branch
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
            subprocess.run(["git", "-C", str(root), "add", "publication-promotion-intent.json"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-m", "tampered intent"], check=True, capture_output=True)
            tampered_commit = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
            tampered_tree = subprocess.check_output(
                ["git", "-C", str(root), "rev-parse", "HEAD^{tree}"], text=True
            ).strip()
            tampered_merge = subprocess.check_output(
                ["git", "-C", str(root), "commit-tree", tampered_tree, "-p", base, "-p", tampered_commit, "-m", "merge tampered"],
                text=True,
            ).strip()
            subprocess.run(["git", "-C", str(root), "checkout", "--detach", tampered_merge], check=True, capture_output=True)
            with self.assertRaisesRegex(ValueError, "first parent"):
                verify_merged_intent(
                    repository_root=root,
                    merged_revision=tampered_merge,
                    intent_path=intent_path,
                    trusted_controller_revision=CONTROLLER,
                    trusted_policy_revision=POLICY,
                    branch=branch,
                )

            subprocess.run(["git", "-C", str(root), "checkout", "--detach", merge], check=True, capture_output=True)
            with self.assertRaisesRegex(ValueError, "trust pins"):
                verify_merged_intent(
                    repository_root=root,
                    merged_revision=merge,
                    intent_path=intent_path,
                    trusted_controller_revision=CONTROLLER,
                    trusted_policy_revision="a" * 40,
                    branch=original_branch,
                )

    def test_merged_intent_accepts_only_the_exact_committed_regular_blob(self):
        with tempfile.TemporaryDirectory() as directory:
            root, base, merge, intent, intent_bytes, branch = self._merged_fixture(directory)
            result = verify_merged_intent(
                repository_root=root,
                merged_revision=merge,
                intent_path=root / "publication-promotion-intent.json",
                trusted_controller_revision=CONTROLLER,
                trusted_policy_revision=POLICY,
                branch=branch,
            )
            self.assertEqual(result, intent)

            tampered = copy.deepcopy(intent)
            tampered["run_provenance"]["workflow_name"] = "tampered worktree copy"
            (root / "publication-promotion-intent.json").write_bytes(
                (json.dumps(tampered, indent=2, sort_keys=True) + "\n").encode()
            )
            result = verify_merged_intent(
                repository_root=root,
                merged_revision=merge,
                intent_path=root / "publication-promotion-intent.json",
                trusted_controller_revision=CONTROLLER,
                trusted_policy_revision=POLICY,
                branch=branch,
            )
            self.assertEqual(result["run_provenance"]["workflow_name"], intent["run_provenance"]["workflow_name"])
            self.assertNotEqual((root / "publication-promotion-intent.json").read_bytes(), intent_bytes)

    def test_merged_intent_rejects_the_symlink_exploit(self):
        with tempfile.TemporaryDirectory() as directory:
            root, _, merge, _, _, branch = self._merged_fixture(directory, kind="symlink")
            intent_path = root / "publication-promotion-intent.json"
            self.assertTrue(intent_path.is_symlink())
            tracked = subprocess.check_output(["git", "-C", str(root), "ls-files"], text=True).splitlines()
            self.assertNotIn("outside-intent.json", tracked)
            self.assertEqual(intent_path.read_bytes(), (root / "outside-intent.json").read_bytes())
            with self.assertRaisesRegex(ValueError, "unexpected Git mode"):
                verify_merged_intent(
                    repository_root=root,
                    merged_revision=merge,
                    intent_path=intent_path,
                    trusted_controller_revision=CONTROLLER,
                    trusted_policy_revision=POLICY,
                    branch=branch,
                )

    def test_merged_intent_rejects_unexpected_mode_and_object_type(self):
        for kind in ("executable", "tree"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                root, _, merge, _, _, branch = self._merged_fixture(directory, kind=kind)
                with self.assertRaisesRegex(ValueError, "Git"):
                    verify_merged_intent(
                        repository_root=root,
                        merged_revision=merge,
                        intent_path=root / "publication-promotion-intent.json",
                        trusted_controller_revision=CONTROLLER,
                        trusted_policy_revision=POLICY,
                        branch=branch,
                    )

    def test_merged_intent_rejects_tampered_committed_blob(self):
        def tamper(intent):
            intent["base_lock_digest"] = "0" * 64

        with tempfile.TemporaryDirectory() as directory:
            root, _, merge, _, _, branch = self._merged_fixture(directory, intent_mutator=tamper)
            with self.assertRaisesRegex(ValueError, "parent lock"):
                verify_merged_intent(
                    repository_root=root,
                    merged_revision=merge,
                    intent_path=root / "publication-promotion-intent.json",
                    trusted_controller_revision=CONTROLLER,
                    trusted_policy_revision=POLICY,
                    branch=branch,
                )

    def test_merged_intent_rejects_noncanonical_committed_json(self):
        with tempfile.TemporaryDirectory() as directory:
            root, base = self._new_git_repo(directory)
            _, _, intent = self._build(Path(directory), base)
            noncanonical = (json.dumps(intent, sort_keys=True) + "\n").encode()
            merge = self._merge_intent(root, base, noncanonical)
            branch = f"automation/publication-{intent['idempotency_key']}"
            with self.assertRaisesRegex(ValueError, "canonical"):
                verify_merged_intent(
                    repository_root=root,
                    merged_revision=merge,
                    intent_path=root / "publication-promotion-intent.json",
                    trusted_controller_revision=CONTROLLER,
                    trusted_policy_revision=POLICY,
                    branch=branch,
                )

    def test_live_consumer_base_compare_and_swap_stops_when_target_moves(self):
        verify_live_consumer_base(expected_base="a" * 40, live_base="a" * 40)
        with self.assertRaisesRegex(ValueError, "differs"):
            verify_live_consumer_base(expected_base="a" * 40, live_base="b" * 40)

    def test_existing_promotion_pr_requires_exact_base_head_tree_and_intent_bindings(self):
        with tempfile.TemporaryDirectory() as directory:
            (
                root, base, head, expected_tree, intent, intent_bytes, branch,
                remote_head_ref, repository, pr,
            ) = self._existing_pr_fixture(directory)

            verified = verify_existing_promotion_pr(
                pr=pr,
                repository_root=root,
                repository=repository,
                expected_base=base,
                expected_tree=expected_tree,
                expected_intent_digest=_digest(intent_bytes),
                expected_branch=branch,
                expected_idempotency_key=intent["idempotency_key"],
                expected_paths={"publication-promotion-intent.json"},
                remote_head_ref=remote_head_ref,
            )
            self.assertEqual(verified["head"]["sha"], head)

            wrong_base = copy.deepcopy(pr)
            wrong_base["base"]["ref"] = "main"
            with self.assertRaisesRegex(ValueError, "base branch"):
                verify_existing_promotion_pr(
                    pr=wrong_base, repository_root=root, repository=repository,
                    expected_base=base, expected_tree=expected_tree,
                    expected_intent_digest=_digest(intent_bytes), expected_branch=branch,
                    expected_idempotency_key=intent["idempotency_key"],
                    expected_paths={"publication-promotion-intent.json"}, remote_head_ref=remote_head_ref,
                )

            wrong_head = copy.deepcopy(pr)
            wrong_head["head"]["ref"] = "automation/publication-other"
            with self.assertRaisesRegex(ValueError, "head branch"):
                verify_existing_promotion_pr(
                    pr=wrong_head, repository_root=root, repository=repository,
                    expected_base=base, expected_tree=expected_tree,
                    expected_intent_digest=_digest(intent_bytes), expected_branch=branch,
                    expected_idempotency_key=intent["idempotency_key"],
                    expected_paths={"publication-promotion-intent.json"}, remote_head_ref=remote_head_ref,
                )

            stale = copy.deepcopy(pr)
            stale["head"]["sha"] = base
            subprocess.run(["git", "-C", str(root), "update-ref", remote_head_ref, base], check=True)
            with self.assertRaisesRegex(ValueError, "exact deterministic commit"):
                verify_existing_promotion_pr(
                    pr=stale, repository_root=root, repository=repository,
                    expected_base=base, expected_tree=expected_tree,
                    expected_intent_digest=_digest(intent_bytes), expected_branch=branch,
                    expected_idempotency_key=intent["idempotency_key"],
                    expected_paths={"publication-promotion-intent.json"}, remote_head_ref=remote_head_ref,
                )
            subprocess.run(["git", "-C", str(root), "update-ref", remote_head_ref, head], check=True)

            unexpected = copy.deepcopy(pr)
            (root / "unexpected.txt").write_text("unexpected\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "unexpected.txt"], check=True)
            unexpected_tree = subprocess.check_output(["git", "-C", str(root), "write-tree"], text=True).strip()
            unexpected_head = subprocess.check_output(
                ["git", "-C", str(root), "commit-tree", unexpected_tree, "-p", base, "-m", "unexpected"],
                text=True,
            ).strip()
            subprocess.run(["git", "-C", str(root), "update-ref", remote_head_ref, unexpected_head], check=True)
            unexpected["head"]["sha"] = unexpected_head
            with self.assertRaisesRegex(ValueError, "tree differs"):
                verify_existing_promotion_pr(
                    pr=unexpected, repository_root=root, repository=repository,
                    expected_base=base, expected_tree=expected_tree,
                    expected_intent_digest=_digest(intent_bytes), expected_branch=branch,
                    expected_idempotency_key=intent["idempotency_key"],
                    expected_paths={"publication-promotion-intent.json"}, remote_head_ref=remote_head_ref,
                )

            different_binding = copy.deepcopy(pr)
            different_binding["body"] = different_binding["body"].replace(
                intent["idempotency_key"], "0" * 64
            )
            subprocess.run(["git", "-C", str(root), "update-ref", remote_head_ref, head], check=True)
            with self.assertRaisesRegex(ValueError, "idempotency key"):
                verify_existing_promotion_pr(
                    pr=different_binding, repository_root=root, repository=repository,
                    expected_base=base, expected_tree=expected_tree,
                    expected_intent_digest=_digest(intent_bytes), expected_branch=branch,
                    expected_idempotency_key=intent["idempotency_key"],
                    expected_paths={"publication-promotion-intent.json"}, remote_head_ref=remote_head_ref,
                )

    def test_existing_promotion_pr_requires_explicit_merged_at_null(self):
        with tempfile.TemporaryDirectory() as directory:
            (
                root, base, _, expected_tree, intent, intent_bytes, branch,
                remote_head_ref, repository, pr,
            ) = self._existing_pr_fixture(directory)
            arguments = {
                "repository_root": root,
                "repository": repository,
                "expected_base": base,
                "expected_tree": expected_tree,
                "expected_intent_digest": _digest(intent_bytes),
                "expected_branch": branch,
                "expected_idempotency_key": intent["idempotency_key"],
                "expected_paths": {"publication-promotion-intent.json"},
                "remote_head_ref": remote_head_ref,
            }

            # A complete API object explicitly reports an unmerged PR with null.
            self.assertIsNone(verify_existing_promotion_pr(pr=pr, **arguments)["merged_at"])

            merged = copy.deepcopy(pr)
            merged["merged_at"] = "2026-09-26T00:00:00Z"
            with self.assertRaisesRegex(ValueError, "not open"):
                verify_existing_promotion_pr(pr=merged, **arguments)

            incomplete = copy.deepcopy(pr)
            del incomplete["merged_at"]
            with self.assertRaisesRegex(ValueError, "missing the merged_at field"):
                verify_existing_promotion_pr(pr=incomplete, **arguments)

    def test_existing_promotion_pr_rejects_incomplete_trust_bindings(self):
        with tempfile.TemporaryDirectory() as directory:
            (
                root, base, _, expected_tree, intent, intent_bytes, branch,
                remote_head_ref, repository, pr,
            ) = self._existing_pr_fixture(directory)
            arguments = {
                "repository_root": root,
                "repository": repository,
                "expected_base": base,
                "expected_tree": expected_tree,
                "expected_intent_digest": _digest(intent_bytes),
                "expected_branch": branch,
                "expected_idempotency_key": intent["idempotency_key"],
                "expected_paths": {"publication-promotion-intent.json"},
                "remote_head_ref": remote_head_ref,
            }
            malformed = []
            missing_state = copy.deepcopy(pr)
            del missing_state["state"]
            malformed.append(("state", missing_state))
            missing_base = copy.deepcopy(pr)
            del missing_base["base"]
            malformed.append(("base", missing_base))
            missing_head = copy.deepcopy(pr)
            del missing_head["head"]
            malformed.append(("head", missing_head))
            missing_base_sha = copy.deepcopy(pr)
            del missing_base_sha["base"]["sha"]
            malformed.append(("base SHA", missing_base_sha))
            missing_head_sha = copy.deepcopy(pr)
            del missing_head_sha["head"]["sha"]
            malformed.append(("head SHA", missing_head_sha))
            missing_repo_name = copy.deepcopy(pr)
            del missing_repo_name["head"]["repo"]["full_name"]
            malformed.append(("repository", missing_repo_name))
            missing_base_repo_name = copy.deepcopy(pr)
            del missing_base_repo_name["base"]["repo"]["full_name"]
            malformed.append(("base repository", missing_base_repo_name))

            for label, incomplete in malformed:
                with self.subTest(field=label), self.assertRaises(ValueError):
                    verify_existing_promotion_pr(pr=incomplete, **arguments)

if __name__ == "__main__":
    unittest.main()
