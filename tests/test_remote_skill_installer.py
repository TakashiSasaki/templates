from __future__ import annotations

import importlib.util
import io
import subprocess
import sys
import tarfile
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/install_agent_policy_skill.py"


def load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("install_agent_policy_skill", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


installer = load_script()


def add_file(archive: tarfile.TarFile, name: str, content: bytes) -> None:
    member = tarfile.TarInfo(name)
    member.size = len(content)
    archive.addfile(member, io.BytesIO(content))


def skill_archive(*, extra_members: list[tarfile.TarInfo] | None = None) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        add_file(
            archive,
            "templates-source/skills/agent-policy/SKILL.md",
            b"---\nname: agent-policy\n---\n",
        )
        add_file(
            archive,
            "templates-source/skills/agent-policy/runtime-manifest.json",
            b"{}\n",
        )
        add_file(
            archive,
            "templates-source/skills/agent-policy/scripts/install.py",
            b"print('installer')\n",
        )
        add_file(
            archive,
            "templates-source/skills/agent-policy/README.md",
            b"# agent-policy\n",
        )
        add_file(archive, "templates-source/README.md", b"outside skill\n")
        for member in extra_members or []:
            archive.addfile(member)
    return buffer.getvalue()


def test_remote_installer_pins_the_policy_owned_skill_revision() -> None:
    assert installer.TOOLCHAIN_REPOSITORY == "TakashiSasaki/templates"
    assert (
        installer.SKILL_SOURCE_REVISION
        == "499dc8699e3dcd9f460d603718bdf2266c45e7ca"
    )
    assert installer.FULL_SHA.fullmatch(installer.SKILL_SOURCE_REVISION)
    assert installer.archive_url().endswith(
        "/tar.gz/499dc8699e3dcd9f460d603718bdf2266c45e7ca"
    )


def test_archive_url_rejects_mutable_or_short_revisions() -> None:
    for revision in ("policy", "main", "e4a0ae84"):
        with pytest.raises(ValueError, match="full lowercase commit SHA"):
            installer.archive_url(revision)


def test_extract_skill_archive_selects_only_the_skill_subtree(tmp_path: Path) -> None:
    destination = tmp_path / "skill"
    result = installer.extract_skill_archive(skill_archive(), destination)

    assert result == destination.resolve()
    assert (destination / "SKILL.md").read_text(encoding="utf-8").startswith("---")
    assert (destination / "runtime-manifest.json").is_file()
    assert (destination / "scripts/install.py").is_file()
    assert not (destination / "README-from-root.md").exists()
    assert not (tmp_path / "README.md").exists()


@pytest.mark.parametrize(
    "name",
    [
        "templates-source/skills/agent-policy/../outside.txt",
        "templates-source/skills/agent-policy/..\\outside.txt",
        "templates-source/skills/agent-policy/file:stream",
    ],
)
def test_extract_skill_archive_rejects_cross_platform_unsafe_paths(
    tmp_path: Path,
    name: str,
) -> None:
    traversal = tarfile.TarInfo(name)
    traversal.size = 0

    with pytest.raises(RuntimeError, match="unsafe path"):
        installer.extract_skill_archive(
            skill_archive(extra_members=[traversal]),
            tmp_path / "skill",
        )


def test_extract_skill_archive_rejects_links(tmp_path: Path) -> None:
    link = tarfile.TarInfo("templates-source/skills/agent-policy/link")
    link.type = tarfile.SYMTYPE
    link.linkname = "../../outside"

    with pytest.raises(RuntimeError, match="links are not allowed"):
        installer.extract_skill_archive(
            skill_archive(extra_members=[link]),
            tmp_path / "skill",
        )


def test_extract_skill_archive_requires_install_contract(tmp_path: Path) -> None:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        add_file(
            archive,
            "templates-source/skills/agent-policy/SKILL.md",
            b"---\nname: agent-policy\n---\n",
        )

    with pytest.raises(RuntimeError, match="missing required paths"):
        installer.extract_skill_archive(buffer.getvalue(), tmp_path / "skill")


def test_install_downloaded_skill_delegates_to_atomic_local_installer(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    target = tmp_path / "installed" / "agent-policy"
    observed: dict[str, object] = {}

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        observed["command"] = command
        observed["check"] = kwargs.get("check")
        assert Path(command[1]).name == "install.py"
        assert Path(command[1]).is_file()
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(installer.subprocess, "run", fake_run)
    installer.install_downloaded_skill(skill_archive(), target, replace=True)

    command = observed["command"]
    assert isinstance(command, list)
    assert command[0] == sys.executable
    assert command[2:] == [str(target), "--replace"]
    assert observed["check"] is True


def test_download_archive_rejects_oversized_content_length() -> None:
    class Headers:
        def get(self, _key: str) -> str:
            return str(installer.ARCHIVE_LIMIT + 1)

    class FakeResponse:
        headers = Headers()

        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self, amount: int = -1) -> bytes:
            raise AssertionError(f"read must not run for oversized archive: {amount}")

    def opener(
        _request: object,
        *,
        timeout: int,
    ) -> FakeResponse:
        assert timeout == 30
        return FakeResponse()

    with pytest.raises(RuntimeError, match="download size limit"):
        installer.download_archive(opener=opener)
