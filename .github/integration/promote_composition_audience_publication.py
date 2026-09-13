#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROMOTED_IDS = (
    "composition-provider-maintenance",
    "composition-installer-release",
)
COMPOSITION_REVISION = "6b7d764c963f957c6bee43c0c1d42eb03970ec8f"


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    result = subprocess.run(
        [
            "python",
            "scripts/materialize_publication_staging.py",
            "--site-root",
            ".",
            "--staging-ids",
            ",".join(PROMOTED_IDS),
        ],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    staged_root = Path(result.stdout.strip()).resolve(strict=True)
    if staged_root.parent != ROOT.parent or not staged_root.name.startswith(f".{ROOT.name}.publication-staging-"):
        raise SystemExit(f"unexpected staging root: {staged_root}")
    shutil.copy2(staged_root / "site-manifest.json", ROOT / "site-manifest.json")
    shutil.copy2(staged_root / "reader-navigation-locales.json", ROOT / "reader-navigation-locales.json")

    sources_path = ROOT / "publication-sources.json"
    sources = json.loads(sources_path.read_text(encoding="utf-8"))
    sources["publications"]["composition"]["revision"] = COMPOSITION_REVISION
    write_json(sources_path, sources)

    staging_path = ROOT / "publication-staging.json"
    staging = json.loads(staging_path.read_text(encoding="utf-8"))
    selected = [mapping["id"] for mapping in staging["mappings"] if mapping["id"] in PROMOTED_IDS]
    if selected != list(PROMOTED_IDS):
        raise SystemExit(f"unexpected promoted staging mapping order: {selected}")
    staging["mappings"] = [mapping for mapping in staging["mappings"] if mapping["id"] not in PROMOTED_IDS]
    write_json(staging_path, staging)

    tests_path = ROOT / "tests/test_publication_staging.py"
    text = tests_path.read_text(encoding="utf-8")
    anchor = '''def _configure_composition_mappings(site_root: Path) -> None:\n    staging_path = site_root / "publication-staging.json"\n'''
    replacement = '''def _configure_composition_mappings(site_root: Path) -> None:\n    # Reconstruct the historical pre-promotion Site state so staging behavior\n    # remains regression-tested after these mappings become active authority.\n    manifest_path = site_root / "site-manifest.json"\n    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))\n\n    def remove_promoted(nodes):\n        retained = []\n        for node in nodes:\n            children = node.get("children")\n            if isinstance(children, list):\n                remove_promoted(children)\n                retained.append(node)\n            elif not (\n                node.get("publication") == "composition"\n                and node.get("document") in {"provider-maintenance", "installer-release"}\n            ):\n                retained.append(node)\n        nodes[:] = retained\n\n    remove_promoted(manifest["navigation"])\n    write = json.dumps(manifest, ensure_ascii=False, indent=2) + "\\n"\n    manifest_path.write_text(write, encoding="utf-8")\n\n    locales_path = site_root / "reader-navigation-locales.json"\n    locales = json.loads(locales_path.read_text(encoding="utf-8"))\n    for locale in locales["locales"]:\n        locale["labels"] = [\n            label for label in locale["labels"]\n            if label.get("id") not in COMPOSITION_STAGING_IDS\n        ]\n    write = json.dumps(locales, ensure_ascii=False, indent=2) + "\\n"\n    locales_path.write_text(write, encoding="utf-8")\n\n    staging_path = site_root / "publication-staging.json"\n'''
    if text.count(anchor) != 1:
        raise SystemExit(f"staging test fixture anchor count: {text.count(anchor)}")
    tests_path.write_text(text.replace(anchor, replacement, 1), encoding="utf-8")

    commit_test = ROOT / "tests/test_publication_staging_commit.py"
    text = commit_test.read_text(encoding="utf-8")
    old_import = "from tests.test_publication_staging import _copy_inputs, COMPOSITION_STAGING_IDS"
    new_import = "from tests.test_publication_staging import (\n    _configure_composition_mappings,\n    _copy_inputs,\n    COMPOSITION_STAGING_IDS,\n)"
    if text.count(old_import) != 1:
        raise SystemExit("staging commit import anchor mismatch")
    text = text.replace(old_import, new_import, 1)
    marker = "            _copy_inputs(root)\n"
    if text.count(marker) != 3:
        raise SystemExit(f"staging commit setup count: {text.count(marker)}")
    text = text.replace(marker, marker + "            _configure_composition_mappings(root)\n")
    commit_test.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
