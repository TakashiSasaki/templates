from __future__ import annotations

import importlib.util
import io
import json
import os
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


def materialize_skill(target: Path) -> None:
    installer.extract_skill_archive(skill_archive(), target)


def test_remote_installer_pins_the_policy_owned_skill_revision() -> None:
    assert installer.TOOLCHAIN_REPOSITORY == "TakashiSasaki/templates"
    assert installer.INSTALLER_PATH == "scripts/install_agent_policy_skill.py"
    assert installer.SKILL_SOURCE_PATH == "skills/agent-policy"
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


def test_installation_attestation_binds_closed_path_type_inventory(
    tmp_path: Path,
) -> None:
    target = tmp_path / "installed" / "agent-policy"
    target.parent.mkdir(parents=True)
    materialize_skill(target)
    attestation = tmp_path / "trust" / "agent-policy-installation.json"
    installer_revision = "a" * 40

    installer.write_installation_attestation(
        target,
        attestation,
        installer_revision=installer_revision,
    )
    value = json.loads(attestation.read_text(encoding="utf-8"))

    assert value["installer"] == {
        "repository": "TakashiSasaki/templates",
        "revision": installer_revision,
        "path": "scripts/install_agent_policy_skill.py",
    }
    assert value["skill_source"] == {
        "repository": "TakashiSasaki/templates",
        "revision": installer.SKILL_SOURCE_REVISION,
        "path": "skills/agent-policy",
    }
    assert value["installation"]["root"] == str(target.absolute())
    entries = value["installation"]["entries"]
    assert set(entries) == {
        "README.md",
        "SKILL.md",
        "runtime-manifest.json",
        "scripts",
        "scripts/install.py",
    }
    assert entries["scripts"] == {"type": "directory"}
    assert entries["SKILL.md"]["type"] == "file"
    assert len(entries["SKILL.md"]["sha256"]) == 64
    installer.verify_installation_attestation(
        target,
        attestation,
        installer_revision=installer_revision,
    )


def test_installation_attestation_detects_installed_skill_tampering(
    tmp_path: Path,
) -> None:
    target = tmp_path / "installed" / "agent-policy"
    target.parent.mkdir(parents=True)
    materialize_skill(target)
    attestation = tmp_path / "trust" / "agent-policy-installation.json"
    installer_revision = "a" * 40
    installer.write_installation_attestation(
        target,
        attestation,
        installer_revision=installer_revision,
    )

    (target / "SKILL.md").write_text("modified\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="does not match installed skill tree"):
        installer.verify_installation_attestation(
            target,
            attestation,
            installer_revision=installer_revision,
        )


def test_installation_attestation_rejects_added_paths(tmp_path: Path) -> None:
    target = tmp_path / "installed" / "agent-policy"
    target.parent.mkdir(parents=True)
    materialize_skill(target)
    attestation = tmp_path / "trust" / "agent-policy-installation.json"
    installer_revision = "a" * 40
    installer.write_installation_attestation(
        target,
        attestation,
        installer_revision=installer_revision,
    )

    (target / "scripts" / "json.py").write_text("raise SystemExit(99)\n", encoding="utf-8")
    (target / "extra-empty-directory").mkdir()

    with pytest.raises(RuntimeError, match="does not match installed skill tree"):
        installer.verify_installation_attestation(
            target,
            attestation,
            installer_revision=installer_revision,
        )


def test_installation_attestation_must_be_outside_skill_tree(tmp_path: Path) -> None:
    target = tmp_path / "installed" / "agent-policy"
    target.parent.mkdir(parents=True)
    materialize_skill(target)

    with pytest.raises(ValueError, match="outside the installed skill tree"):
        installer.write_installation_attestation(
            target,
            target / "installation-attestation.json",
            installer_revision="a" * 40,
        )


def test_attestation_destination_is_preflighted_before_install(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    target = tmp_path / "agent-policy"

    def unexpected_download(*_args: object, **_kwargs: object) -> bytes:
        raise AssertionError("download must not run before attestation preflight")

    monkeypatch.setattr(installer, "download_archive", unexpected_download)
    status = installer.main(
        [
            str(target),
            "--installer-revision",
            "a" * 40,
            "--attestation",
            str(target / "installation-attestation.json"),
        ]
    )

    assert status == 1
    assert not target.exists()


def test_verify_only_cli_does_not_download_or_install(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    target = tmp_path / "agent-policy"
    materialize_skill(target)
    attestation = tmp_path / "trust" / "agent-policy-installation.json"
    installer_revision = "a" * 40
    installer.write_installation_attestation(
        target,
        attestation,
        installer_revision=installer_revision,
    )

    def unexpected_download(*_args: object, **_kwargs: object) -> bytes:
        raise AssertionError("verify-only must not download")

    def unexpected_install(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("verify-only must not install")

    monkeypatch.setattr(installer, "download_archive", unexpected_download)
    monkeypatch.setattr(installer, "install_downloaded_skill", unexpected_install)
    status = installer.main(
        [
            str(target),
            "--installer-revision",
            installer_revision,
            "--attestation",
            str(attestation),
            "--verify-only",
        ]
    )

    assert status == 0


def test_materialize_run_image_copies_only_attested_tree_and_verifies(
    tmp_path: Path,
) -> None:
    target = tmp_path / "installed" / "agent-policy"
    target.parent.mkdir(parents=True)
    materialize_skill(target)
    attestation = tmp_path / "trust" / "agent-policy-installation.json"
    run_image = tmp_path / "deployment" / "review-run" / "agent-policy"
    installer_revision = "a" * 40
    installer.write_installation_attestation(
        target,
        attestation,
        installer_revision=installer_revision,
    )

    installer.materialize_run_image(
        target,
        run_image,
        attestation,
        installer_revision=installer_revision,
    )

    assert installer.installed_tree_inventory(run_image) == installer.installed_tree_inventory(
        target
    )
    installer.verify_run_image(
        target,
        run_image,
        attestation,
        installer_revision=installer_revision,
    )


def test_materialize_run_image_rejects_source_drift_after_attestation(
    tmp_path: Path,
) -> None:
    target = tmp_path / "installed" / "agent-policy"
    target.parent.mkdir(parents=True)
    materialize_skill(target)
    attestation = tmp_path / "trust" / "agent-policy-installation.json"
    run_image = tmp_path / "deployment" / "agent-policy"
    installer_revision = "a" * 40
    installer.write_installation_attestation(
        target,
        attestation,
        installer_revision=installer_revision,
    )
    (target / "SKILL.md").write_text("changed after attestation\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="does not match installed skill tree"):
        installer.materialize_run_image(
            target,
            run_image,
            attestation,
            installer_revision=installer_revision,
        )
    assert not run_image.exists()


def test_verify_run_image_detects_post_materialization_tampering(
    tmp_path: Path,
) -> None:
    target = tmp_path / "installed" / "agent-policy"
    target.parent.mkdir(parents=True)
    materialize_skill(target)
    attestation = tmp_path / "trust" / "agent-policy-installation.json"
    run_image = tmp_path / "deployment" / "agent-policy"
    installer_revision = "a" * 40
    installer.write_installation_attestation(
        target,
        attestation,
        installer_revision=installer_revision,
    )
    installer.materialize_run_image(
        target,
        run_image,
        attestation,
        installer_revision=installer_revision,
    )
    (run_image / "scripts" / "install.py").write_text("tampered\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="does not match installation attestation"):
        installer.verify_run_image(
            target,
            run_image,
            attestation,
            installer_revision=installer_revision,
        )


def test_materialize_run_image_requires_fresh_nonoverlapping_destination(
    tmp_path: Path,
) -> None:
    target = tmp_path / "installed" / "agent-policy"
    target.parent.mkdir(parents=True)
    materialize_skill(target)
    attestation = tmp_path / "trust" / "agent-policy-installation.json"
    installer_revision = "a" * 40
    installer.write_installation_attestation(
        target,
        attestation,
        installer_revision=installer_revision,
    )

    with pytest.raises(ValueError, match="outside the installed skill tree"):
        installer.materialize_run_image(
            target,
            target / "run-image",
            attestation,
            installer_revision=installer_revision,
        )

    existing = tmp_path / "existing"
    existing.mkdir()
    with pytest.raises(ValueError, match="must not already exist"):
        installer.materialize_run_image(
            target,
            existing,
            attestation,
            installer_revision=installer_revision,
        )


def test_run_image_cli_operations_do_not_download_or_install(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    target = tmp_path / "installed" / "agent-policy"
    target.parent.mkdir(parents=True)
    materialize_skill(target)
    attestation = tmp_path / "trust" / "agent-policy-installation.json"
    run_image = tmp_path / "deployment" / "agent-policy"
    installer_revision = "a" * 40
    installer.write_installation_attestation(
        target,
        attestation,
        installer_revision=installer_revision,
    )

    def unexpected_download(*_args: object, **_kwargs: object) -> bytes:
        raise AssertionError("run-image operations must not download")

    def unexpected_install(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("run-image operations must not install")

    monkeypatch.setattr(installer, "download_archive", unexpected_download)
    monkeypatch.setattr(installer, "install_downloaded_skill", unexpected_install)

    materialize_status = installer.main(
        [
            str(target),
            "--installer-revision",
            installer_revision,
            "--attestation",
            str(attestation),
            "--materialize-run-image",
            str(run_image),
        ]
    )
    assert materialize_status == 0

    verify_status = installer.main(
        [
            str(target),
            "--installer-revision",
            installer_revision,
            "--attestation",
            str(attestation),
            "--verify-run-image",
            str(run_image),
        ]
    )
    assert verify_status == 0


def test_installed_skill_digest_rejects_symlink_path_components(
    tmp_path: Path,
) -> None:
    real_parent = tmp_path / "real"
    target = real_parent / "agent-policy"
    real_parent.mkdir()
    materialize_skill(target)
    alias = tmp_path / "alias"
    alias.symlink_to(real_parent, target_is_directory=True)

    with pytest.raises(RuntimeError, match="symbolic-link component"):
        installer.installed_file_digests(alias / "agent-policy")


def test_installed_skill_digest_rejects_hard_links(tmp_path: Path) -> None:
    target = tmp_path / "agent-policy"
    materialize_skill(target)
    outside = tmp_path / "outside.txt"
    outside.write_text("linked\n", encoding="utf-8")
    os.link(outside, target / "linked.txt")

    with pytest.raises(RuntimeError, match="hard-linked file"):
        installer.installed_file_digests(target)


def test_installed_skill_digest_enforces_distribution_size_limit(
    tmp_path: Path,
) -> None:
    target = tmp_path / "agent-policy"
    materialize_skill(target)
    oversized = target / "oversized.bin"
    with oversized.open("wb") as output:
        output.truncate(installer.SKILL_LIMIT + 1)

    with pytest.raises(RuntimeError, match="exceeds the size limit"):
        installer.installed_file_digests(target)


def test_attestation_requires_full_installer_revision(tmp_path: Path) -> None:
    target = tmp_path / "agent-policy"
    materialize_skill(target)

    with pytest.raises(ValueError, match="installer revision"):
        installer.installation_attestation(target, installer_revision="policy")


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
