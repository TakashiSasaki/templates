from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from types import ModuleType

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
DESCRIPTOR = ROOT / "release/skill-installer.json"
SCHEMA = ROOT / "schemas/skill-installer-release.schema.json"
README = ROOT / "README.md"
SKILL_README = ROOT / "skills/agent-policy/README.md"
BOOTSTRAP_DOC = ROOT / "docs/bootstrap.md"
GETTING_STARTED = ROOT / "docs/getting-started.md"
RELEASE_TRUST = ROOT / "repository-policy/release-trust.md"
INSTALLER_REVISION = "f4457c90854db34c3ce8e1c381f67a4d7d5ea523"
SKILL_REVISION = "344aaf0b140e3c066363297012bb866efbc106e4"
RAW_INSTALLER_URL = (
    "https://raw.githubusercontent.com/TakashiSasaki/templates/"
    f"{INSTALLER_REVISION}/scripts/install_agent_policy_skill.py"
)
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")


def load_script() -> ModuleType:
    path = ROOT / "scripts/verify_skill_installer_release.py"
    spec = importlib.util.spec_from_file_location("verify_skill_installer_release", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


verifier = load_script()


def load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_installer_release_descriptor_is_schema_valid_and_immutable() -> None:
    descriptor = load_json(DESCRIPTOR)
    Draft202012Validator(load_json(SCHEMA)).validate(descriptor)

    installer = descriptor["installer"]
    skill_source = descriptor["skill_source"]
    assert isinstance(installer, dict)
    assert isinstance(skill_source, dict)
    assert installer == {
        "repository": "TakashiSasaki/templates",
        "revision": INSTALLER_REVISION,
        "path": "scripts/install_agent_policy_skill.py",
    }
    assert skill_source == {
        "repository": "TakashiSasaki/templates",
        "revision": SKILL_REVISION,
        "path": "skills/agent-policy",
    }
    assert FULL_SHA.fullmatch(INSTALLER_REVISION)
    assert FULL_SHA.fullmatch(SKILL_REVISION)


def test_installer_release_verifier_matches_pinned_history() -> None:
    assert verifier.verify() == (INSTALLER_REVISION, SKILL_REVISION)


def test_publication_docs_publish_only_the_full_sha_installer_url() -> None:
    documents = (README, BOOTSTRAP_DOC, GETTING_STARTED)
    for path in documents:
        content = path.read_text(encoding="utf-8")
        assert RAW_INSTALLER_URL in content, path
        assert "raw.githubusercontent.com/TakashiSasaki/templates/policy/" not in content
        assert "raw.githubusercontent.com/TakashiSasaki/templates/main/" not in content
        assert "scripts/install_agent_policy_skill.py', timeout=30" in content


def test_release_policy_defines_installed_readme_boundary() -> None:
    content = RELEASE_TRUST.read_text(encoding="utf-8")
    assert "installer-publication surface" in content
    assert "distributed consumer artifact, not an installer-publication authority" in content
    assert "must not embed a specific installer-script revision or skill-source revision" in content


def test_installed_skill_readme_is_publication_independent() -> None:
    # The installed README is a distributed consumer artifact rather than the
    # installer-publication surface, so publication SHAs belong elsewhere.
    content = SKILL_README.read_text(encoding="utf-8")
    assert "## Immutable remote installation" in content
    assert "Remote installation is supported" in content
    assert "release/skill-installer.json" in content
    assert "raw.githubusercontent.com" not in content
    assert INSTALLER_REVISION not in content
    assert SKILL_REVISION not in content
    # Guard against the historical placeholder that treated remote installation
    # as future follow-up work instead of a supported publication path.
    assert "follow-up installer work" not in content.lower()


def test_docs_distinguish_installer_skill_and_runtime_revisions() -> None:
    # SKILL_README intentionally carries the role names but not publication SHAs;
    # repository-level publication docs carry the currently published identities.
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (README, SKILL_README, BOOTSTRAP_DOC, GETTING_STARTED)
    )
    assert INSTALLER_REVISION in combined
    assert SKILL_REVISION in combined
    assert "installer script revision" in combined.lower()
    assert "skill source revision" in combined.lower()
    assert "stable runtime" in combined.lower()
