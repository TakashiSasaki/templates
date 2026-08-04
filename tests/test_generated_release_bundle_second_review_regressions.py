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


@unittest.skipUnless(
    _is_template_maintainer_source(),
    "template-maintainer-only generated release bundle second review regressions",
)
class GeneratedReleaseBundleSecondReviewRegressionTests(unittest.TestCase):
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

    def run_bundle(self, root: Path, revision: str, *arguments: str):
        return _run_generated_python(
            root,
            "-I",
            "product/produce_release_bundle.py",
            "--revision",
            revision,
            *arguments,
        )

    def prepare_approved_release(self, root: Path) -> str:
        revision = self.install_and_commit(root)
        self.produce_release(root, revision)
        return revision

    def test_failed_atomic_write_removes_only_its_new_temporary(self) -> None:
        with _generated_repository() as root:
            _install_release_evidence_producer(root)
            _install_release_bundle_producer(root)
            producer = root / "product/produce_release_bundle.py"
            _inject_after_line(
                producer,
                "temporary.write_bytes(content)",
                [
                    "if path == INDEX_PATH:",
                    "    raise OSError('injected failure after temporary write')",
                ],
            )
            revision = _commit_generated_repository(root)
            self.produce_release(root, revision)
            bundle_path = root / "contracts/release-bundle.json"
            bundle_before = bundle_path.read_bytes()

            result = self.run_bundle(root, revision)

            self.assertEqual(2, result.returncode)
            self.assertIn("cannot publish release bundle index", result.stderr)
            temporary = root / "product/release-bundle-index.json.tmp"
            self.assertFalse(temporary.exists() or temporary.is_symlink())
            self.assertEqual(bundle_before, bundle_path.read_bytes())
            self.assertFalse((root / "product/release-bundle-index.json").exists())
            records = root / "product/release-bundle-records"
            self.assertFalse(
                records.exists()
                and any(path.suffix == ".json" for path in records.iterdir())
            )

    def test_local_clean_filter_is_never_executed(self) -> None:
        with _generated_repository() as root:
            _install_release_evidence_producer(root)
            _install_release_bundle_producer(root)
            (root / ".gitattributes").write_text(
                "contracts/surfaces.json filter=reviewfilter\n",
                encoding="utf-8",
            )
            revision = _commit_generated_repository(root)
            self.produce_release(root, revision)
            marker = root / "product/clean-filter-executed"
            _run_git(
                root,
                "config",
                "filter.reviewfilter.clean",
                "sh -c 'printf executed > product/clean-filter-executed; cat'",
            )

            result = self.run_bundle(root, revision)

            self.assertEqual(
                0,
                result.returncode,
                f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
            )
            self.assertFalse(marker.exists())

    def test_concurrent_producers_serialize_lifecycle_updates(self) -> None:
        with _generated_repository() as root:
            _install_release_evidence_producer(root)
            _install_release_bundle_producer(root)
            producer = root / "product/produce_release_bundle.py"
            _inject_after_line(producer, "index = load_index()", ["time.sleep(0.5)"])
            revision = _commit_generated_repository(root)
            self.produce_release(root, revision)
            command = [
                sys.executable,
                "-I",
                "product/produce_release_bundle.py",
                "--revision",
                revision,
            ]
            first = subprocess.Popen(
                command,
                cwd=root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            second = subprocess.Popen(
                command,
                cwd=root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            first_stdout, first_stderr = first.communicate(timeout=20)
            second_stdout, second_stderr = second.communicate(timeout=20)

            self.assertEqual(
                0,
                first.returncode,
                f"stdout:\n{first_stdout}\nstderr:\n{first_stderr}",
            )
            self.assertEqual(
                0,
                second.returncode,
                f"stdout:\n{second_stdout}\nstderr:\n{second_stderr}",
            )
            retry = self.run_bundle(root, revision)
            self.assertEqual(
                0,
                retry.returncode,
                f"stdout:\n{retry.stdout}\nstderr:\n{retry.stderr}",
            )
            index = _load_json(root / "product/release-bundle-index.json")
            self.assertEqual(3, len(index["records"]))

    def test_lifecycle_schema_version_requires_exact_integer(self) -> None:
        for malformed in (True, 1.0):
            with self.subTest(schema_version=repr(malformed)):
                with _generated_repository() as root:
                    revision = self.prepare_approved_release(root)
                    initial = self.run_bundle(root, revision)
                    self.assertEqual(0, initial.returncode, initial.stderr)
                    index_path = root / "product/release-bundle-index.json"
                    index = _load_json(index_path)
                    index["schemaVersion"] = malformed
                    _write_json(index_path, index)

                    result = self.run_bundle(root, revision)

                    self.assertEqual(2, result.returncode)
                    self.assertIn("release bundle index is malformed", result.stderr)


class GeneratedReleaseBundleSecondReviewRegressionScopeTests(unittest.TestCase):
    def test_second_review_suite_is_template_maintainer_only(self) -> None:
        source_is_template = _is_template_maintainer_source()
        suite_is_skipped = bool(
            getattr(
                GeneratedReleaseBundleSecondReviewRegressionTests,
                "__unittest_skip__",
                False,
            )
        )
        self.assertEqual(not source_is_template, suite_is_skipped)


if __name__ == "__main__":
    unittest.main()
