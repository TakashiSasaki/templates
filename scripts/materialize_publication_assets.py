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
import os
import subprocess
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.publication_contract import (  # noqa: E402
    PublicationContractError,
    load_publication_catalog,
    parse_name,
    read_json_object,
)
from scripts.publication_contract_v4 import load_publication_catalog_v4  # noqa: E402

MATERIALIZER = Path("scripts/materialize_publication.py")
CATALOG = Path("docs/publication-catalog.json")


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


def materialize_publication(root: Path, label: str) -> bool:
    """Prepare one provider root and require strict post-materialization validity."""
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

    if needs_materialization:
        run_materializer(root, label)

    validate(root, label, version, phase="materialized")
    return needs_materialization


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
