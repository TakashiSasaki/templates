"""Validate provider-owned publication capability declarations at the boundary."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class CapabilityError(ValueError):
    """A provider capability declaration is malformed or not closed."""


CAPABILITIES_PATH = Path("docs/publication-capabilities.json")
REGISTRY_PATH = Path("contracts/publication-compatibility/provider-registry.json")
FEATURES_PATH = Path("contracts/publication-compatibility/feature-registry.json")
PROTOCOL = "publication-bundle"
FALLBACKS = {"none", "generic-document", "ignore"}
RIGHTS = {"allowlisted", "reference-only", "not-assessed"}
RECORD_SUBJECT_OWNERSHIP = "external-as-recorded"
RECORD_REDISTRIBUTION = "local-record-metadata"
EXPORT_KINDS = {"document", "asset", "record", "catalog"}


def _read(path: Path, label: str) -> dict[str, Any]:
    try:
        def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for key, value in pairs:
                if key in result:
                    raise CapabilityError(f"{label} contains duplicate member: {key}")
                result[key] = value
            return result

        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=unique,
            parse_constant=lambda value: (_ for _ in ()).throw(
                CapabilityError(f"{label} contains non-standard number: {value}")
            ),
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CapabilityError(f"unable to read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise CapabilityError(f"{label} must be an object")
    return value


def _registry(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    registry = _read(root / REGISTRY_PATH, "provider registry")
    features = _read(root / FEATURES_PATH, "feature registry")
    if registry != {
        "schema_version": 1,
        "repository": "TakashiSasaki/templates",
        "providers": registry.get("providers"),
    } or not isinstance(registry.get("providers"), dict):
        raise CapabilityError("provider registry has an invalid shape")
    if features.get("schema_version") != 1 or not isinstance(features.get("features"), dict):
        raise CapabilityError("feature registry has an invalid shape")
    return registry["providers"], features["features"]


def validate_provider_declaration(root: Path, provider: str) -> dict[str, Any]:
    """Return a validated declaration; do not infer support from its strings alone."""
    providers, features = _registry(Path(__file__).resolve().parents[1])
    entry = providers.get(provider)
    if not isinstance(entry, dict) or entry.get("publication_capabilities") != CAPABILITIES_PATH.as_posix():
        raise CapabilityError(f"provider registry does not bind {provider}")
    value = _read(root / CAPABILITIES_PATH, f"{provider} publication capabilities")
    if set(value) != {"schema_version", "provider", "protocol", "exports", "requirements"}:
        raise CapabilityError(f"{provider} declaration has unsupported or missing fields")
    if value["schema_version"] != 1 or value["provider"] != provider or value["protocol"] != PROTOCOL:
        raise CapabilityError(f"{provider} declaration identity or protocol mismatch")
    exports = value["exports"]
    if not isinstance(exports, list) or not exports:
        raise CapabilityError(f"{provider} exports must be a non-empty array")
    export_features: set[str] = set()
    for index, item in enumerate(exports):
        if not isinstance(item, dict):
            raise CapabilityError(f"{provider}.exports[{index}] must be an object")
        allowed = {"kind", "namespace", "media_type", "identity_basis", "feature", "rights",
                   "subject_ownership", "redistribution"}
        if not set(item) <= allowed or not {"kind", "namespace", "media_type", "identity_basis"} <= set(item):
            raise CapabilityError(f"{provider}.exports[{index}] has an invalid shape")
        if item["kind"] not in EXPORT_KINDS or any(
            not isinstance(item[field], str) or not item[field].strip()
            for field in ("namespace", "media_type", "identity_basis")
        ):
            raise CapabilityError(f"{provider}.exports[{index}] has invalid metadata")
        feature = item.get("feature")
        if feature is not None:
            if not isinstance(feature, str) or feature not in features:
                raise CapabilityError(f"{provider}.exports[{index}] uses an unknown feature")
            export_features.add(feature)
        rights = item.get("rights")
        if rights is not None and rights not in RIGHTS:
            raise CapabilityError(f"{provider}.exports[{index}] has invalid rights")
        if item["kind"] == "record" and provider == "modeling":
            expected = {"kind", "namespace", "media_type", "identity_basis", "feature",
                        "subject_ownership", "redistribution"}
            if set(item) != expected or item["subject_ownership"] != RECORD_SUBJECT_OWNERSHIP or item["redistribution"] != RECORD_REDISTRIBUTION:
                raise CapabilityError(
                    "modeling record export must separate external subject ownership from local metadata redistribution"
                )
    requirements = value["requirements"]
    if not isinstance(requirements, list):
        raise CapabilityError(f"{provider} requirements must be an array")
    requirement_features: set[str] = set()
    for index, item in enumerate(requirements):
        if not isinstance(item, dict) or set(item) != {"feature", "required", "fallback"}:
            raise CapabilityError(f"{provider}.requirements[{index}] has an invalid shape")
        feature = item["feature"]
        if not isinstance(feature, str) or feature not in features or feature in requirement_features:
            raise CapabilityError(f"{provider}.requirements[{index}] uses an unknown or duplicate feature")
        if type(item["required"]) is not bool or item["fallback"] not in FALLBACKS:
            raise CapabilityError(f"{provider}.requirements[{index}] has invalid fallback metadata")
        if item["required"] and feature not in export_features:
            raise CapabilityError(
                f"{provider}.requirements[{index}] is required but has no declared export coverage"
            )
        requirement_features.add(feature)
    return {"provider": provider, "protocol": PROTOCOL, "exports": exports, "requirements": requirements,
            "export_features": sorted(export_features)}


def normalize_requirement_closure(
    declarations: dict[str, dict[str, Any]],
    providers: tuple[str, ...] | list[str] | None = None,
) -> list[dict[str, Any]]:
    """Project provider requirements into a deterministic, provider-bound closure."""
    names = tuple(providers or declarations)
    if set(names) != set(declarations):
        raise CapabilityError("requirement closure providers do not match declarations")
    result: list[dict[str, Any]] = []
    for provider in names:
        declaration = declarations[provider]
        if declaration.get("provider") != provider:
            raise CapabilityError(f"requirement closure has a misbound {provider} declaration")
        for item in declaration.get("requirements", []):
            result.append({
                "provider": provider,
                "feature": item["feature"],
                "required": item["required"],
                "fallback": item["fallback"],
            })
    result.sort(key=lambda item: (names.index(item["provider"]), item["feature"]))
    return result


def validate_catalog_closure(declaration: dict[str, Any], *, document_count: int, asset_count: int) -> None:
    """Ensure the declaration names the kinds actually sent through the Bundle."""
    kinds = {item["kind"] for item in declaration["exports"]}
    if document_count and not kinds.intersection({"document", "catalog"}):
        raise CapabilityError(f"{declaration['provider']} declares no document/catalog export")
    if asset_count and "asset" not in kinds and "record" not in kinds:
        raise CapabilityError(f"{declaration['provider']} declares no asset/record export")
