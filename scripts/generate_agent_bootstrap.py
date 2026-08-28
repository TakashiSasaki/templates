#!/usr/bin/env python3
"""Generate and verify the Site-owned coding-agent bootstrap projection."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.resolve_publication_sources import SourceLockError, resolve_sources

REPOSITORY = "TakashiSasaki/templates"
SCHEMA_URL = "https://templates.moukaeritai.work/schemas/agent-bootstrap.schema.json"
CANONICAL_URL = "https://templates.moukaeritai.work/agent.json"
PUBLICATION_CATALOG_PATH = "docs/publication-catalog.json"
COMPOSITION_OVERVIEW_DOCUMENT_ID = "composition:overview"
POLICY_OVERVIEW_DOCUMENT_ID = "policy:overview"
SITE_OVERVIEW_DOCUMENT_ID = "site:portal-home"
COEXISTENCE_DOCUMENT_ID = "site:policy-composition-coexistence"
COEXISTENCE_URL = "https://templates.moukaeritai.work/coexistence/"
FULL_SHA = re.compile(r"\A[0-9a-f]{40}\Z")
SHA256 = re.compile(r"\A[0-9a-f]{64}\Z")

VERIFIED_INSTALLER_BOOTSTRAP = """\
import hashlib
import pathlib
import subprocess
import sys
import urllib.request

url, expected, installer_file, skill_target = sys.argv[1:5]
data = urllib.request.urlopen(url, timeout=30).read()
actual = hashlib.sha256(data).hexdigest()
if actual != expected:
    raise SystemExit(
        f"installer SHA-256 mismatch: expected {expected}, got {actual}"
    )
path = pathlib.Path(installer_file)
path.parent.mkdir(parents=True, exist_ok=True)
path.write_bytes(data)
subprocess.run(
    [sys.executable, "-I", str(path), skill_target],
    check=True,
)
"""


class AgentBootstrapError(RuntimeError):
    """Raised when the bootstrap projection cannot be derived safely."""


def read_json_object(path: Path, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise AgentBootstrapError(f"{label} must be a regular file: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise AgentBootstrapError(f"unable to read {label} {path}: {exc}") from exc

    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise AgentBootstrapError(
                    f"{label} contains duplicate object member: {key}"
                )
            result[key] = value
        return result

    try:
        value = json.loads(text, object_pairs_hook=unique)
    except json.JSONDecodeError as exc:
        raise AgentBootstrapError(f"unable to parse {label} {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise AgentBootstrapError(f"{label} must be a JSON object")
    return value


def require_object(
    value: Any,
    *,
    label: str,
    fields: set[str],
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise AgentBootstrapError(
            f"{label} must contain exactly: {', '.join(sorted(fields))}"
        )
    return value


def require_full_sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or FULL_SHA.fullmatch(value) is None:
        raise AgentBootstrapError(
            f"{label} must be a full lowercase 40-character commit SHA"
        )
    return value


def require_sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or SHA256.fullmatch(value) is None:
        raise AgentBootstrapError(
            f"{label} must be 64 lowercase hexadecimal characters"
        )
    return value


def validate_release_descriptor(path: Path) -> dict[str, Any]:
    value = read_json_object(path, "Composition installer release descriptor")
    require_object(
        value,
        label="Composition installer release descriptor",
        fields={"schema_version", "channel", "installer", "skill_source", "toolchain"},
    )
    if type(value["schema_version"]) is not int or value["schema_version"] != 1:
        raise AgentBootstrapError("Composition installer release schema_version must be 1")
    if value["channel"] != "stable":
        raise AgentBootstrapError("Composition installer release channel must be stable")

    installer = require_object(
        value["installer"],
        label="installer",
        fields={"repository", "revision", "path", "sha256"},
    )
    skill = require_object(
        value["skill_source"],
        label="skill_source",
        fields={"repository", "revision", "path"},
    )
    toolchain = require_object(
        value["toolchain"],
        label="toolchain",
        fields={"repository", "revision"},
    )

    for entry, label in (
        (installer, "installer"),
        (skill, "skill_source"),
        (toolchain, "toolchain"),
    ):
        if entry["repository"] != REPOSITORY:
            raise AgentBootstrapError(f"{label}.repository must be {REPOSITORY}")
        require_full_sha(entry["revision"], f"{label}.revision")

    if installer["path"] != "scripts/install_composition_skill.py":
        raise AgentBootstrapError("installer.path is not the canonical installer path")
    require_sha256(installer["sha256"], "installer.sha256")
    if skill["path"] != "skills/composition":
        raise AgentBootstrapError("skill_source.path is not the canonical Skill path")
    return value


def build_manifest(source_lock: Path, composition_release: Path) -> dict[str, Any]:
    try:
        sources = resolve_sources(source_lock, {})
    except SourceLockError as exc:
        raise AgentBootstrapError(str(exc)) from exc
    release = validate_release_descriptor(composition_release)
    installer = release["installer"]
    skill_source = release["skill_source"]
    toolchain = release["toolchain"]
    installer_url = (
        "https://raw.githubusercontent.com/TakashiSasaki/templates/"
        f"{installer['revision']}/{installer['path']}"
    )
    instructions_url = (
        "https://raw.githubusercontent.com/TakashiSasaki/templates/"
        f"{skill_source['revision']}/{skill_source['path']}/SKILL.md"
    )

    return {
        "$schema": SCHEMA_URL,
        "schema_version": 3,
        "repository": REPOSITORY,
        "canonical_url": CANONICAL_URL,
        "purpose": "Discover authorities and compose new or existing software repositories",
        "authorities": {
            "composition": {
                "role": "artifact-capability-lifecycle-semantics",
                "publication_revision": sources["composition"],
                "overview_document_id": COMPOSITION_OVERVIEW_DOCUMENT_ID,
                "publication_catalog_path": PUBLICATION_CATALOG_PATH,
            },
            "policy": {
                "role": "coding-agent-operating-policy",
                "publication_revision": sources["policy"],
                "overview_document_id": POLICY_OVERVIEW_DOCUMENT_ID,
                "publication_catalog_path": PUBLICATION_CATALOG_PATH,
                "relationship_to_composition": "independent-optional",
            },
            "site": {
                "role": "publication-integration",
                "overview_document_id": SITE_OVERVIEW_DOCUMENT_ID,
                "consumer_repository_mutation": False,
            },
        },
        "integration_contracts": {
            "policy_composition_coexistence": {
                "owner": "site",
                "document_id": COEXISTENCE_DOCUMENT_ID,
                "canonical_url": COEXISTENCE_URL,
            }
        },
        "composition": {
            "publication_revision": sources["composition"],
            "installer": {
                "repository": REPOSITORY,
                "revision": installer["revision"],
                "path": installer["path"],
                "sha256": installer["sha256"],
                "url": installer_url,
            },
            "skill": {
                "name": "composition",
                "repository": REPOSITORY,
                "revision": skill_source["revision"],
                "path": skill_source["path"],
                "entrypoint": "scripts/run.py",
                "instructions_url": instructions_url,
            },
            "toolchain": {
                "repository": REPOSITORY,
                "revision": toolchain["revision"],
            },
        },
        "requirements": {
            "python": {"minimum": "3.11", "maximum": "3.14"},
            "https": True,
        },
        "bootstrap": {
            "download": "https",
            "verify": "sha256-before-execute",
            "execute": "python-isolated",
            "installation_modes": ["persistent", "transient"],
            "canonical_operation": "execute-verified-installer-argv",
            "reimplementation_policy": "do-not-reimplement",
            "verified_installer_argv": [
                "{python}",
                "-I",
                "-c",
                VERIFIED_INSTALLER_BOOTSTRAP,
                "{installer_url}",
                "{installer_sha256}",
                "{installer_file}",
                "{skill_target}",
            ],
            "argument_bindings": {
                "{installer_url}": "composition.installer.url",
                "{installer_sha256}": "composition.installer.sha256",
            },
            "caller_inputs": ["{python}", "{installer_file}", "{skill_target}"],
        },
        "workflow": {
            "runner_argv": [
                "{python}",
                "{skill_target}/scripts/run.py",
                "--repository",
                "{repository}",
                "{command}",
            ],
            "diagnose": "doctor",
            "provenance": "provenance",
            "inspect_before_mutation": "inspect",
            "plan_before_apply": True,
            "validate_after_apply": True,
        },
    }


def render_manifest(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def verify_projection(path: Path, expected: bytes, label: str) -> None:
    if path.is_symlink() or not path.is_file():
        raise AgentBootstrapError(f"{label} must be a regular file: {path}")
    try:
        actual = path.read_bytes()
    except OSError as exc:
        raise AgentBootstrapError(f"unable to read {label} {path}: {exc}") from exc
    if actual != expected:
        raise AgentBootstrapError(
            f"{label} is stale; regenerate it from the locked Composition release descriptor"
        )


def verify_site_projections(site_root: Path, composition_root: Path) -> None:
    site_root = site_root.resolve(strict=True)
    composition_root = composition_root.resolve(strict=True)
    expected = render_manifest(
        build_manifest(
            site_root / "publication-sources.json",
            composition_root / "release/composition-installer.json",
        )
    )
    verify_projection(site_root / "agent.json", expected, "repository agent manifest")
    verify_projection(
        site_root / "assets/agent.json",
        expected,
        "published agent manifest",
    )

    schema = site_root / "schemas/agent-bootstrap.schema.json"
    published_schema = site_root / "assets/schemas/agent-bootstrap.schema.json"
    if schema.is_symlink() or not schema.is_file():
        raise AgentBootstrapError(f"agent bootstrap schema must be a regular file: {schema}")
    verify_projection(
        published_schema,
        schema.read_bytes(),
        "published agent bootstrap schema",
    )
    read_json_object(schema, "agent bootstrap schema")


def write_site_projections(site_root: Path, composition_root: Path) -> None:
    site_root = site_root.resolve(strict=True)
    composition_root = composition_root.resolve(strict=True)
    payload = render_manifest(
        build_manifest(
            site_root / "publication-sources.json",
            composition_root / "release/composition-installer.json",
        )
    )
    targets = (site_root / "agent.json", site_root / "assets/agent.json")
    for target in targets:
        if target.is_symlink():
            raise AgentBootstrapError(f"projection target must not be a symlink: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)

    schema = site_root / "schemas/agent-bootstrap.schema.json"
    if schema.is_symlink() or not schema.is_file():
        raise AgentBootstrapError(f"agent bootstrap schema must be a regular file: {schema}")
    published_schema = site_root / "assets/schemas/agent-bootstrap.schema.json"
    if published_schema.is_symlink():
        raise AgentBootstrapError(
            f"published schema target must not be a symlink: {published_schema}"
        )
    published_schema.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(schema, published_schema)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-root", type=Path, required=True)
    parser.add_argument("--composition-root", type=Path, required=True)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    try:
        if args.write:
            write_site_projections(args.site_root, args.composition_root)
            print("Agent bootstrap projections regenerated.")
        else:
            verify_site_projections(args.site_root, args.composition_root)
            print("Agent bootstrap projections are synchronized.")
    except (AgentBootstrapError, OSError) as exc:
        print(f"agent bootstrap projection failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
