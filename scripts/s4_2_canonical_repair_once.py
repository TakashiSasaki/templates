#!/usr/bin/env python3
"""One-shot Session 4.2 repair helper; removed by the repair commit."""
from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"expected repair anchor missing: {path}: {old[:80]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


def main() -> None:
    replace_once(
        "scripts/assemble_publications.py",
        'def load_manifest(path: Path) -> Manifest:\n    data = read_json(path, "site manifest")\n    schema_version = data.get("schema_version")\n',
        'def parse_manifest(data: dict[str, Any]) -> Manifest:\n    schema_version = data.get("schema_version")\n',
    )
    replace_once(
        "scripts/assemble_publications.py",
        '    raise AssemblyError("site manifest must be schema version 2 or 3")\n\n\ndef asset_entries',
        '    raise AssemblyError("site manifest must be schema version 2 or 3")\n\n\ndef load_manifest(path: Path) -> Manifest:\n    return parse_manifest(read_json(path, "site manifest"))\n\n\ndef asset_entries',
    )

    replace_once(
        "scripts/site_website_contract.py",
        'import argparse\nimport json\nfrom pathlib import Path\n',
        'import argparse\nimport json\nimport sys\nfrom pathlib import Path\n\nif __package__ in (None, ""):\n    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))\n\nfrom scripts.assemble_publications import AssemblyError, load_manifest\n',
    )
    target = Path("scripts/site_website_contract.py")
    text = target.read_text(encoding="utf-8")
    start = text.index('    manifest_data = read(root, "site-manifest.json")\n')
    end = text.index('    pages, routes, metadata = [], [], []\n', start)
    text = text[:start] + '''    try:\n        manifest = load_manifest(root / "site-manifest.json")\n    except AssemblyError as exc:\n        raise ValueError(str(exc)) from exc\n    navigation = manifest.documents\n''' + text[end:]
    target.write_text(text, encoding="utf-8")

    replace_once(
        "scripts/generate_repository_trees.py",
        'import re\nimport subprocess\nimport tomllib\n',
        'import re\nimport subprocess\nimport sys\nimport tomllib\n',
    )
    replace_once(
        "scripts/generate_repository_trees.py",
        'from urllib.parse import quote, quote_from_bytes, urlsplit\n\n\nNAME =',
        'from urllib.parse import quote, quote_from_bytes, urlsplit\n\nif __package__ in (None, ""):\n    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))\n\nfrom scripts.assemble_publications import AssemblyError, load_manifest\n\n\nNAME =',
    )
    target = Path("scripts/generate_repository_trees.py")
    text = target.read_text(encoding="utf-8")
    start = text.index('def manifest_destinations(site_root: Path) -> dict[tuple[str, str], str]:\n')
    end = text.index('\n\ndef published_sources(', start)
    text = text[:start] + '''def manifest_destinations(site_root: Path) -> dict[tuple[str, str], str]:\n    try:\n        manifest = load_manifest(site_root / "site-manifest.json")\n    except AssemblyError as exc:\n        raise RepositoryTreeError(str(exc)) from exc\n    return {\n        (document["publication"], document["document"]): document["destination"].as_posix()\n        for document in manifest.documents\n    }\n''' + text[end:]
    target.write_text(text, encoding="utf-8")

    replace_once(
        "scripts/prepare_repository_tree_publication.py",
        'import json\nimport shutil\nfrom pathlib import Path\n',
        'import json\nimport shutil\nimport sys\nfrom pathlib import Path\n',
    )
    replace_once(
        "scripts/prepare_repository_tree_publication.py",
        'from typing import Any, Iterable\n\nOUTPUT_MARKER =',
        'from typing import Any, Iterable\n\nif __package__ in (None, ""):\n    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))\n\nfrom scripts.assemble_publications import AssemblyError, parse_manifest\n\nOUTPUT_MARKER =',
    )
    target = Path("scripts/prepare_repository_tree_publication.py")
    text = target.read_text(encoding="utf-8")
    start = text.index('def augment_manifest(manifest: dict[str, Any]) -> dict[str, Any]:\n')
    end = text.index('\n\ndef prepare(site_root: Path, output_root: Path) -> list[str]:\n', start)
    replacement = '''def augment_manifest(manifest: dict[str, Any]) -> dict[str, Any]:\n    try:\n        validated = parse_manifest(manifest)\n    except AssemblyError as exc:\n        raise PreparationError(str(exc)) from exc\n    if validated.schema_version == 3:\n        return dict(manifest)\n\n    navigation = manifest["navigation"]\n    if any(\n        isinstance(node, dict) and node.get("title") == TREE_NAVIGATION["title"]\n        for node in navigation\n    ):\n        raise PreparationError(\n            "base site manifest must not predeclare generated repository trees"\n        )\n\n    result = dict(manifest)\n    result["navigation"] = [\n        navigation[0],\n        __import__("json").loads(__import__("json").dumps(TREE_NAVIGATION)),\n        *navigation[1:],\n    ]\n    return result\n'''
    text = text[:start] + replacement + text[end:]
    old = '    output_root = prepare_output_root(output_root, site_root)\n    copy_tree(site_root / "docs", output_root / "docs", "site docs")\n'
    new = '    manifest_data = read_json(manifest_path, "site manifest")\n    prepared_manifest = augment_manifest(manifest_data)\n\n    output_root = prepare_output_root(output_root, site_root)\n    copy_tree(site_root / "docs", output_root / "docs", "site docs")\n'
    if old not in text:
        raise SystemExit("prepare pre-write validation anchor missing")
    text = text.replace(old, new, 1)
    old = '    write_json(\n        prepared_manifest_path,\n        augment_manifest(read_json(manifest_path, "site manifest")),\n    )\n'
    new = '    write_json(\n        prepared_manifest_path,\n        prepared_manifest,\n    )\n'
    if old not in text:
        raise SystemExit("prepare manifest write anchor missing")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")

    replace_once(
        "tests/test_repository_trees.py",
        '                    "schema_version": 2,\n                    "navigation": [\n',
        '                    "schema_version": 2,\n                    "home": {"publication": "composition", "document": "overview"},\n                    "navigation": [\n',
    )
    replace_once(
        "tests/test_repository_file_previews.py",
        '                    "schema_version": 2,\n                    "navigation": [\n',
        '                    "schema_version": 2,\n                    "home": {"publication": "skill", "document": "overview"},\n                    "navigation": [\n',
    )

    Path("tests/test_canonical_manifest_consumer_boundaries.py").write_text('''from __future__ import annotations\n\nimport json\nimport shutil\nimport tempfile\nimport unittest\nfrom pathlib import Path\n\nfrom scripts import site_website_contract as website\nfrom scripts.generate_repository_trees import RepositoryTreeError, manifest_destinations\nfrom scripts.prepare_repository_tree_publication import PreparationError, prepare\n\nROOT = Path(__file__).resolve().parents[1]\n\n\nclass CanonicalManifestConsumerBoundaryTests(unittest.TestCase):\n    def production_manifest(self):\n        return json.loads((ROOT / "site-manifest.json").read_text(encoding="utf-8"))\n\n    def write_manifest(self, root, manifest):\n        root.mkdir(parents=True, exist_ok=True)\n        (root / "site-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")\n\n    def invalid_manifests(self):\n        incomplete = self.production_manifest()\n        incomplete.pop("audiences")\n        unsafe = self.production_manifest()\n        unsafe["documents"][1]["destination"] = "../outside.md"\n        return (("incomplete", incomplete), ("unsafe", unsafe))\n\n    def test_website_projection_uses_complete_canonical_validation(self):\n        for label, manifest in self.invalid_manifests():\n            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:\n                root = Path(tmp)\n                shutil.copy2(ROOT / "zensical.template.toml", root / "zensical.template.toml")\n                self.write_manifest(root, manifest)\n                with self.assertRaises(ValueError):\n                    website.documents(root)\n\n    def test_repository_tree_projection_uses_complete_canonical_validation(self):\n        for label, manifest in self.invalid_manifests():\n            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:\n                root = Path(tmp)\n                self.write_manifest(root, manifest)\n                with self.assertRaises(RepositoryTreeError):\n                    manifest_destinations(root)\n\n    def test_preparation_rejects_before_output_creation(self):\n        for label, manifest in self.invalid_manifests():\n            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:\n                root = Path(tmp) / "site"\n                output = Path(tmp) / "prepared"\n                self.write_manifest(root, manifest)\n                with self.assertRaises(PreparationError):\n                    prepare(root, output)\n                self.assertFalse(output.exists())\n\n\nif __name__ == "__main__":\n    unittest.main()\n''', encoding="utf-8")


if __name__ == "__main__":
    main()
