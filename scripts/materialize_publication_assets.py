#!/usr/bin/env python3
"""Materialize provider-owned publication build products before Site reads them.

Site owns only orchestration. A provider that needs build-time publication assets
exposes the conventional ``scripts/materialize_publication.py`` entrypoint. Site
does not know the provider's generator, semantic revision model, or output format.

Schema-v4 catalogs receive explicit source- then materialized-phase validation.
Schema-v3 providers may use the conventional materializer as a migration bridge;
after it runs, the existing strict v3 validator must pass.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from collections import OrderedDict
from pathlib import Path, PurePosixPath
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.publication_contract import (  # noqa: E402
    PublicationContractError,
    asset_files,
    load_publication_catalog,
    parse_name,
    read_json_object,
)
from scripts.publication_contract_v4 import load_publication_catalog_v4  # noqa: E402

MATERIALIZER = Path("scripts/materialize_publication.py")
CATALOG = Path("docs/publication-catalog.json")
STAMP_FILE = Path(".publication-materialization-stamp.json")
MATERIALIZATION_CACHE_LIMIT = 8
_SUCCESSFUL_MATERIALIZATIONS: OrderedDict[Path, str] = OrderedDict()


class PublicationMaterializationError(RuntimeError):
    """Raised when generic provider publication preparation cannot complete."""


def schema_version(root: Path, label: str) -> int:
    catalog = root / CATALOG
    if not catalog.is_file():
        raise PublicationMaterializationError(
            f"{label} has no publication catalog: {CATALOG}"
        )
    try:
        value = read_json_object(catalog, f"{label} catalog").get("schema_version")
    except PublicationContractError as exc:
        raise PublicationMaterializationError(str(exc)) from exc
    if type(value) is not int or value not in {3, 4}:
        raise PublicationMaterializationError(
            f"{label} publication catalog schema must be 3 or 4"
        )
    return value


def _strict_catalog(root: Path, label: str, version: int) -> Any:
    try:
        if version == 4:
            return load_publication_catalog_v4(
                root,
                label=f"{label} catalog",
                phase="materialized",
            )
        return load_publication_catalog(root, label=f"{label} catalog")
    except PublicationContractError as exc:
        raise PublicationMaterializationError(str(exc)) from exc


def validate(root: Path, label: str, version: int, *, phase: str) -> None:
    try:
        if version == 4:
            load_publication_catalog_v4(root, label=f"{label} catalog", phase=phase)
        elif phase == "materialized":
            load_publication_catalog(root, label=f"{label} catalog")
    except PublicationContractError as exc:
        raise PublicationMaterializationError(str(exc)) from exc


def run_materializer(root: Path, label: str) -> None:
    materializer = root / MATERIALIZER
    if materializer.is_symlink() or not materializer.is_file():
        raise PublicationMaterializationError(
            f"{label} requires a regular provider materializer at {MATERIALIZER}"
        )
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            str(materializer),
            "--source-root",
            str(root),
        ],
        cwd=root,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise PublicationMaterializationError(
            f"{label} publication materializer failed"
            + (f": {detail}" if detail else "")
        )


def _materialization_fingerprint(root: Path, materializer: Path) -> str:
    """Fingerprint mutation-sensitive lifecycle inputs for bounded reuse.

    The canonical resolved provider root is the cache key. The catalog and
    conventional provider entrypoint are additionally hashed so an in-place
    contract or materializer update cannot reuse a stale successful result.
    Every cache hit is still followed by strict materialized-phase validation.
    """
    digest = hashlib.sha256()
    for path in (root / CATALOG, materializer):
        try:
            payload = path.read_bytes()
        except OSError as exc:
            raise PublicationMaterializationError(
                f"unable to fingerprint publication materialization input {path}: {exc}"
            ) from exc
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(payload)
        digest.update(b"\0")
    return digest.hexdigest()


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    text = json.dumps(data, indent=2, sort_keys=True) + "\n"
    temp_path = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    try:
        temp_path.write_text(text, encoding="utf-8")
        temp_path.replace(path)
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass


def _provider_git_identity(root: Path) -> str:
    is_git_repo = (root / ".git").exists()
    try:
        git_proc = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        if git_proc.returncode == 0:
            sha = git_proc.stdout.strip()
            if len(sha) in (40, 64) and all(c in "0123456789abcdefABCDEF" for c in sha):
                return sha.lower()
        if is_git_repo:
            raise PublicationMaterializationError(
                f"unable to determine Git HEAD identity for provider at {root}"
            )
    except PublicationMaterializationError:
        raise
    except Exception as exc:
        if is_git_repo:
            raise PublicationMaterializationError(
                f"unable to determine Git HEAD identity for provider at {root}: {exc}"
            ) from exc
    return ""


def _provider_semantic_revision(root: Path) -> str:
    manifest_path = root / "generated" / "composition-playground-publication.json"
    if manifest_path.is_file() and not manifest_path.is_symlink():
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("semantic_revision"), str):
                return data["semantic_revision"]
        except Exception:
            pass
    return ""


def _check_reserved_stamp_collision(catalog: Any, label: str) -> None:
    reserved = PurePosixPath(STAMP_FILE.as_posix())
    for doc in getattr(catalog, "documents", ()):
        if PurePosixPath(doc.source) == reserved:
            raise PublicationMaterializationError(
                f"{label} document source collides with reserved stamp path: {doc.source}"
            )
    for asset in getattr(catalog, "assets", ()):
        if PurePosixPath(asset.source) == reserved or PurePosixPath(asset.destination) == reserved:
            raise PublicationMaterializationError(
                f"{label} asset collides with reserved stamp path: {reserved}"
            )


def _write_stamp(
    root: Path,
    label: str,
    version: int,
    fingerprint: str,
    catalog: Any,
) -> None:
    generated_digests: dict[str, str] = {}
    if version == 4:
        for asset in catalog.generated_assets:
            path = root / asset.source
            if asset.optional and not path.exists():
                continue
            field = f"{label} generated asset {asset.source}"
            try:
                files = asset_files(root, asset.source, field)
            except Exception:
                continue
            for p in sorted(files):
                if p.is_file() and not p.is_symlink():
                    generated_digests[p.relative_to(root).as_posix()] = hashlib.sha256(
                        p.read_bytes()
                    ).hexdigest()
    else:
        for asset in catalog.assets:
            path = root / asset.source
            if asset.optional and not path.exists():
                continue
            field = f"{label} asset {asset.source}"
            try:
                files = asset_files(root, asset.source, field)
            except Exception:
                continue
            for p in sorted(files):
                if p.is_file() and not p.is_symlink():
                    generated_digests[p.relative_to(root).as_posix()] = hashlib.sha256(
                        p.read_bytes()
                    ).hexdigest()

    git_revision = _provider_git_identity(root)
    semantic_rev = _provider_semantic_revision(root)
    stamp_data = {
        "stamp_version": 1,
        "canonical_root": str(root.resolve(strict=True)),
        "fingerprint": fingerprint,
        "git_revision": git_revision,
        "semantic_revision": semantic_rev,
        "generated_digests": generated_digests,
    }
    _atomic_write_json(root / STAMP_FILE, stamp_data)


def _validate_stamp(
    root: Path,
    label: str,
    version: int,
    fingerprint: str,
) -> Any | None:
    stamp_path = root / STAMP_FILE
    if stamp_path.is_symlink() or not stamp_path.is_file():
        return None
    try:
        data = json.loads(stamp_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("stamp_version") != 1:
            return None
        if data.get("canonical_root") != str(root.resolve(strict=True)):
            return None
        if data.get("fingerprint") != fingerprint:
            return None
        git_revision = _provider_git_identity(root)
        if data.get("git_revision", "") != git_revision:
            return None
        semantic_rev = _provider_semantic_revision(root)
        if semantic_rev and data.get("semantic_revision") != semantic_rev:
            return None
        generated_digests = data.get("generated_digests")
        if not isinstance(generated_digests, dict):
            return None
        for relative_path, expected_digest in generated_digests.items():
            path = root / relative_path
            if path.is_symlink() or not path.is_file():
                return None
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != expected_digest:
                return None
        catalog = _strict_catalog(root, label, version)
        if catalog is None:
            return None
        _check_reserved_stamp_collision(catalog, label)
        current_generated_files: set[str] = set()
        if version == 4:
            for asset in catalog.generated_assets:
                path = root / asset.source
                if asset.optional and not path.exists():
                    continue
                files = asset_files(root, asset.source, f"{label} generated asset {asset.source}")
                for p in files:
                    current_generated_files.add(p.relative_to(root).as_posix())
        else:
            for asset in catalog.assets:
                path = root / asset.source
                if asset.optional and not path.exists():
                    continue
                files = asset_files(root, asset.source, f"{label} asset {asset.source}")
                for p in files:
                    current_generated_files.add(p.relative_to(root).as_posix())
        if set(generated_digests.keys()) != current_generated_files:
            return None
        return catalog
    except Exception:
        return None


def is_publication_materialized(root: Path, label: str) -> bool:
    """Report whether a provider has a valid, verified materialization stamp."""
    try:
        root = root.resolve(strict=True)
        version = schema_version(root, label)
        materializer = root / MATERIALIZER
        if version == 4:
            catalog = load_publication_catalog_v4(root, label=f"{label} catalog", phase="source")
            if not catalog.generated_assets:
                catalog = _strict_catalog(root, label, version)
                if catalog is not None:
                    _check_reserved_stamp_collision(catalog, label)
                return catalog is not None
        else:
            if not materializer.is_file():
                catalog = _strict_catalog(root, label, version)
                if catalog is not None:
                    _check_reserved_stamp_collision(catalog, label)
                return catalog is not None
        fingerprint = _materialization_fingerprint(root, materializer)
        return _validate_stamp(root, label, version, fingerprint) is not None
    except Exception:
        return False


def _remember_success(root: Path, fingerprint: str) -> None:
    _SUCCESSFUL_MATERIALIZATIONS[root] = fingerprint
    _SUCCESSFUL_MATERIALIZATIONS.move_to_end(root)
    while len(_SUCCESSFUL_MATERIALIZATIONS) > MATERIALIZATION_CACHE_LIMIT:
        _SUCCESSFUL_MATERIALIZATIONS.popitem(last=False)


def _prepare_publication(root: Path, label: str) -> tuple[Any, bool]:
    root = root.resolve(strict=True)
    version = schema_version(root, label)
    materializer = root / MATERIALIZER

    if version == 4:
        try:
            catalog = load_publication_catalog_v4(
                root,
                label=f"{label} catalog",
                phase="source",
            )
        except PublicationContractError as exc:
            raise PublicationMaterializationError(str(exc)) from exc
        needs_materialization = bool(catalog.generated_assets)
        if needs_materialization and not materializer.is_file():
            raise PublicationMaterializationError(
                f"{label} declares generated publication assets but has no {MATERIALIZER}"
            )
        if materializer.exists() and (
            materializer.is_symlink() or not materializer.is_file()
        ):
            raise PublicationMaterializationError(
                f"{label} materializer must be a regular non-symlink file"
            )
    else:
        # Migration bridge: schema v3 cannot describe generation lifecycle.
        # Presence of the conventional provider entrypoint opts into the stage.
        if materializer.is_symlink():
            raise PublicationMaterializationError(
                f"{label} materializer must not be a symbolic link"
            )
        needs_materialization = materializer.is_file()

    if not needs_materialization:
        catalog = _strict_catalog(root, label, version)
        _check_reserved_stamp_collision(catalog, label)
        return catalog, False

    fingerprint = _materialization_fingerprint(root, materializer)
    stamped_catalog = _validate_stamp(root, label, version, fingerprint)
    if stamped_catalog is not None:
        _remember_success(root, fingerprint)
        return stamped_catalog, False

    _SUCCESSFUL_MATERIALIZATIONS.pop(root, None)
    (root / STAMP_FILE).unlink(missing_ok=True)

    run_materializer(root, label)
    catalog = _strict_catalog(root, label, version)
    _check_reserved_stamp_collision(catalog, label)
    _write_stamp(root, label, version, fingerprint, catalog)
    _remember_success(root, fingerprint)
    return catalog, True


def load_materialized_publication_catalog(root: Path, label: str) -> Any:
    """Return a strictly valid catalog after generic provider materialization."""
    catalog, _ = _prepare_publication(root, label)
    return catalog


def materialize_publication(root: Path, label: str) -> bool:
    """Prepare one provider root and report whether its materializer executed."""
    _, materialized = _prepare_publication(root, label)
    return materialized


def parse_publications(values: list[str]) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for index, value in enumerate(values):
        if "=" not in value:
            raise PublicationMaterializationError(
                f"--publication[{index}] must use NAME=PATH"
            )
        name, raw_path = value.split("=", 1)
        try:
            name = parse_name(name, f"--publication[{index}].name")
        except PublicationContractError as exc:
            raise PublicationMaterializationError(str(exc)) from exc
        if not raw_path or name in result:
            raise PublicationMaterializationError(
                f"invalid or duplicate publication: {value!r}"
            )
        result[name] = Path(raw_path)
    if not result:
        raise PublicationMaterializationError("at least one --publication is required")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publication", action="append", default=[])
    args = parser.parse_args()
    try:
        publications = parse_publications(args.publication)
        materialized = []
        for name, root in sorted(publications.items()):
            if materialize_publication(root, name):
                materialized.append(name)
        print(
            "validated provider publication build products; materialized="
            + (",".join(materialized) if materialized else "none")
        )
    except (PublicationMaterializationError, OSError, UnicodeError) as exc:
        print(f"materialize_publication_assets.py: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
