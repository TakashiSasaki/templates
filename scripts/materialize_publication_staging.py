#!/usr/bin/env python3
"""Materialize explicit Site-owned publication mappings for compatibility builds."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterator

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.assemble_publications import AssemblyError, load_manifest, parse_name, safe_path
from scripts.prepare_repository_tree_publication import PreparationError, augment_manifest
from scripts.reader_navigation_locales import (
    LABEL_ID,
    LANGUAGE_TAG,
    ReaderNavigationLocaleError,
    load_overlays,
    navigation_titles,
)


from integration.staging import (
    PublicationStagingError,
    _read_json,
    _name,
    _destination,
    _walk_pages,
    _load_staging,
    _write_json,
    stage_models,
)














def _create_snapshot(
    site_root: Path,
    manifest: dict[str, Any],
    locales: dict[str, Any],
    original_manifest: bytes,
    original_locales: bytes,
) -> Path:
    """Create and validate an isolated staged Site root without replacing source files."""

    snapshot_root = Path(
        tempfile.mkdtemp(
            dir=site_root.parent,
            prefix=f".{site_root.name}.publication-staging-",
        )
    )
    try:
        shutil.copytree(site_root, snapshot_root, dirs_exist_ok=True, symlinks=True)
        snapshot_manifest = snapshot_root / "site-manifest.json"
        snapshot_locales = snapshot_root / "reader-navigation-locales.json"
        _write_json(snapshot_manifest, manifest)
        _write_json(snapshot_locales, locales)

        try:
            load_manifest(snapshot_manifest)
            staged_manifest = _read_json(snapshot_manifest, "materialized site manifest")
            prepared_navigation = augment_manifest(staged_manifest)["navigation"]
            load_overlays(snapshot_locales, prepared_navigation)
        except (AssemblyError, PreparationError, ReaderNavigationLocaleError) as exc:
            raise PublicationStagingError(
                f"materialized Site mapping failed canonical validation: {exc}"
            ) from exc

        # A source mutation while the private snapshot was being created makes the
        # qualification input ambiguous, so reject it. There is no destructive
        # rollback: the source checkout was never replaced.
        if (
            (site_root / "site-manifest.json").read_bytes() != original_manifest
            or (site_root / "reader-navigation-locales.json").read_bytes()
            != original_locales
        ):
            raise PublicationStagingError("Site mapping changed during staging")

        return snapshot_root
    except BaseException:
        shutil.rmtree(snapshot_root, ignore_errors=True)
        raise




def materialize_many(site_root: Path, staging_ids: list[str]) -> Path:
    original_manifest = (site_root / "site-manifest.json").read_bytes()
    original_locales = (site_root / "reader-navigation-locales.json").read_bytes()
    manifest, locales = stage_models(site_root, staging_ids)
    return _create_snapshot(site_root, manifest, locales, original_manifest, original_locales)


def materialize(site_root: Path, staging_id: str) -> Path:
    """Backward-compatible single-mapping API returning the qualification root."""

    return materialize_many(site_root, [staging_id])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site-root", required=True, type=Path)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--staging-id")
    selection.add_argument(
        "--staging-ids",
        help="comma-separated ordered staging IDs for one atomic compatibility build",
    )
    args = parser.parse_args()
    staging_ids = (
        [args.staging_id]
        if args.staging_id is not None
        else [item.strip() for item in args.staging_ids.split(",")]
    )
    try:
        snapshot_root = materialize_many(args.site_root, staging_ids)
    except (PublicationStagingError, OSError, UnicodeError) as exc:
        print(f"materialize_publication_staging.py: {exc}", file=sys.stderr)
        return 1
    print(snapshot_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
