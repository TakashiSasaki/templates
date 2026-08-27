from __future__ import annotations

import contextlib
import importlib.util
import io
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_composition_skill_installer_release.py"


def load_verifier():
    spec = importlib.util.spec_from_file_location(
        "composition_skill_installer_release_failure_verifier", SCRIPT
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


verifier = load_verifier()


class CompositionSkillInstallerReleaseFailureTests(unittest.TestCase):
    def test_verify_rejects_installer_skill_source_pin_mismatch(self) -> None:
        original = verifier.require_file

        def mismatched_installer(revision: str, path: str) -> bytes:
            if path == "scripts/install_composition_skill.py":
                return (
                    'TOOLCHAIN_REPOSITORY = "TakashiSasaki/templates"\n'
                    'SKILL_SOURCE_REVISION = "0000000000000000000000000000000000000000"\n'
                ).encode("utf-8")
            return original(revision, path)

        with mock.patch.object(
            verifier, "require_file", side_effect=mismatched_installer
        ), mock.patch.object(verifier, "require_sha256", return_value="0" * 64):
            with self.assertRaisesRegex(
                ValueError,
                "installer skill source revision differs from release descriptor",
            ):
                verifier.verify()

    def test_require_sha256_rejects_installer_digest_mismatch(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "pinned installer SHA-256 mismatch: expected .* got ",
        ):
            verifier.require_sha256(b"tampered-installer\n", "0" * 64, "pinned installer")

    def test_verify_rejects_runtime_lock_digest_mismatch(self) -> None:
        original = verifier.require_file

        def mismatched_runtime_lock(revision: str, path: str) -> bytes:
            if path == "requirements-runtime.lock":
                return b"not-the-pinned-runtime-lock\n"
            return original(revision, path)

        with mock.patch.object(verifier, "require_file", side_effect=mismatched_runtime_lock):
            with self.assertRaisesRegex(
                ValueError,
                "toolchain runtime lock digest differs from skill runtime manifest",
            ):
                verifier.verify()

    def test_main_cli_success_and_failure_exit_codes(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            self.assertEqual(verifier.main(["--git-ref", "HEAD"]), 0)
        self.assertIn("Composition installer release is synchronized", stdout.getvalue())

        stderr = io.StringIO()
        with mock.patch.object(
            verifier, "verify", side_effect=ValueError("bad pin")
        ), contextlib.redirect_stderr(stderr):
            self.assertEqual(verifier.main(["--git-ref", "HEAD"]), 1)
        self.assertIn(
            "Composition installer release verification error: bad pin",
            stderr.getvalue(),
        )


if __name__ == "__main__":
    unittest.main()
