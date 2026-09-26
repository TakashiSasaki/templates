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
            tampered["qualification"]["workflow_name"] = "tampered worktree copy"
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
            self.assertEqual(result["qualification"]["workflow_name"], intent["qualification"]["workflow_name"])
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
