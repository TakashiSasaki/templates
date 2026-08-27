from __future__ import annotations

import contextlib
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
RELEASE_DESCRIPTOR = ROOT / "release" / "composition-installer.json"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


installer = load_module("install_composition_skill", SCRIPT)


def add_file(archive: tarfile.TarFile, name: str, content: bytes) -> None:
    member = tarfile.TarInfo(name)
    member.size = len(content)
    archive.addfile(member, io.BytesIO(content))


def required_relative_paths() -> tuple[str, ...]:
    return tuple(
        item.as_posix()
        for item in sorted(installer.REQUIRED_SKILL_PATHS, key=lambda item: item.as_posix())
    )


def add_required_files(archive: tarfile.TarFile, prefix: str) -> None:
    for relative in required_relative_paths():
        content = (
            b"---\nname: composition\n---\n"
            if relative == "SKILL.md"
            else b"{}\n"
            if relative == "runtime-manifest.json"
            else b"# runnable test fixture\n"
        )
        add_file(archive, f"{prefix}/{relative}", content)


def skill_archive(*, extra_members: list[tarfile.TarInfo] | None = None) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        prefix = "templates-source/skills/composition"
        add_required_files(archive, prefix)
        add_file(archive, f"{prefix}/README.md", b"# Composition skill\n")
        add_file(archive, "templates-source/README.md", b"outside skill\n")
        for member in extra_members or []:
            archive.addfile(member)
    return buffer.getvalue()


class NoLengthHeaders:
    def get(self, _key: str):
        return None


class BytesResponse:
    headers = NoLengthHeaders()

    def __init__(self, data: bytes):
        self.data = data

    def __enter__(self):
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self, amount: int = -1) -> bytes:
        return self.data if amount < 0 else self.data[:amount]


class CompositionRemoteSkillInstallerTests(unittest.TestCase):
    def test_remote_installer_pins_published_skill_source_revision(self) -> None:
        descriptor = json.loads(RELEASE_DESCRIPTOR.read_text(encoding="utf-8"))
        expected = descriptor["skill_source"]["revision"]
        self.assertEqual(installer.TOOLCHAIN_REPOSITORY, "TakashiSasaki/templates")
        self.assertEqual(installer.SKILL_SOURCE_REVISION, expected)
        self.assertIsNotNone(installer.FULL_SHA.fullmatch(installer.SKILL_SOURCE_REVISION))
        self.assertTrue(installer.archive_url().endswith(f"/tar.gz/{expected}"))

    def test_archive_url_rejects_mutable_or_short_revisions(self) -> None:
        for revision in ("composition", "main", "f9508b92"):
            with self.subTest(revision=revision):
                with self.assertRaisesRegex(ValueError, "full lowercase commit SHA"):
                    installer.archive_url(revision)

    def test_extract_selects_complete_composition_skill_subtree(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            destination = root / "skill"
            result = installer.extract_skill_archive(skill_archive(), destination)
            self.assertEqual(result, destination.resolve())
            for relative in required_relative_paths():
                self.assertTrue((destination / relative).is_file(), relative)
            self.assertFalse((root / "README.md").exists())

    def test_extract_rejects_cross_platform_unsafe_paths(self) -> None:
        for name in (
            "templates-source/skills/composition/../outside.txt",
            "templates-source/skills/composition/..\\outside.txt",
            "templates-source/skills/composition/file:stream",
        ):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                traversal = tarfile.TarInfo(name)
                traversal.size = 0
                with self.assertRaisesRegex(RuntimeError, "unsafe path"):
                    installer.extract_skill_archive(
                        skill_archive(extra_members=[traversal]),
                        Path(temporary) / "skill",
                    )

    def test_extract_rejects_links_unsupported_types_duplicates_and_multiple_roots(self) -> None:
        cases: list[tuple[tarfile.TarInfo, str]] = []
        link = tarfile.TarInfo("templates-source/skills/composition/link")
        link.type = tarfile.SYMTYPE
        link.linkname = "../../outside"
        cases.append((link, "links are not allowed"))
        fifo = tarfile.TarInfo("templates-source/skills/composition/fifo")
        fifo.type = tarfile.FIFOTYPE
        cases.append((fifo, "unsupported member type"))
        duplicate = tarfile.TarInfo("templates-source/skills/composition/SKILL.md")
        duplicate.size = 0
        cases.append((duplicate, "duplicate path.*SKILL.md"))
        second_root = tarfile.TarInfo("templates-other/skills/composition/extra.txt")
        second_root.size = 0
        cases.append((second_root, "multiple top-level roots"))
        for member, message in cases:
            with self.subTest(message=message), tempfile.TemporaryDirectory() as temporary:
                with self.assertRaisesRegex(RuntimeError, message):
                    installer.extract_skill_archive(
                        skill_archive(extra_members=[member]),
                        Path(temporary) / "skill",
                    )

    def test_extract_rejects_unsafe_archive_root_token(self) -> None:
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
            add_file(
                archive,
                "bad:root/skills/composition/SKILL.md",
                b"---\nname: composition\n---\n",
            )
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(RuntimeError, "unsafe root prefix"):
                installer.extract_skill_archive(buffer.getvalue(), Path(temporary) / "skill")

    def test_extract_rejects_skill_size_limit_exceeded(self) -> None:
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
            prefix = "templates-source/skills/composition"
            add_required_files(archive, prefix)
            add_file(archive, f"{prefix}/oversized.bin", b"x" * installer.SKILL_LIMIT)
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(RuntimeError, "extracted skill exceeds the size limit"):
                installer.extract_skill_archive(buffer.getvalue(), Path(temporary) / "skill")

    def test_extract_requires_complete_regular_runnable_skill_contract(self) -> None:
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
            add_file(
                archive,
                "templates-source/skills/composition/SKILL.md",
                b"---\nname: composition\n---\n",
            )
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(RuntimeError, "missing required files"):
                installer.extract_skill_archive(buffer.getvalue(), Path(temporary) / "skill")

        buffer = io.BytesIO()
        prefix = "templates-source/skills/composition"
        with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
            for relative in required_relative_paths():
                if relative == "SKILL.md":
                    directory = tarfile.TarInfo(f"{prefix}/{relative}")
                    directory.type = tarfile.DIRTYPE
                    archive.addfile(directory)
                else:
                    add_file(archive, f"{prefix}/{relative}", b"x")
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(RuntimeError, "missing required files.*SKILL.md"):
                installer.extract_skill_archive(buffer.getvalue(), Path(temporary) / "skill")

    def test_extract_normalizes_tar_errors_from_iteration_and_extraction(self) -> None:
        class BrokenIterationArchive:
            def __enter__(self):
                return self

            def __exit__(self, *args: object) -> None:
                return None

            def getmembers(self):
                raise tarfile.ReadError("broken member table")

        with tempfile.TemporaryDirectory() as temporary, mock.patch.object(
            installer.tarfile, "open", return_value=BrokenIterationArchive()
        ):
            with self.assertRaisesRegex(RuntimeError, "unable to read skill archive"):
                installer.extract_skill_archive(b"fake", Path(temporary) / "skill")

        prefix = "templates-source/skills/composition"
        members = []
        for relative in required_relative_paths():
            member = tarfile.TarInfo(f"{prefix}/{relative}")
            member.size = 1
            members.append(member)

        class BrokenExtractionArchive:
            def __enter__(self):
                return self

            def __exit__(self, *args: object) -> None:
                return None

            def getmembers(self):
                return members

            def extractfile(self, _member: tarfile.TarInfo):
                raise tarfile.ReadError("broken payload")

        with tempfile.TemporaryDirectory() as temporary, mock.patch.object(
            installer.tarfile, "open", return_value=BrokenExtractionArchive()
        ):
            with self.assertRaisesRegex(RuntimeError, "unable to read skill archive"):
                installer.extract_skill_archive(b"fake", Path(temporary) / "skill")

    def test_extract_rejects_negative_file_size_and_early_eof(self) -> None:
        prefix = "templates-source/skills/composition"
        negative = tarfile.TarInfo(f"{prefix}/SKILL.md")
        negative.size = -1

        class NegativeArchive:
            def __enter__(self):
                return self

            def __exit__(self, *args: object) -> None:
                return None

            def getmembers(self):
                return [negative]

        with tempfile.TemporaryDirectory() as temporary, mock.patch.object(
            installer.tarfile, "open", return_value=NegativeArchive()
        ):
            with self.assertRaisesRegex(RuntimeError, "invalid file size"):
                installer.extract_skill_archive(b"fake", Path(temporary) / "negative")

        members = []
        for relative in required_relative_paths():
            member = tarfile.TarInfo(f"{prefix}/{relative}")
            member.size = 1
            members.append(member)

        class EarlyEofArchive:
            def __enter__(self):
                return self

            def __exit__(self, *args: object) -> None:
                return None

            def getmembers(self):
                return members

            def extractfile(self, _member: tarfile.TarInfo):
                return io.BytesIO(b"")

        with tempfile.TemporaryDirectory() as temporary, mock.patch.object(
            installer.tarfile, "open", return_value=EarlyEofArchive()
        ):
            with self.assertRaisesRegex(RuntimeError, "member ended early"):
                installer.extract_skill_archive(b"fake", Path(temporary) / "early-eof")

    def test_install_delegates_to_atomic_local_installer_in_isolated_python(self) -> None:
        observed: dict[str, object] = {}

        def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            observed["command"] = command
            observed["check"] = kwargs.get("check")
            self.assertEqual(Path(command[2]).name, "install.py")
            self.assertTrue(Path(command[2]).is_file())
            return subprocess.CompletedProcess(command, 0)

        with tempfile.TemporaryDirectory() as temporary, mock.patch.object(
            installer.subprocess, "run", side_effect=fake_run
        ):
            target = Path(temporary) / "installed" / "composition"
            installer.install_downloaded_skill(skill_archive(), target, replace=True)

        command = observed["command"]
        assert isinstance(command, list)
        self.assertEqual(command[0:2], [sys.executable, "-I"])
        self.assertEqual(command[3:], [str(target), "--replace"])
        self.assertIs(observed["check"], True)

    def test_download_limits_and_empty_archive_fail_closed(self) -> None:
        class Headers:
            def __init__(self, value: str | None):
                self.value = value

            def get(self, _key: str):
                return self.value

        class Response(BytesResponse):
            def __init__(self, data: bytes, length: str | None):
                super().__init__(data)
                self.headers = Headers(length)

        for data, length, message in (
            (b"unused", str(installer.ARCHIVE_LIMIT + 1), "download size limit"),
            (b"unused", "abc", "invalid Content-Length"),
            (b"unused", "-10", "download size limit"),
            (b"x" * (installer.ARCHIVE_LIMIT + 1), None, "download size limit"),
            (b"", None, "download was empty"),
        ):
            with self.subTest(message=message):
                def opener(_request: object, *, timeout: int, data=data, length=length):
                    self.assertEqual(timeout, 30)
                    return Response(data, length)

                with self.assertRaisesRegex(RuntimeError, message):
                    installer.download_archive(opener=opener)

    def test_main_cli_exit_codes_and_error_formatting(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "composition"
            stdout = io.StringIO()
            with mock.patch.object(installer, "download_archive", return_value=b"archive"), mock.patch.object(
                installer, "install_downloaded_skill"
            ) as install, contextlib.redirect_stdout(stdout):
                self.assertEqual(installer.main([str(target)]), 0)
            install.assert_called_once_with(b"archive", target.absolute(), replace=False)
            self.assertIn("Installed Composition skill", stdout.getvalue())

            stderr = io.StringIO()
            with mock.patch.object(
                installer, "download_archive", side_effect=RuntimeError("broken download")
            ), contextlib.redirect_stderr(stderr):
                self.assertEqual(installer.main([str(target)]), 1)
            self.assertIn(
                "Composition remote installer error: broken download",
                stderr.getvalue(),
            )


if __name__ == "__main__":
    unittest.main()
