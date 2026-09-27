"""Adversarial coverage for exact Site adoption PR reuse and target checks."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import yaml

from scripts import verify_site_adoption_pr as verifier


REPOSITORY = "TakashiSasaki/templates"
IDEMPOTENCY_KEY = "a" * 64
BRANCH = f"automation/site-publication-{IDEMPOTENCY_KEY}"


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


class SiteAdoptionPRVerifierTests(unittest.TestCase):
    def _fixture(self, directory: str):
        work = Path(directory)
        repository_root = work / "repository"
        repository_root.mkdir()
        subprocess.run(["git", "init", "-b", "site", str(repository_root)], check=True, capture_output=True)
        _git(repository_root, "config", "user.name", "Test")
        _git(repository_root, "config", "user.email", "test@example.invalid")

        base_lock = b'{"schema_version":1,"revision":"' + b"1" * 40 + b'"}\n'
        lock = repository_root / "integration-source.json"
        lock.write_bytes(base_lock)
        subprocess.run(["git", "-C", str(repository_root), "add", "integration-source.json"], check=True)
        subprocess.run(["git", "-C", str(repository_root), "commit", "-m", "Site base"], check=True, capture_output=True)
        base = _git(repository_root, "rev-parse", "HEAD")

        candidate_lock = work / "candidate-integration-source.json"
        candidate_bytes = (
            json.dumps(
                {
                    "schema_version": 1,
                    "repository": REPOSITORY,
                    "revision": "2" * 40,
                    "bundle_schema": 4,
                    "bundle_identity": "3" * 64,
                    "content_digest": "4" * 64,
                },
                indent=2,
            )
            + "\n"
        ).encode()
        candidate_lock.write_bytes(candidate_bytes)
        lock.write_bytes(candidate_bytes)
        subprocess.run(["git", "-C", str(repository_root), "add", "integration-source.json"], check=True)
        expected_tree = _git(repository_root, "write-tree")
        subprocess.run(["git", "-C", str(repository_root), "commit", "-m", "Adopt candidate"], check=True, capture_output=True)
        head = _git(repository_root, "rev-parse", "HEAD")
        remote_head_ref = f"refs/remotes/origin/{BRANCH}"
        subprocess.run(["git", "-C", str(repository_root), "update-ref", remote_head_ref, head], check=True)

        body = verifier.render_pr_body(
            repository=REPOSITORY,
            consumer_base=base,
            idempotency_key=IDEMPOTENCY_KEY,
            candidate_lock=candidate_lock,
        )
        pr = {
            "number": 17,
            "state": "open",
            "merged": False,
            "merged_at": None,
            "draft": False,
            "title": verifier.PR_TITLE,
            "html_url": "https://github.com/TakashiSasaki/templates/pull/17",
            "body": body,
            "base": {"ref": "site", "sha": base, "repo": {"full_name": REPOSITORY}},
            "head": {"ref": BRANCH, "sha": head, "repo": {"full_name": REPOSITORY}},
        }
        return {
            "repository_root": repository_root,
            "candidate_lock": candidate_lock,
            "base": base,
            "head": head,
            "expected_tree": expected_tree,
            "remote_head_ref": remote_head_ref,
            "pr": pr,
        }

    def _verify(self, fixture, pr=None, *, candidate_lock=None, expected_tree=None, expected_key=IDEMPOTENCY_KEY):
        return verifier.verify_existing_site_adoption_pr(
            pr=fixture["pr"] if pr is None else pr,
            repository_root=fixture["repository_root"],
            repository=REPOSITORY,
            expected_base=fixture["base"],
            expected_tree=fixture["expected_tree"] if expected_tree is None else expected_tree,
            expected_branch=BRANCH,
            expected_idempotency_key=expected_key,
            candidate_lock=fixture["candidate_lock"] if candidate_lock is None else candidate_lock,
            remote_head_ref=fixture["remote_head_ref"],
        )

    def test_exact_existing_pr_is_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = self._fixture(directory)
            self.assertIs(self._verify(fixture), fixture["pr"])

    def test_existing_pr_rejects_base_head_ref_repository_and_state_mismatches(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = self._fixture(directory)
            mutations = (
                lambda pr: pr["base"].update(sha="f" * 40),
                lambda pr: pr["head"].update(sha="f" * 40),
                lambda pr: pr["head"].update(ref="automation/site-publication-other"),
                lambda pr: pr["head"]["repo"].update(full_name="another-owner/templates"),
                lambda pr: pr.update(state="closed"),
                lambda pr: pr.update(merged=True, merged_at="2026-09-27T00:00:00Z"),
            )
            for mutate in mutations:
                pr = copy.deepcopy(fixture["pr"])
                mutate(pr)
                with self.subTest(pr=pr), self.assertRaises(ValueError):
                    self._verify(fixture, pr)

    def test_existing_pr_rejects_remote_branch_tip_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = self._fixture(directory)
            subprocess.run(
                ["git", "-C", str(fixture["repository_root"]), "update-ref", fixture["remote_head_ref"], fixture["base"]],
                check=True,
            )
            with self.assertRaisesRegex(ValueError, "remote deterministic branch tip"):
                self._verify(fixture)

    def test_existing_pr_rejects_wrong_commit_parent(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = self._fixture(directory)
            root = fixture["repository_root"]
            base_tree = _git(root, "rev-parse", f"{fixture['base']}^{{tree}}")
            wrong_parent = subprocess.check_output(
                ["git", "-C", str(root), "commit-tree", base_tree, "-p", fixture["base"], "-m", "wrong intermediate parent"],
                text=True,
            ).strip()
            wrong_head = subprocess.check_output(
                ["git", "-C", str(root), "commit-tree", fixture["expected_tree"], "-p", wrong_parent, "-m", "wrong adoption parent"],
                text=True,
            ).strip()
            subprocess.run(["git", "-C", str(root), "update-ref", fixture["remote_head_ref"], wrong_head], check=True)
            pr = copy.deepcopy(fixture["pr"])
            pr["head"]["sha"] = wrong_head
            with self.assertRaisesRegex(ValueError, "single commit on the exact Site base"):
                self._verify(fixture, pr)

    def test_existing_pr_rejects_wrong_tree(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = self._fixture(directory)
            root = fixture["repository_root"]
            (root / "integration-source.json").write_bytes(b'{"wrong":"candidate"}\n')
            subprocess.run(["git", "-C", str(root), "add", "integration-source.json"], check=True)
            wrong_tree = _git(root, "write-tree")
            wrong_head = subprocess.check_output(
                ["git", "-C", str(root), "commit-tree", wrong_tree, "-p", fixture["base"], "-m", "wrong tree"],
                text=True,
            ).strip()
            subprocess.run(["git", "-C", str(root), "update-ref", fixture["remote_head_ref"], wrong_head], check=True)
            pr = copy.deepcopy(fixture["pr"])
            pr["head"]["sha"] = wrong_head
            with self.assertRaisesRegex(ValueError, "tree differs from the current candidate"):
                self._verify(fixture, pr)

    def test_existing_pr_rejects_unexpected_changed_path(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = self._fixture(directory)
            root = fixture["repository_root"]
            (root / "unexpected.txt").write_text("unrelated\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "unexpected.txt"], check=True)
            wrong_tree = _git(root, "write-tree")
            wrong_head = subprocess.check_output(
                ["git", "-C", str(root), "commit-tree", wrong_tree, "-p", fixture["base"], "-m", "extra path"],
                text=True,
            ).strip()
            subprocess.run(["git", "-C", str(root), "update-ref", fixture["remote_head_ref"], wrong_head], check=True)
            pr = copy.deepcopy(fixture["pr"])
            pr["head"]["sha"] = wrong_head
            with self.assertRaisesRegex(ValueError, "unexpected changed paths"):
                self._verify(fixture, pr, expected_tree=wrong_tree)

    def test_existing_pr_rejects_candidate_lock_byte_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = self._fixture(directory)
            changed_candidate = Path(directory) / "changed-candidate.json"
            changed_candidate.write_bytes(fixture["candidate_lock"].read_bytes() + b" ")
            pr = copy.deepcopy(fixture["pr"])
            pr["body"] = verifier.render_pr_body(
                repository=REPOSITORY,
                consumer_base=fixture["base"],
                idempotency_key=IDEMPOTENCY_KEY,
                candidate_lock=changed_candidate,
            )
            with self.assertRaisesRegex(ValueError, "lock bytes differ from the exact candidate"):
                self._verify(fixture, pr, candidate_lock=changed_candidate)

    def test_existing_pr_rejects_idempotency_and_transaction_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = self._fixture(directory)
            pr = copy.deepcopy(fixture["pr"])
            pr["body"] = verifier.render_pr_body(
                repository=REPOSITORY,
                consumer_base=fixture["base"],
                idempotency_key="b" * 64,
                candidate_lock=fixture["candidate_lock"],
            )
            with self.assertRaisesRegex(ValueError, "transaction binding"):
                self._verify(fixture, pr)

    def test_pr_discovery_rejects_ambiguous_branch_and_ignores_other_branches(self):
        pages = [[{"number": 17, "head": {"ref": BRANCH}}, {"number": 18, "head": {"ref": "other"}}]]
        self.assertEqual(verifier.find_matching_pr_number(pages, BRANCH), 17)
        with self.assertRaisesRegex(ValueError, "multiple pull requests"):
            verifier.find_matching_pr_number([pages[0], [{"number": 19, "head": {"ref": BRANCH}}]], BRANCH)

    def test_live_site_target_is_read_again_and_movement_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = self._fixture(directory)
            moved_site = "f" * 40
            with patch.object(verifier, "read_live_site_sha", side_effect=[fixture["base"], moved_site]) as read_live:
                verifier.verify_live_site_target(
                    expected_base=fixture["base"],
                    repository_root=fixture["repository_root"],
                    repository=REPOSITORY,
                )
                with self.assertRaisesRegex(ValueError, "live Site target differs"):
                    verifier.verify_live_site_target(
                        expected_base=fixture["base"],
                        repository_root=fixture["repository_root"],
                        repository=REPOSITORY,
                    )
                self.assertEqual(read_live.call_count, 2)

    def test_new_pr_is_rediscovered_and_uses_the_same_exact_verifier_before_ready(self):
        workflow = yaml.safe_load((Path(__file__).resolve().parents[1] / ".github/workflows/publication-reconcile.yml").read_text())
        job = workflow["jobs"]["adopt_lock_pr"]
        step = next(step for step in job["steps"] if step.get("name") == "Create or reconcile the idempotent Site adoption PR")
        script = step["run"]
        create_at = script.index("gh pr create")
        rediscover_at = script.index("existing=$(matching_pr)", create_at)
        verify_at = script.index('verify_existing "$existing"', rediscover_at)
        ready_at = script.index('report_pr_ready "$existing"', verify_at)
        self.assertLess(create_at, rediscover_at)
        self.assertLess(rediscover_at, verify_at)
        self.assertLess(verify_at, ready_at)
        self.assertIn("python3 scripts/verify_site_adoption_pr.py verify-pr", script)
        self.assertIn('verify_existing "$pr"', script[script.index("report_pr_ready()") : create_at])

    def test_live_target_is_refreshed_at_push_creation_and_reuse_boundaries(self):
        workflow = yaml.safe_load((Path(__file__).resolve().parents[1] / ".github/workflows/publication-reconcile.yml").read_text())
        step = next(step for step in workflow["jobs"]["adopt_lock_pr"]["steps"] if step.get("name") == "Create or reconcile the idempotent Site adoption PR")
        script = step["run"]
        for action in ("git push --force-with-lease", "gh pr create"):
            action_at = script.index(action)
            previous_command = next(
                line.strip()
                for line in reversed(script[:action_at].splitlines())
                if line.strip() and not line.strip().startswith("#")
            )
            self.assertEqual(previous_command, "verify_target")
        verify_existing = script[script.index("verify_existing()") : script.index("report_pr_ready()")]
        self.assertGreaterEqual(verify_existing.count("verify_target"), 2)
        self.assertLess(
            verify_existing.index("gh api \"repos/$GITHUB_REPOSITORY/pulls/$pr\""),
            verify_existing.rindex("verify_target"),
        )
        report = script[script.index("report_pr_ready()") : script.index("test -n \"$EXPECTED_SITE_BASE\"")]
        self.assertIn('verify_existing "$pr"', report)

    def test_reconciliation_controller_keeps_the_review_boundary(self):
        workflow_text = (Path(__file__).resolve().parents[1] / ".github/workflows/publication-reconcile.yml").read_text()
        workflow = yaml.safe_load(workflow_text)
        job = workflow["jobs"]["adopt_lock_pr"]
        step = next(step for step in job["steps"] if step.get("name") == "Create or reconcile the idempotent Site adoption PR")
        script = step["run"]
        self.assertEqual(step["env"]["BRANCH"], "automation/site-publication-$IDEMPOTENCY_KEY")
        self.assertIn("matching_pr()", script)
        self.assertIn("An idempotency branch exists without an open PR; stop for human recovery.", script)
        self.assertIn("gh pr create", script)
        self.assertIn("report_pr_ready()", script)
        self.assertIn("independent exact-head review", script)
        self.assertIn("separate human merge authorization", script)
        self.assertNotRegex(script, r"(?m)^\s*gh\s+pr\s+merge(?:\s|$)")
        self.assertNotRegex(script, r"(?m)^\s*gh\s+pr\s+review\s+--approve(?:\s|$)")
        self.assertNotRegex(script, r"(?m)^\s*git\s+push\b.*(?:refs/heads/)?site(?:\s|$)")
        pushes = [line.strip() for line in script.splitlines() if line.strip().startswith("git push")]
        self.assertEqual(pushes, ['git push --force-with-lease="$remote_ref:" origin "HEAD:$BRANCH"'])
        self.assertNotIn("actions/deploy-pages@", workflow_text)
        self.assertNotIn("deploy-pages.yml", workflow_text)


if __name__ == "__main__":
    unittest.main()
