from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.advance_publication_source import (
    PublicationAdvanceError,
    advance_publication,
)


REPOSITORY = "TakashiSasaki/templates"


def run_git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def write_composition_release(root: Path, marker: str, *, valid: bool = True) -> None:
    release = root / "release" / "composition-installer.json"
    release.parent.mkdir(parents=True, exist_ok=True)
    if not valid:
        release.write_text('{"schema_version": 999}\n', encoding="utf-8")
        return
    value = {
        "schema_version": 1,
        "channel": "stable",
        "installer": {
            "repository": REPOSITORY,
            "revision": marker * 40,
            "path": "scripts/install_composition_skill.py",
            "sha256": marker * 64,
        },
        "skill_source": {
            "repository": REPOSITORY,
            "revision": chr(ord(marker) + 1) * 40,
            "path": "skills/composition",
        },
        "toolchain": {
            "repository": REPOSITORY,
            "revision": chr(ord(marker) + 2) * 40,
        },
    }
    release.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def write_policy_release(root: Path, marker: str, *, valid: bool = True) -> None:
    release = root / "release" / "skill-installer.json"
    release.parent.mkdir(parents=True, exist_ok=True)
    if not valid:
        release.write_text('{"schema_version": 999}\n', encoding="utf-8")
        return
    value = {
        "schema_version": 1,
        "installer": {
            "repository": REPOSITORY,
            "revision": marker * 40,
            "path": "scripts/install_agent_policy_skill.py",
        },
        "skill_source": {
            "repository": REPOSITORY,
            "revision": chr(ord(marker) + 1) * 40,
            "path": "skills/agent-policy",
        },
    }
    release.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def init_repository(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    run_git(root, "config", "user.email", "site-tests@example.invalid")
    run_git(root, "config", "user.name", "Site Tests")


def commit_all(root: Path, message: str) -> str:
    run_git(root, "add", "-A")
    run_git(root, "commit", "-q", "-m", message)
    return run_git(root, "rev-parse", "HEAD")


def init_composition(
    root: Path,
    *,
    invalid_target_release: bool = False,
) -> tuple[str, str]:
    init_repository(root)
    write_composition_release(root, "a")
    first = commit_all(root, "first composition release")
    write_composition_release(root, "d", valid=not invalid_target_release)
    second = commit_all(root, "second composition release")
    return first, second


def init_policy(
    root: Path,
    *,
    invalid_target_release: bool = False,
) -> tuple[str, str]:
    init_repository(root)
    write_policy_release(root, "1")
    first = commit_all(root, "first policy release")
    write_policy_release(root, "3", valid=not invalid_target_release)
    second = commit_all(root, "second policy release")
    return first, second


def write_site(root: Path, composition: str, policy: str) -> None:
    (root / "assets").mkdir(parents=True, exist_ok=True)
    lock = {
        "schema_version": 1,
        "repository": REPOSITORY,
        "publications": {
            "composition": {"revision": composition},
            "policy": {"revision": policy},
        },
    }
    (root / "publication-sources.json").write_text(
        json.dumps(lock, indent=2) + "\n",
        encoding="utf-8",
    )
    (root / "agent.json").write_text("{}\n", encoding="utf-8")
    (root / "assets" / "agent.json").write_text("{}\n", encoding="utf-8")


def snapshot_site(root: Path) -> dict[str, bytes]:
    return {
        path: (root / path).read_bytes()
        for path in (
            "publication-sources.json",
            "agent.json",
            "assets/agent.json",
        )
    }


class AdvancePublicationSourceTests(unittest.TestCase):
    def test_composition_advance_updates_lock_and_both_agent_projections(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            composition_root = root / "composition"
            policy_root = root / "policy"
            site_root = root / "site"
            current_composition, target_composition = init_composition(composition_root)
            current_policy, _ = init_policy(policy_root)
            run_git(policy_root, "checkout", "-q", "--detach", current_policy)
            write_site(site_root, current_composition, current_policy)

            plan = advance_publication(
                site_root=site_root,
                provider="composition",
                provider_root=composition_root,
                composition_root=composition_root,
                policy_root=policy_root,
                target_revision=target_composition,
                expected_current=current_composition,
            )

            lock = json.loads((site_root / "publication-sources.json").read_text())
            self.assertEqual(
                lock["publications"]["composition"]["revision"],
                target_composition,
            )
            self.assertEqual(lock["publications"]["policy"]["revision"], current_policy)
            self.assertEqual(
                (site_root / "agent.json").read_bytes(),
                (site_root / "assets" / "agent.json").read_bytes(),
            )
            manifest = json.loads((site_root / "agent.json").read_text())
            self.assertEqual(
                manifest["authorities"]["composition"]["publication_revision"],
                target_composition,
            )
            self.assertEqual(
                manifest["authorities"]["policy"]["publication_revision"],
                current_policy,
            )
            self.assertEqual(manifest["composition"]["installer"]["revision"], "d" * 40)
            self.assertEqual(manifest["policy"]["installer"]["revision"], "1" * 40)
            self.assertEqual(plan.revisions["composition"], target_composition)

    def test_policy_advance_preserves_composition_and_updates_policy_bootstrap_projection(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            composition_root = root / "composition"
            policy_root = root / "policy"
            site_root = root / "site"
            current_composition, _ = init_composition(composition_root)
            run_git(composition_root, "checkout", "-q", "--detach", current_composition)
            current_policy, target_policy = init_policy(policy_root)
            write_site(site_root, current_composition, current_policy)

            advance_publication(
                site_root=site_root,
                provider="policy",
                provider_root=policy_root,
                composition_root=composition_root,
                policy_root=policy_root,
                target_revision=target_policy,
                expected_current=current_policy,
            )

            lock = json.loads((site_root / "publication-sources.json").read_text())
            self.assertEqual(
                lock["publications"]["composition"]["revision"],
                current_composition,
            )
            self.assertEqual(lock["publications"]["policy"]["revision"], target_policy)
            manifest = json.loads((site_root / "agent.json").read_text())
            self.assertEqual(
                manifest["authorities"]["policy"]["publication_revision"],
                target_policy,
            )
            self.assertEqual(
                manifest["authorities"]["composition"]["publication_revision"],
                current_composition,
            )
            self.assertEqual(manifest["policy"]["installer"]["revision"], "3" * 40)
            self.assertEqual(manifest["policy"]["skill"]["revision"], "4" * 40)

    def test_policy_advance_rejects_mismatched_composition_checkout_before_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            composition_root = root / "composition"
            policy_root = root / "policy"
            site_root = root / "site"
            current_composition, target_composition = init_composition(composition_root)
            current_policy, target_policy = init_policy(policy_root)
            write_site(site_root, current_composition, current_policy)
            self.assertEqual(run_git(composition_root, "rev-parse", "HEAD"), target_composition)
            before = snapshot_site(site_root)

            with self.assertRaisesRegex(
                PublicationAdvanceError,
                "Composition checkout HEAD .* does not match prospective",
            ):
                advance_publication(
                    site_root=site_root,
                    provider="policy",
                    provider_root=policy_root,
                    composition_root=composition_root,
                    policy_root=policy_root,
                    target_revision=target_policy,
                    expected_current=current_policy,
                )

            self.assertEqual(snapshot_site(site_root), before)

    def test_composition_advance_rejects_mismatched_policy_checkout_before_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            composition_root = root / "composition"
            policy_root = root / "policy"
            site_root = root / "site"
            current_composition, target_composition = init_composition(composition_root)
            current_policy, target_policy = init_policy(policy_root)
            write_site(site_root, current_composition, current_policy)
            self.assertEqual(run_git(policy_root, "rev-parse", "HEAD"), target_policy)
            before = snapshot_site(site_root)

            with self.assertRaisesRegex(
                PublicationAdvanceError,
                "Policy checkout HEAD .* does not match prospective",
            ):
                advance_publication(
                    site_root=site_root,
                    provider="composition",
                    provider_root=composition_root,
                    composition_root=composition_root,
                    policy_root=policy_root,
                    target_revision=target_composition,
                    expected_current=current_composition,
                )

            self.assertEqual(snapshot_site(site_root), before)

    def test_expected_current_mismatch_fails_before_any_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            composition_root = root / "composition"
            policy_root = root / "policy"
            site_root = root / "site"
            current_composition, target_composition = init_composition(composition_root)
            current_policy, _ = init_policy(policy_root)
            run_git(policy_root, "checkout", "-q", "--detach", current_policy)
            write_site(site_root, current_composition, current_policy)
            before = snapshot_site(site_root)

            with self.assertRaisesRegex(PublicationAdvanceError, "expected current"):
                advance_publication(
                    site_root=site_root,
                    provider="composition",
                    provider_root=composition_root,
                    composition_root=composition_root,
                    policy_root=policy_root,
                    target_revision=target_composition,
                    expected_current="0" * 40,
                )

            self.assertEqual(snapshot_site(site_root), before)

    def test_provider_checkout_must_match_target_before_any_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            composition_root = root / "composition"
            policy_root = root / "policy"
            site_root = root / "site"
            current_composition, target_composition = init_composition(composition_root)
            current_policy, _ = init_policy(policy_root)
            run_git(policy_root, "checkout", "-q", "--detach", current_policy)
            write_site(site_root, current_composition, current_policy)
            run_git(composition_root, "checkout", "-q", "--detach", current_composition)
            before = snapshot_site(site_root)

            with self.assertRaisesRegex(PublicationAdvanceError, "does not match target"):
                advance_publication(
                    site_root=site_root,
                    provider="composition",
                    provider_root=composition_root,
                    composition_root=composition_root,
                    policy_root=policy_root,
                    target_revision=target_composition,
                    expected_current=current_composition,
                )

            self.assertEqual(snapshot_site(site_root), before)

    def test_invalid_target_sha_fails_before_any_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            composition_root = root / "composition"
            policy_root = root / "policy"
            site_root = root / "site"
            current_composition, _ = init_composition(composition_root)
            current_policy, _ = init_policy(policy_root)
            write_site(site_root, current_composition, current_policy)
            before = snapshot_site(site_root)

            with self.assertRaisesRegex(PublicationAdvanceError, "full lowercase"):
                advance_publication(
                    site_root=site_root,
                    provider="composition",
                    provider_root=composition_root,
                    composition_root=composition_root,
                    policy_root=policy_root,
                    target_revision="composition",
                    expected_current=current_composition,
                )

            self.assertEqual(snapshot_site(site_root), before)

    def test_invalid_target_composition_release_fails_before_any_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            composition_root = root / "composition"
            policy_root = root / "policy"
            site_root = root / "site"
            current_composition, target_composition = init_composition(
                composition_root,
                invalid_target_release=True,
            )
            current_policy, _ = init_policy(policy_root)
            run_git(policy_root, "checkout", "-q", "--detach", current_policy)
            write_site(site_root, current_composition, current_policy)
            before = snapshot_site(site_root)

            with self.assertRaisesRegex(PublicationAdvanceError, "preflight"):
                advance_publication(
                    site_root=site_root,
                    provider="composition",
                    provider_root=composition_root,
                    composition_root=composition_root,
                    policy_root=policy_root,
                    target_revision=target_composition,
                    expected_current=current_composition,
                )

            self.assertEqual(snapshot_site(site_root), before)

    def test_invalid_target_policy_release_fails_before_any_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            composition_root = root / "composition"
            policy_root = root / "policy"
            site_root = root / "site"
            current_composition, _ = init_composition(composition_root)
            run_git(composition_root, "checkout", "-q", "--detach", current_composition)
            current_policy, target_policy = init_policy(
                policy_root,
                invalid_target_release=True,
            )
            write_site(site_root, current_composition, current_policy)
            before = snapshot_site(site_root)

            with self.assertRaisesRegex(PublicationAdvanceError, "preflight"):
                advance_publication(
                    site_root=site_root,
                    provider="policy",
                    provider_root=policy_root,
                    composition_root=composition_root,
                    policy_root=policy_root,
                    target_revision=target_policy,
                    expected_current=current_policy,
                )

            self.assertEqual(snapshot_site(site_root), before)

    def test_symlink_projection_target_is_rejected_before_any_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            composition_root = root / "composition"
            policy_root = root / "policy"
            site_root = root / "site"
            current_composition, target_composition = init_composition(composition_root)
            current_policy, _ = init_policy(policy_root)
            run_git(policy_root, "checkout", "-q", "--detach", current_policy)
            write_site(site_root, current_composition, current_policy)
            published = site_root / "assets" / "agent.json"
            published.unlink()
            published.symlink_to(site_root / "agent.json")
            lock_before = (site_root / "publication-sources.json").read_bytes()
            agent_before = (site_root / "agent.json").read_bytes()

            with self.assertRaisesRegex(PublicationAdvanceError, "regular file"):
                advance_publication(
                    site_root=site_root,
                    provider="composition",
                    provider_root=composition_root,
                    composition_root=composition_root,
                    policy_root=policy_root,
                    target_revision=target_composition,
                    expected_current=current_composition,
                )

            self.assertEqual((site_root / "publication-sources.json").read_bytes(), lock_before)
            self.assertEqual((site_root / "agent.json").read_bytes(), agent_before)
            self.assertTrue(published.is_symlink())


if __name__ == "__main__":
    unittest.main()
