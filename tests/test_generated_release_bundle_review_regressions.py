from __future__ import annotations

import subprocess
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


def _run_git(root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise AssertionError(
            f"git {' '.join(arguments)} failed\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    return completed.stdout.strip()


@unittest.skipUnless(
    _is_template_maintainer_source(),
    "template-maintainer-only generated release bundle review regressions",
)
class GeneratedReleaseBundleReviewRegressionTests(unittest.TestCase):
    def install_and_commit(self, root: Path) -> str:
        _install_release_evidence_producer(root)
        _install_release_bundle_producer(root)
        return _commit_generated_repository(root)

    def produce_release(self, root: Path, revision: str) -> None:
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

    def prepare_approved_release(self, root: Path) -> str:
        revision = self.install_and_commit(root)
        self.produce_release(root, revision)
        return revision

    def run_bundle(self, root: Path, revision: str, *arguments: str):
        return _run_generated_python(
            root,
            "-I",
            "product/produce_release_bundle.py",
            "--revision",
            revision,
            *arguments,
        )

    def test_git_replacement_objects_are_disabled_during_preflight(self) -> None:
        with _generated_repository() as root:
            revision = self.install_and_commit(root)
            _run_git(root, "config", "user.name", "Fixture Reviewer")
            _run_git(
                root,
                "config",
                "user.email",
                "fixture-reviewer@example.invalid",
            )
            surfaces_path = root / "contracts/surfaces.json"
            surfaces = _load_json(surfaces_path)
            surfaces["surfaces"][0]["purpose"] += " Replacement-only bytes."
            _write_json(surfaces_path, surfaces)
            _run_git(root, "add", "contracts/surfaces.json")
            _run_git(root, "commit", "-m", "Create replacement tree")
            replacement = _run_git(root, "rev-parse", "HEAD")
            _run_git(root, "reset", "--hard", revision)
            _run_git(root, "replace", revision, replacement)
            _run_git(root, "reset", "--hard", revision)
            self.produce_release(root, revision)

            result = self.run_bundle(root, revision)

            self.assertEqual(2, result.returncode)
            self.assertIn("Git replacement objects are not permitted", result.stderr)
            self.assertEqual(
                "template",
                _load_json(root / "contracts/release-bundle.json")["mode"],
            )

    def test_raw_worktree_bytes_must_match_candidate_blobs(self) -> None:
        with _generated_repository() as root:
            _install_release_evidence_producer(root)
            _install_release_bundle_producer(root)
            (root / ".gitattributes").write_text(
                "contracts/surfaces.json ident\n",
                encoding="utf-8",
            )
            surfaces_path = root / "contracts/surfaces.json"
            surfaces = _load_json(surfaces_path)
            surfaces["surfaces"][0]["purpose"] += " Ident marker $Id$."
            _write_json(surfaces_path, surfaces)
            revision = _commit_generated_repository(root)
            surfaces_path.unlink()
            _run_git(root, "checkout", "--", "contracts/surfaces.json")
            self.assertIn(b"$Id:", surfaces_path.read_bytes())
            self.assertEqual("", _run_git(root, "diff", "--name-only"))
            self.produce_release(root, revision)

            result = self.run_bundle(root, revision)

            self.assertEqual(2, result.returncode)
            self.assertIn(
                "raw worktree bytes differ from candidate blobs: contracts/surfaces.json",
                result.stderr,
            )

    def test_candidate_must_not_track_lifecycle_output_paths(self) -> None:
        with _generated_repository() as root:
            _install_release_evidence_producer(root)
            _install_release_bundle_producer(root)
            _write_json(
                root / "product/release-bundle-index.json",
                {
                    "schemaVersion": 1,
                    "currentRecordId": None,
                    "records": [],
                },
            )
            revision = _commit_generated_repository(root)
            self.produce_release(root, revision)

            result = self.run_bundle(root, revision)

            self.assertEqual(2, result.returncode)
            self.assertIn(
                "candidate tracks lifecycle output paths: product/release-bundle-index.json",
                result.stderr,
            )

    def test_dangling_index_symlink_is_rejected_without_mutation(self) -> None:
        with _generated_repository() as root:
            revision = self.prepare_approved_release(root)
            bundle_path = root / "contracts/release-bundle.json"
            bundle_before = bundle_path.read_bytes()
            index_path = root / "product/release-bundle-index.json"
            try:
                index_path.symlink_to("missing-release-bundle-index.json")
            except OSError as exc:
                self.skipTest(f"symbolic links are unavailable: {exc}")

            result = self.run_bundle(root, revision)

            self.assertEqual(2, result.returncode)
            self.assertIn(
                "release bundle index must be a regular non-symbolic file",
                result.stderr,
            )
            self.assertTrue(index_path.is_symlink())
            self.assertEqual(bundle_before, bundle_path.read_bytes())

    def test_index_identity_must_match_retained_bundle_metadata(self) -> None:
        with _generated_repository() as root:
            revision = self.prepare_approved_release(root)
            self.assertEqual(0, self.run_bundle(root, revision).returncode)
            index_path = root / "product/release-bundle-index.json"
            index = _load_json(index_path)
            old_id = index["currentRecordId"]
            replacement_digit = "0" if old_id[-1] != "0" else "1"
            new_id = old_id[:-1] + replacement_digit
            old_path = root / f"product/release-bundle-records/{old_id}.json"
            new_path = root / f"product/release-bundle-records/{new_id}.json"
            old_path.rename(new_path)
            record = index["records"][0]
            record["id"] = new_id
            record["path"] = f"product/release-bundle-records/{new_id}.json"
            index["currentRecordId"] = new_id
            _write_json(index_path, index)

            result = self.run_bundle(
                root,
                revision,
                "--activate-record",
                new_id,
            )

            self.assertEqual(2, result.returncode)
            self.assertIn(
                f"release bundle record {new_id}: provenance id does not match index",
                result.stderr,
            )

    def test_every_successor_chain_must_terminate_at_current_record(self) -> None:
        with _generated_repository() as root:
            revision = self.prepare_approved_release(root)
            for _ in range(3):
                result = self.run_bundle(root, revision)
                self.assertEqual(0, result.returncode, result.stderr)
            index_path = root / "product/release-bundle-index.json"
            index = _load_json(index_path)
            first, second, third = index["records"]
            self.assertEqual(third["id"], index["currentRecordId"])
            first["status"] = "superseded"
            first["supersededBy"] = second["id"]
            second["status"] = "superseded"
            second["supersededBy"] = first["id"]
            _write_json(index_path, index)

            result = self.run_bundle(root, revision)

            self.assertEqual(2, result.returncode)
            self.assertIn(
                f"release bundle record {first['id']}: successor chain contains a cycle",
                result.stderr,
            )

    def test_index_publication_failure_restores_bundle_and_new_record(self) -> None:
        with _generated_repository() as root:
            revision = self.prepare_approved_release(root)
            bundle_path = root / "contracts/release-bundle.json"
            bundle_before = bundle_path.read_bytes()
            temporary_index = root / "product/release-bundle-index.json.tmp"
            temporary_index.mkdir(parents=True)

            result = self.run_bundle(root, revision)

            self.assertEqual(2, result.returncode)
            self.assertIn("cannot publish release bundle index", result.stderr)
            self.assertEqual(bundle_before, bundle_path.read_bytes())
            self.assertFalse(
                (root / "product/release-bundle-index.json").exists()
            )
            records_dir = root / "product/release-bundle-records"
            self.assertFalse(
                records_dir.exists()
                and any(path.suffix == ".json" for path in records_dir.iterdir())
            )


class GeneratedReleaseBundleReviewRegressionScopeTests(unittest.TestCase):
    def test_review_regression_suite_is_template_maintainer_only(self) -> None:
        source_is_template = _is_template_maintainer_source()
        suite_is_skipped = bool(
            getattr(
                GeneratedReleaseBundleReviewRegressionTests,
                "__unittest_skip__",
                False,
            )
        )
        self.assertEqual(not source_is_template, suite_is_skipped)


if __name__ == "__main__":
    unittest.main()
