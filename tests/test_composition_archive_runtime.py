from __future__ import annotations

import hashlib
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
RUNTIME_PATH = ROOT / "skills" / "composition" / "scripts" / "runtime.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


runtime = load_module("composition_archive_runtime", RUNTIME_PATH)


def archive_bytes(
    files: dict[str, bytes],
    *,
    extra_members: list[tarfile.TarInfo] | None = None,
) -> bytes:
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w:gz") as archive:
        root = tarfile.TarInfo("templates-test/")
        root.type = tarfile.DIRTYPE
        archive.addfile(root)
        for relative, data in files.items():
            member = tarfile.TarInfo(f"templates-test/{relative}")
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))
        for member in extra_members or []:
            archive.addfile(member)
    return stream.getvalue()


def required_files() -> dict[str, bytes]:
    return {
        path: (b"attrs===1\n" if path == "requirements-runtime.lock" else b"# test\n")
        for path in runtime.REQUIRED_SNAPSHOT_PATHS
    }


class CompositionArchiveRuntimeTests(unittest.TestCase):
    def test_archive_url_requires_full_sha(self) -> None:
        revision = "1" * 40
        self.assertEqual(
            runtime.source_archive_url(revision),
            "https://codeload.github.com/TakashiSasaki/templates/tar.gz/" + revision,
        )
        with self.assertRaisesRegex(runtime.RunnerError, "full lowercase SHA"):
            runtime.source_archive_url("composition")

    def test_extract_snapshot_builds_digest_inventory_without_git_metadata(self) -> None:
        files = required_files()
        files["catalog/catalog.json"] = b"{}\n"
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "source"
            inventory = runtime.extract_source_snapshot(
                archive_bytes(files),
                destination,
                "1" * 40,
            )
            self.assertEqual(
                inventory["catalog/catalog.json"],
                hashlib.sha256(b"{}\n").hexdigest(),
            )
            self.assertFalse((destination / ".git").exists())
            self.assertEqual(
                (destination / "catalog" / "catalog.json").read_bytes(),
                b"{}\n",
            )

    def test_extract_snapshot_rejects_symlink(self) -> None:
        link = tarfile.TarInfo("templates-test/link")
        link.type = tarfile.SYMTYPE
        link.linkname = "requirements-runtime.lock"
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(runtime.RunnerError, "symbolic and hard links"):
                runtime.extract_source_snapshot(
                    archive_bytes(required_files(), extra_members=[link]),
                    Path(temporary) / "source",
                    "1" * 40,
                )

    def test_extract_snapshot_rejects_portable_case_collision(self) -> None:
        files = required_files()
        files["Case.txt"] = b"a"
        files["case.txt"] = b"b"
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(runtime.RunnerError, "portable path collision"):
                runtime.extract_source_snapshot(
                    archive_bytes(files),
                    Path(temporary) / "source",
                    "1" * 40,
                )

    def test_extract_snapshot_rejects_windows_unsafe_path_components(self) -> None:
        for relative in (
            "NUL",
            "con.txt",
            "COM¹.txt",
            "LPT²",
            "trailing.",
            "trailing ",
            "bad?name",
            "bad|name",
            "control\x01name",
        ):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as temporary:
                files = required_files()
                files[relative] = b"unsafe"
                with self.assertRaisesRegex(runtime.RunnerError, "unsafe path"):
                    runtime.extract_source_snapshot(
                        archive_bytes(files),
                        Path(temporary) / "source",
                        "1" * 40,
                    )

    def test_run_composer_uses_ephemeral_snapshot_not_source_cache(self) -> None:
        revision = "1" * 40
        files = required_files()
        snapshot = archive_bytes(files)
        observed: dict[str, object] = {}

        def fake_subprocess_run(command, *, env, check):
            context_path = Path(env[runtime.SOURCE_CONTEXT_ENV])
            observed["context_exists_during_run"] = context_path.is_file()
            observed["context"] = json.loads(context_path.read_text(encoding="utf-8"))
            observed["command"] = list(command)
            return subprocess.CompletedProcess(command, 0)

        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "consumer"
            with (
                mock.patch.object(runtime, "download_source_archive", return_value=snapshot),
                mock.patch.object(
                    runtime._impl,
                    "ensure_runtime_cache",
                    return_value=Path(sys.executable),
                ),
                mock.patch.object(
                    runtime._impl,
                    "ensure_source_cache",
                    side_effect=AssertionError("Git source cache must not be used"),
                ),
                mock.patch.object(runtime.subprocess, "run", side_effect=fake_subprocess_run),
            ):
                status = runtime.run_composer(
                    repository,
                    ["inspect"],
                    explicit_revision=revision,
                )
        self.assertEqual(status, 0)
        self.assertTrue(observed["context_exists_during_run"])
        context = observed["context"]
        assert isinstance(context, dict)
        self.assertEqual(context["revision"], revision)
        self.assertEqual(context["repository"], "TakashiSasaki/templates")


if __name__ == "__main__":
    unittest.main()
