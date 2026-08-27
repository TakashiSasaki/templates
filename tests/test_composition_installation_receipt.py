from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "install_composition_skill.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


installer = load_module("composition_installation_receipt_installer", SCRIPT)


def add_file(archive: tarfile.TarFile, name: str, content: bytes) -> None:
    member = tarfile.TarInfo(name)
    member.size = len(content)
    archive.addfile(member, io.BytesIO(content))


def skill_archive(*, include_reserved_receipt: bool = False) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        prefix = "templates-source/skills/composition"
        for relative in sorted(installer.REQUIRED_SKILL_PATHS, key=lambda item: item.as_posix()):
            content = (
                b"---\nname: composition\n---\n"
                if relative.as_posix() == "SKILL.md"
                else b"{}\n"
                if relative.as_posix() == "runtime-manifest.json"
                else b"# runnable test fixture\n"
            )
            add_file(archive, f"{prefix}/{relative.as_posix()}", content)
        if include_reserved_receipt:
            add_file(
                archive,
                f"{prefix}/installation-receipt.json",
                b'{"schema_version":1}\n',
            )
    return buffer.getvalue()


class CompositionInstallationReceiptTests(unittest.TestCase):
    def test_remote_install_stages_exact_skill_source_receipt_before_atomic_install(self) -> None:
        observed: dict[str, object] = {}

        def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            source = Path(command[2]).parents[1]
            receipt = source / "installation-receipt.json"
            self.assertTrue(receipt.is_file())
            observed["receipt"] = json.loads(receipt.read_text(encoding="utf-8"))
            observed["command"] = list(command)
            return subprocess.CompletedProcess(command, 0)

        with tempfile.TemporaryDirectory() as temporary, mock.patch.object(
            installer.subprocess, "run", side_effect=fake_run
        ):
            target = Path(temporary) / "installed" / "composition"
            installer.install_downloaded_skill(
                skill_archive(),
                target,
                replace=True,
            )

        self.assertEqual(
            observed["receipt"],
            {
                "schema_version": 1,
                "source": {
                    "repository": installer.TOOLCHAIN_REPOSITORY,
                    "revision": installer.SKILL_SOURCE_REVISION,
                },
            },
        )
        command = observed["command"]
        assert isinstance(command, list)
        self.assertEqual(command[0:2], [sys.executable, "-I"])
        self.assertEqual(command[3:], [str(target), "--replace"])

    def test_archive_cannot_supply_or_spoof_reserved_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(
                RuntimeError,
                "must not provide the reserved installation receipt path",
            ):
                installer.extract_skill_archive(
                    skill_archive(include_reserved_receipt=True),
                    Path(temporary) / "skill",
                )

    def test_receipt_payload_rejects_mutable_revision_and_other_repository(self) -> None:
        with self.assertRaisesRegex(ValueError, "full lowercase SHA"):
            installer.installation_receipt_payload(revision="composition")
        with self.assertRaisesRegex(ValueError, "repository is unsupported"):
            installer.installation_receipt_payload(repository="example/other")


if __name__ == "__main__":
    unittest.main()
