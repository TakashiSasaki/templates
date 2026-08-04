from __future__ import annotations

import os
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
    "template-maintainer-only generated release bundle fifth review regressions",
)
class GeneratedReleaseBundleFifthReviewRegressionTests(unittest.TestCase):
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

    def run_bundle(self, root: Path, revision: str):
        return _run_generated_python(
            root,
            "-I",
            "product/produce_release_bundle.py",
            "--revision",
            revision,
        )

    def test_atomic_write_collision_preserves_foreign_temporary(self) -> None:
        with _generated_repository() as root:
            _install_release_evidence_producer(root)
            _install_release_bundle_producer(root)
            producer = root / "product/produce_release_bundle.py"
            _inject_after_line(
                producer,
                "temporary_preexisted = temporary.exists() or temporary.is_symlink()",
                [
                    "if path == INDEX_PATH and not temporary_preexisted:",
                    "    temporary.symlink_to('fifth-review-foreign-index-temporary')",
                ],
            )
            revision = _commit_generated_repository(root)
            self.produce_release(root, revision)
            bundle = root / "contracts/release-bundle.json"
            bundle_before = bundle.read_bytes()

            result = self.run_bundle(root, revision)

            self.assertEqual(2, result.returncode)
            self.assertIn("cannot publish release bundle index", result.stderr)
            temporary = root / "product/release-bundle-index.json.tmp"
            self.assertTrue(temporary.is_symlink())
            self.assertEqual(
                "fifth-review-foreign-index-temporary",
                os.readlink(temporary),
            )
            self.assertFalse(
                (root / "product/fifth-review-foreign-index-temporary").exists()
            )
            self.assertEqual(bundle_before, bundle.read_bytes())
            self.assertFalse((root / "product/release-bundle-index.json").exists())
            self.assertEqual([], _record_files(root))


class GeneratedReleaseBundleFifthReviewRegressionScopeTests(unittest.TestCase):
    def test_fifth_review_suite_is_template_maintainer_only(self) -> None:
        source_is_template = _is_template_maintainer_source()
        suite_is_skipped = bool(
            getattr(
                GeneratedReleaseBundleFifthReviewRegressionTests,
                "__unittest_skip__",
                False,
            )
        )
        self.assertEqual(not source_is_template, suite_is_skipped)


if __name__ == "__main__":
    unittest.main()
