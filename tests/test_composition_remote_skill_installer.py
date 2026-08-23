from __future__ import annotations

import contextlib
import importlib.util
import io
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path, PurePosixPath
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "install_composition_skill.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


installer = load_module("install_composition_skill", SCRIPT)


def add_file(archive: tarfile.TarFile, name: str, content: bytes) -> None:
    member = tarfile.TarInfo(name)
    member.size = len(content)
    archive.addfile(member, io.BytesIO(content))


def skill_archive(*, extra_members: list[tarfile.TarInfo] | None = None) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        prefix = "templates-source/skills/composition"
        add_file(archive, f"{prefix}/SKILL.md", b"---\nname: composition\n---\n")
        add_file(archive, f"{prefix}/runtime-manifest.json", b"{}\n")
        add_file(archive, f"{prefix}/scripts/install.py", b"print('installer')\n")
        add_file(archive, f"{prefix}/scripts/run.py", b"print('runner')\n")
        add_file(archive, f"{prefix}/scripts/runtime.py", b"print('runtime')\n")
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
    def test_remote_installer_pins_review_candidate_revision(self) -> None:
        self.assertEqual(installer.TOOLCHAIN_REPOSITORY, "TakashiSasaki/templates")
        self.assertEqual(
            installer.SKILL_SOURCE_REVISION,
            "da2e169e1a650a2150936ca92d49596286e34a30",
        )
        self.assertIsNotNone(installer.FULL_SHA.fullmatch(installer.SKILL_SOURCE_REVISION))
        self.assertTrue(
            installer.archive_url().endswith(
                "/tar.gz/da2e169e1a650a2150936ca92d49596286e34a30"
            )
        )

    def test_archive_url_rejects_mutable_or_short_revisions(self) -> None:
        for revision in ("composition", "main", "da2e169e"):
            with self.subTest(revision=revision):
                with self.assertRaisesRegex(ValueError, "full lowercase commit SHA"):
                    installer.archive_url(revision)

    def test_safe_relative_member_ignores_absolute_paths(self) -> None:
        member = tarfile.TarInfo("/templates-source/skills/composition/SKILL.md")
        self.assertIsNone(installer.safe_relative_member(member))

    def test_extract_selects_only_composition_skill_subtree(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            destination = root / "skill"
            result = installer.extract_skill_archive(skill_archive(), destination)
            self.assertEqual(result, destination.resolve())
            self.assertTrue((destination / "SKILL.md").is_file())
            self.assertTrue((destination / "runtime-manifest.json").is_file())
            self.assertTrue((destination / "scripts" / "install.py").is_file())
            self.assertTrue((destination / "scripts" / "run.py").is_file())
            self.assertTrue((destination / "scripts" / "runtime.py").is_file())
            self.assertFalse((root / "README.md").exists())

    def test_extract_rejects_cross_platform_unsafe_paths(self) -> None:
        names = (
            "templates-source/skills/composition/../outside.txt",
            "templates-source/skills/composition/..\\outside.txt",
            "templates-source/skills/composition/file:stream",
        )
        for name in names:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                traversal = tarfile.TarInfo(name)
                traversal.size = 0
                with self.assertRaisesRegex(RuntimeError, "unsafe path"):
                    installer.extract_skill_archive(
                        skill_archive(extra_members=[traversal]),
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
                installer.extract_skill_archive(
                    buffer.getvalue(), Path(temporary) / "skill"
                )

    def test_extract_rejects_links(self) -> None:
        for member_type in (tarfile.SYMTYPE, tarfile.LNKTYPE):
            with self.subTest(member_type=member_type), tempfile.TemporaryDirectory() as temporary:
                link = tarfile.TarInfo("templates-source/skills/composition/link")
                link.type = member_type
                link.linkname = "../../outside"
                with self.assertRaisesRegex(RuntimeError, "links are not allowed"):
                    installer.extract_skill_archive(
                        skill_archive(extra_members=[link]),
                        Path(temporary) / "skill",
                    )

    def test_extract_rejects_unsupported_member_types(self) -> None:
        fifo = tarfile.TarInfo("templates-source/skills/composition/fifo")
        fifo.type = tarfile.FIFOTYPE
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(RuntimeError, "unsupported member type"):
                installer.extract_skill_archive(
                    skill_archive(extra_members=[fifo]), Path(temporary) / "skill"
                )

    def test_extract_rejects_duplicate_member_paths(self) -> None:
        duplicate = tarfile.TarInfo("templates-source/skills/composition/SKILL.md")
        duplicate.size = 0
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(RuntimeError, "duplicate path.*SKILL.md"):
                installer.extract_skill_archive(
                    skill_archive(extra_members=[duplicate]), Path(temporary) / "skill"
                )

    def test_extract_rejects_multiple_top_level_roots(self) -> None:
        second_root = tarfile.TarInfo("templates-other/skills/composition/extra.txt")
        second_root.size = 0
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(RuntimeError, "multiple top-level roots"):
                installer.extract_skill_archive(
                    skill_archive(extra_members=[second_root]), Path(temporary) / "skill"
                )

    def test_extract_rejects_skill_size_limit_exceeded(self) -> None:
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
            prefix = "templates-source/skills/composition"
            add_file(archive, f"{prefix}/SKILL.md", b"---\nname: composition\n---\n")
            add_file(archive, f"{prefix}/runtime-manifest.json", b"{}\n")
            add_file(archive, f"{prefix}/scripts/install.py", b"x")
            add_file(archive, f"{prefix}/scripts/run.py", b"x")
            add_file(archive, f"{prefix}/scripts/runtime.py", b"x")
            add_file(archive, f"{prefix}/oversized.bin", b"x" * installer.SKILL_LIMIT)
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(RuntimeError, "extracted skill exceeds the size limit"):
                installer.extract_skill_archive(
                    buffer.getvalue(), Path(temporary) / "skill"
                )

    def test_extract_requires_complete_runnable_skill_contract(self) -> None:
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
            add_file(
                archive,
                "templates-source/skills/composition/SKILL.md",
                b"---\nname: composition\n---\n",
            )
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(RuntimeError, "missing required files"):
                installer.extract_skill_archive(
                    buffer.getvalue(),
                    Path(temporary) / "skill",
                )

    def test_extract_requires_required_paths_to_be_regular_files(self) -> None:
        buffer = io.BytesIO()
        prefix = "templates-source/skills/composition"
        with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
            directory = tarfile.TarInfo(f"{prefix}/SKILL.md")
            directory.type = tarfile.DIRTYPE
            archive.addfile(directory)
            add_file(archive, f"{prefix}/runtime-manifest.json", b"{}\n")
            add_file(archive, f"{prefix}/scripts/install.py", b"x")
            add_file(archive, f"{prefix}/scripts/run.py", b"x")
            add_file(archive, f"{prefix}/scripts/runtime.py", b"x")
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(RuntimeError, "missing required files.*SKILL.md"):
                installer.extract_skill_archive(
                    buffer.getvalue(), Path(temporary) / "skill"
                )

    def test_extract_normalizes_tar_errors_from_member_iteration(self) -> None:
        class BrokenArchive:
            def __enter__(self):
                return self

            def __exit__(self, *args: object) -> None:
                return None

            def getmembers(self):
                raise tarfile.ReadError("broken member table")

        with tempfile.TemporaryDirectory() as temporary, mock.patch.object(
            installer.tarfile, "open", return_value=BrokenArchive()
        ):
            with self.assertRaisesRegex(RuntimeError, "unable to read skill archive"):
                installer.extract_skill_archive(b"fake", Path(temporary) / "skill")

    def test_extract_normalizes_tar_errors_from_member_extraction(self) -> None:
        prefix = "templates-source/skills/composition"
        members: list[tarfile.TarInfo] = []
        for relative in (
            "SKILL.md",
            "runtime-manifest.json",
            "scripts/install.py",
            "scripts/run.py",
            "scripts/runtime.py",
        ):
            member = tarfile.TarInfo(f"{prefix}/{relative}")
            member.size = 1
            members.append(member)

        class BrokenArchive:
            def __enter__(self):
                return self

            def __exit__(self, *args: object) -> None:
                return None

            def getmembers(self):
                return members

            def extractfile(self, _member: tarfile.TarInfo):
                raise tarfile.ReadError("broken payload")

        with tempfile.TemporaryDirectory() as temporary, mock.patch.object(
            installer.tarfile, "open", return_value=BrokenArchive()
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

        members: list[tarfile.TarInfo] = []
        for relative in (
            "SKILL.md",
            "runtime-manifest.json",
            "scripts/install.py",
            "scripts/run.py",
            "scripts/runtime.py",
        ):
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
        self.assertIsInstance(command, list)
        assert isinstance(command, list)
        self.assertEqual(command[0:2], [sys.executable, "-I"])
        self.assertEqual(command[3:], [str(target), "--replace"])
        self.assertIs(observed["check"], True)

    def test_download_rejects_oversized_content_length_before_read(self) -> None:
        class Headers:
            def get(self, _key: str) -> str:
                return str(installer.ARCHIVE_LIMIT + 1)

        class FakeResponse:
            headers = Headers()

            def __enter__(self):
                return self

            def __exit__(self, *args: object) -> None:
                return None

            def read(self, amount: int = -1) -> bytes:
                raise AssertionError(f"read must not run for oversized archive: {amount}")

        def opener(_request: object, *, timeout: int):
            self.assertEqual(timeout, 30)
            return FakeResponse()

        with self.assertRaisesRegex(RuntimeError, "download size limit"):
            installer.download_archive(opener=opener)

    def test_download_rejects_malformed_and_negative_content_length(self) -> None:
        class Headers:
            def __init__(self, value: str):
                self.value = value

            def get(self, _key: str) -> str:
                return self.value

        class FakeResponse:
            def __init__(self, value: str):
                self.headers = Headers(value)

            def __enter__(self):
                return self

            def __exit__(self, *args: object) -> None:
                return None

            def read(self, amount: int = -1) -> bytes:
                return b"unused"

        for value, message in (("abc", "invalid Content-Length"), ("-10", "download size limit")):
            with self.subTest(value=value):
                def opener(_request: object, *, timeout: int, value: str = value):
                    self.assertEqual(timeout, 30)
                    return FakeResponse(value)

                with self.assertRaisesRegex(RuntimeError, message):
                    installer.download_archive(opener=opener)

    def test_download_rejects_oversized_payload_without_content_length(self) -> None:
        payload = b"x" * (installer.ARCHIVE_LIMIT + 1)

        def opener(_request: object, *, timeout: int):
            self.assertEqual(timeout, 30)
            return BytesResponse(payload)

        with self.assertRaisesRegex(RuntimeError, "download size limit"):
            installer.download_archive(opener=opener)

    def test_download_rejects_empty_archive(self) -> None:
        def opener(_request: object, *, timeout: int):
            self.assertEqual(timeout, 30)
            return BytesResponse(b"")

        with self.assertRaisesRegex(RuntimeError, "download was empty"):
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