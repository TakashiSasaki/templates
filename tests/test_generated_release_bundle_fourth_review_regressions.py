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
)


def _inject_after_line(path: Path, stripped_line: str, inserted: list[str]) -> None:
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    for position, line in enumerate(lines):
        if line.strip() != stripped_line:
            continue
        indentation = line[: len(line) - len(line.lstrip())]
        injected = [f"{indentation}{text}\n" for text in inserted]
        lines[position + 1 : position + 1] = injected
        path.write_text("".join(lines), encoding="utf-8")
        return
    raise AssertionError(f"producer injection point not found: {stripped_line}")


def _record_files(root: Path) -> list[Path]:
    records = root / "product/release-bundle-records"
    if not records.exists():
        return []
    return sorted(path for path in records.iterdir() if path.suffix == ".json")


@unittest.skipUnless(
    _is_template_maintainer_source(),
    "template-maintainer-only generated release bundle fourth review regressions",
)
class GeneratedReleaseBundleFourthReviewRegressionTests(unittest.TestCase):
    def install_and_commit(self, root: Path) -> str:
        _install_release_evidence_producer(root)
        _install_release_bundle_producer(root)
        return _commit_generated_repository(root)

    def produce_release(self, root: Path, revision: str) -> None:
        result = _run_generated_python(
            root,
            "-I",
            "product/produce_release_evidence.py",
            "--revision",
            revision,
        )
        self.assertEqual(
            0,
            result.returncode,
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )

    def run_bundle(self, root: Path, revision: str, *arguments: str):
        return _run_generated_python(
            root,
            "-I",
            "product/produce_release_bundle.py",
            "--revision",
            revision,
            *arguments,
        )

    def test_symlinked_producer_leaf_is_rejected_before_root_selection(self) -> None:
        with _generated_repository() as invoked_root:
            with _generated_repository() as target_root:
                invoked_revision = self.install_and_commit(invoked_root)
                target_revision = self.install_and_commit(target_root)
                self.assertEqual(invoked_revision, target_revision)
                self.produce_release(target_root, target_revision)

                invoked_producer = invoked_root / "product/produce_release_bundle.py"
                invoked_producer.unlink()
                invoked_producer.symlink_to(
                    target_root / "product/produce_release_bundle.py"
                )

                result = self.run_bundle(invoked_root, invoked_revision)

                self.assertEqual(2, result.returncode)
                self.assertIn(
                    "producer path must be a regular non-symbolic file",
                    result.stderr,
                )
                self.assertFalse(
                    (target_root / "product/release-bundle-index.json").exists()
                )
                self.assertEqual([], _record_files(target_root))

    def test_current_bundle_replacement_preserves_candidate_mode(self) -> None:
        with _generated_repository() as root:
            _install_release_evidence_producer(root)
            _install_release_bundle_producer(root)
            bundle = root / "contracts/release-bundle.json"
            bundle.chmod(bundle.stat().st_mode | 0o111)
            revision = _commit_generated_repository(root)
            self.produce_release(root, revision)

            initial = self.run_bundle(root, revision)
            self.assertEqual(
                0,
                initial.returncode,
                f"stdout:\n{initial.stdout}\nstderr:\n{initial.stderr}",
            )
            self.assertNotEqual(0, bundle.stat().st_mode & 0o111)

            retry = self.run_bundle(root, revision)
            self.assertEqual(
                0,
                retry.returncode,
                f"stdout:\n{retry.stdout}\nstderr:\n{retry.stderr}",
            )
            self.assertNotEqual(0, bundle.stat().st_mode & 0o111)

    def test_validator_launch_error_rolls_back_creation_and_activation(self) -> None:
        with _generated_repository() as root:
            _install_release_evidence_producer(root)
            _install_release_bundle_producer(root)
            producer = root / "product/produce_release_bundle.py"
            _inject_after_line(
                producer,
                "def validate_bundle(revision: str) -> tuple[bool, str]:",
                [
                    "    if (GIT_DIR / 'fourth-review-validator-oserror').exists():",
                    "        raise OSError('injected validator launch failure')",
                ],
            )
            revision = _commit_generated_repository(root)
            self.produce_release(root, revision)
            bundle = root / "contracts/release-bundle.json"
            bundle_before = bundle.read_bytes()
            (root / ".git/fourth-review-validator-oserror").write_text(
                "fail\n",
                encoding="utf-8",
            )

            result = self.run_bundle(root, revision)

            self.assertEqual(2, result.returncode)
            self.assertIn("cannot execute release bundle validator", result.stderr)
            self.assertEqual(bundle_before, bundle.read_bytes())
            self.assertFalse((root / "product/release-bundle-index.json").exists())
            self.assertEqual([], _record_files(root))

        with _generated_repository() as root:
            _install_release_evidence_producer(root)
            _install_release_bundle_producer(root)
            producer = root / "product/produce_release_bundle.py"
            _inject_after_line(
                producer,
                "def validate_bundle(revision: str) -> tuple[bool, str]:",
                [
                    "    if (GIT_DIR / 'fourth-review-validator-oserror').exists():",
                    "        raise OSError('injected validator launch failure')",
                ],
            )
            revision = _commit_generated_repository(root)
            self.produce_release(root, revision)
            first = self.run_bundle(root, revision)
            second = self.run_bundle(root, revision)
            self.assertEqual(0, first.returncode, first.stderr)
            self.assertEqual(0, second.returncode, second.stderr)
            index_path = root / "product/release-bundle-index.json"
            bundle = root / "contracts/release-bundle.json"
            index_before = index_path.read_bytes()
            bundle_before = bundle.read_bytes()
            index = _load_json(index_path)
            first_record = index["records"][0]["id"]
            (root / ".git/fourth-review-validator-oserror").write_text(
                "fail\n",
                encoding="utf-8",
            )

            result = self.run_bundle(
                root,
                revision,
                "--activate-record",
                first_record,
            )

            self.assertEqual(2, result.returncode)
            self.assertIn("cannot execute release bundle validator", result.stderr)
            self.assertEqual(bundle_before, bundle.read_bytes())
            self.assertEqual(index_before, index_path.read_bytes())

    def test_candidate_drift_before_publication_rolls_back(self) -> None:
        with _generated_repository() as root:
            _install_release_evidence_producer(root)
            _install_release_bundle_producer(root)
            producer = root / "product/produce_release_bundle.py"
            _inject_after_line(
                producer,
                "def active_artifacts() -> list[dict[str, str]]:",
                [
                    "    drift = ROOT / 'contracts/surfaces.json'",
                    "    drift.write_bytes(drift.read_bytes() + b' ')",
                ],
            )
            revision = _commit_generated_repository(root)
            self.produce_release(root, revision)
            bundle = root / "contracts/release-bundle.json"
            bundle_before = bundle.read_bytes()

            result = self.run_bundle(root, revision)

            self.assertEqual(2, result.returncode)
            self.assertIn(
                "raw worktree bytes differ from candidate blobs",
                result.stderr,
            )
            self.assertEqual(bundle_before, bundle.read_bytes())
            self.assertFalse((root / "product/release-bundle-index.json").exists())
            self.assertEqual([], _record_files(root))


class GeneratedReleaseBundleFourthReviewRegressionScopeTests(unittest.TestCase):
    def test_fourth_review_suite_is_template_maintainer_only(self) -> None:
        source_is_template = _is_template_maintainer_source()
        suite_is_skipped = bool(
            getattr(
                GeneratedReleaseBundleFourthReviewRegressionTests,
                "__unittest_skip__",
                False,
            )
        )
        self.assertEqual(not source_is_template, suite_is_skipped)


if __name__ == "__main__":
    unittest.main()
