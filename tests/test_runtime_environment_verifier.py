from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import verify_runtime_environment as runtime  # noqa: E402


class FakeDistribution:
    def __init__(self, metadata: object, version: str = "1.0") -> None:
        self.metadata = metadata
        self.version = version


class RuntimeEnvironmentVerifierTests(unittest.TestCase):
    def test_supported_cpython_versions_are_accepted(self) -> None:
        for version in ((3, 11), (3, 12), (3, 13), (3, 14)):
            with self.subTest(version=version):
                runtime.verify_interpreter("cpython", version)

    def test_non_cpython_and_out_of_range_versions_are_rejected(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "requires CPython"):
            runtime.verify_interpreter("pypy", (3, 12))
        for version in ((3, 10), (3, 15)):
            with self.subTest(version=version):
                with self.assertRaisesRegex(RuntimeError, "unsupported CPython version"):
                    runtime.verify_interpreter("cpython", version)

    def test_distribution_set_allows_only_bootstrap_extras(self) -> None:
        expected = {"attrs": "26.1.0", "referencing": "0.37.0"}
        installed = {
            **expected,
            "pip": "26.2.1",
            "setuptools": "80.9.0",
            "wheel": "0.46.1",
        }
        runtime.verify_distribution_set(expected, installed)

    def test_distribution_set_reports_missing_dependency(self) -> None:
        expected = {"attrs": "26.1.0", "referencing": "0.37.0"}
        with self.assertRaisesRegex(RuntimeError, r"missing=referencing"):
            runtime.verify_distribution_set(expected, {"attrs": "26.1.0"})

    def test_distribution_set_reports_unexpected_distribution(self) -> None:
        expected = {"attrs": "26.1.0"}
        installed = {"attrs": "26.1.0", "requests": "2.32.5"}
        with self.assertRaisesRegex(RuntimeError, r"unexpected=requests"):
            runtime.verify_distribution_set(expected, installed)

    def test_distribution_set_reports_version_mismatch(self) -> None:
        expected = {"attrs": "26.1.0"}
        installed = {"attrs": "25.1.0"}
        with self.assertRaisesRegex(
            RuntimeError,
            r"version-mismatch=attrs:25\.1\.0!=26\.1\.0",
        ):
            runtime.verify_distribution_set(expected, installed)

    def test_parse_lock_rejects_duplicate_normalized_distribution(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            lock = Path(temporary) / "runtime.lock"
            lock.write_text("rpds_py===1.0\nrpds-py===1.0\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "duplicate distribution"):
                runtime.parse_lock(lock)

    def test_installed_distributions_rejects_missing_metadata(self) -> None:
        distribution = FakeDistribution(None)
        with mock.patch.object(
            runtime.importlib.metadata,
            "distributions",
            return_value=[distribution],
        ):
            with self.assertRaisesRegex(RuntimeError, "missing Name metadata"):
                runtime.installed_distributions()

    def test_installed_distributions_rejects_missing_name(self) -> None:
        distribution = FakeDistribution({})
        with mock.patch.object(
            runtime.importlib.metadata,
            "distributions",
            return_value=[distribution],
        ):
            with self.assertRaisesRegex(RuntimeError, "missing Name metadata"):
                runtime.installed_distributions()

    def test_installed_distributions_rejects_duplicate_normalized_names(self) -> None:
        distributions = [
            FakeDistribution({"Name": "rpds_py"}),
            FakeDistribution({"Name": "rpds-py"}),
        ]
        with mock.patch.object(
            runtime.importlib.metadata,
            "distributions",
            return_value=distributions,
        ):
            with self.assertRaisesRegex(RuntimeError, "duplicate installed distribution"):
                runtime.installed_distributions()


if __name__ == "__main__":
    unittest.main()
