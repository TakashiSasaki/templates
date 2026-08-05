#!/usr/bin/env python3
"""Assemble branch-owned publication catalogs into one Zensical project."""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path, PurePosixPath
from typing import Any

NAV_PLACEHOLDER = "__GENERATED_NAV__"
NAME = re.compile(r"\A[a-z0-9]+(?:-[a-z0-9]+)*\Z")

class AssemblyError(RuntimeError):
    pass

def read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise AssemblyError(f"unable to read {label} {path}: {exc}") from exc
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in pairs:
            if key in out:
                raise AssemblyError(f"{label} contains duplicate member: {key}")
            out[key] = value
        return out
    try:
        value = json.loads(text, object_pairs_hook=unique)
    except json.JSONDecodeError as exc:
        raise AssemblyError(f"unable to parse {label} {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise AssemblyError(f"{label} must be an object")
    return value

def safe_path(value: Any, field: str) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value:
        raise AssemblyError(f"{field} must be a safe relative POSIX path")
    if any(part in ("", ".", "..") for part in value.split("/")):
        raise AssemblyError(f"{field} must be a safe relative POSIX path")
    path = PurePosixPath(value)
    if path.is_absolute():
        raise AssemblyError(f"{field} must be a safe relative POSIX path")
    return path

def parse_name(value: Any, field: str) -> str:
    if not isinstance(value, str) or not NAME.fullmatch(value):
        raise AssemblyError(f"{field} must be lowercase kebab-case")
    return value

def resolve(root: Path, relative: PurePosixPath, field: str) -> Path:
    current = root
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise AssemblyError(f"{field} must not traverse a symlink: {relative}")
    return current

def load_catalog(name: str, root: Path) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    data = read_json(root / "docs/publication-catalog.json", f"{name} catalog")
    version = data.get("schema_version")
    if type(version) is not int or version not in (1, 2):
        raise AssemblyError(f"{name} catalog schema_version must be integer 1 or 2")
    allowed = {"schema_version", "documents"} | ({"assets"} if version == 2 else set())
    unknown = set(data) - allowed
    if unknown:
        raise AssemblyError(f"{name} catalog has unsupported fields: {', '.join(sorted(unknown))}")
    raw_docs = data.get("documents")
    if not isinstance(raw_docs, list) or not raw_docs:
        raise AssemblyError(f"{name} catalog documents must be a non-empty array")
    documents: dict[str, dict[str, Any]] = {}
    sources: set[PurePosixPath] = set()
    homes = 0
    for index, raw in enumerate(raw_docs):
        field = f"{name}.documents[{index}]"
        if not isinstance(raw, dict) or set(raw) != {"id", "source", "optional", "home"}:
            raise AssemblyError(f"{field} must contain id, source, optional, and home")
        doc_id = parse_name(raw["id"], f"{field}.id")
        source = safe_path(raw["source"], f"{field}.source")
        if source.suffix.lower() != ".md":
            raise AssemblyError(f"{field}.source must be Markdown")
        if not isinstance(raw["optional"], bool) or not isinstance(raw["home"], bool):
            raise AssemblyError(f"{field}.optional and home must be boolean")
        if doc_id in documents or source in sources:
            raise AssemblyError(f"{name} catalog document IDs and sources must be unique")
        if raw["home"]:
            homes += 1
            if raw["optional"]:
                raise AssemblyError(f"{name} catalog home must not be optional")
        documents[doc_id] = {"source": source, "optional": raw["optional"], "home": raw["home"]}
        sources.add(source)
    if homes != 1:
        raise AssemblyError(f"{name} catalog must define exactly one home")
    raw_assets = data.get("assets", [])
    if not isinstance(raw_assets, list):
        raise AssemblyError(f"{name} catalog assets must be an array")
    assets: list[dict[str, Any]] = []
    destinations: set[PurePosixPath] = set()
    for index, raw in enumerate(raw_assets):
        field = f"{name}.assets[{index}]"
        if not isinstance(raw, dict) or set(raw) != {"source", "destination", "optional"}:
            raise AssemblyError(f"{field} must contain source, destination, and optional")
        source = safe_path(raw["source"], f"{field}.source")
        destination = safe_path(raw["destination"], f"{field}.destination")
        if not isinstance(raw["optional"], bool) or destination in destinations:
            raise AssemblyError(f"{field} is invalid or duplicates a destination")
        destinations.add(destination)
        assets.append({"source": source, "destination": destination, "optional": raw["optional"]})
    return documents, assets

def parse_node(raw: Any, field: str) -> dict[str, Any]:
    if not isinstance(raw, dict) or not isinstance(raw.get("title"), str) or not raw["title"].strip():
        raise AssemblyError(f"{field} must have a non-empty title")
    if "children" in raw:
        if set(raw) != {"title", "children"} or not isinstance(raw["children"], list) or not raw["children"]:
            raise AssemblyError(f"{field} section must contain only title and non-empty children")
        return {"title": raw["title"].strip(), "children": [parse_node(v, f"{field}.children[{i}]") for i, v in enumerate(raw["children"])]}
    if set(raw) != {"title", "publication", "document", "destination"}:
        raise AssemblyError(f"{field} page must contain title, publication, document, and destination")
    return {
        "title": raw["title"].strip(),
        "publication": parse_name(raw["publication"], f"{field}.publication"),
        "document": parse_name(raw["document"], f"{field}.document"),
        "destination": safe_path(raw["destination"], f"{field}.destination"),
    }

def pages(nodes: list[dict[str, Any]]):
    for node in nodes:
        if "children" in node:
            yield from pages(node["children"])
        else:
            yield node

def load_manifest(path: Path) -> tuple[tuple[str, str], list[dict[str, Any]]]:
    data = read_json(path, "site manifest")
    if set(data) != {"schema_version", "home", "navigation"} or data.get("schema_version") != 2:
        raise AssemblyError("site manifest must be schema version 2 with home and navigation")
    home = data["home"]
    if not isinstance(home, dict) or set(home) != {"publication", "document"}:
        raise AssemblyError("site manifest home must identify publication and document")
    nav = data["navigation"]
    if not isinstance(nav, list) or not nav:
        raise AssemblyError(r"site manifest navigation must be non-empty")
    return (
        (parse_name(home["publication"], "home.publication"), parse_name(home["document"], "home.document")),
        [parse_node(v, f"navigation[{i}]") for i, v in enumerate(nav)],
    )

def copy_asset(source: Path, destination: Path, field: str) -> None:
    if source.is_symlink():
        raise AssemblyError(f"{field} must not be a symlink")
    entries = [source] if source.is_file() else list(source.rglob("*")) if source.is_dir() else []
    if not entries:
        raise AssemblyError(f"{field} does not exist or is empty: {source}")
    for item in entries:
        if item.is_symlink():
            raise AssemblyError(f"{field} contains a symlink: {item}")
        if not item.is_file():
            continue
        if item.suffix.lower() == ".md":
            raise AssemblyError(f"{field} contains undeclared Markdown: {item}")
        target = destination if source.is_file() else destination / item.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise AssemblyError(f"output collision: {target}")
        shutil.copy2(item, target)

def render_nav(nodes: list[dict[str, Any]], indent: int = 0) -> str:
    prefix, entry = " " * indent, " " * (indent + 2)
    values = []
    for node in nodes:
        title = json.dumps(node["title"], ensure_ascii=False)
        if "children" in node:
            values.append(f"{entry}{{{title} = {render_nav(node['children'], indent + 2)}}}")
        else:
            dest = json.dumps(node["destination"].as_posix(), ensure_ascii=False)
            values.append(f"{entry}{{{title} = {dest}}}")
    return "[\n" + ",\n".join(values) + f"\n{prefix}]"

def assemble(publication_roots: dict[str, Path], site_root: Path, output_root: Path) -> list[str]:
    site_root = site_root.resolve(strict=True)
    publications: dict[str, tuple[Path, dict[str, dict[str, Any]], list[dict[str, Any]]]] = {}
    for name, root in sorted(publication_roots.items()):
        root = root.resolve(strict=True)
        documents, assets = load_catalog(name, root)
        publications[name] = (root, documents, assets)
    home, navigation = load_manifest(site_root / "site-manifest.json")
    nav_pages = list(pages(navigation))
    seen: set[tuple[str, str] = set()
    destinations: set[PurePosixPath] = set()
    for page in nav_pages:
        key = (page["publication"], page["document"])
        if key in seen or page["destination"] in destinations:
            raise AssemblyError("site manifest document keys and destinations must be unique")
        seen.add(key); destinations.add(page["destination"])
        if key[0] not in publications or key[1] not in publications[key[0]][1]:
            raise AssemblyError(f"site manifest references unknown document: {key[0]}:{key[1]}")
    catalog_keys = {(name, doc_id) for name, (_, docs, _) in publications.items() for doc_id in docs}
    if seen != catalog_keys:
        missing = sorted(catalog_keys - seen); extra = sorted(seen - catalog_keys)
        raise AssemblyError("site manifest does not cover publication documents: " + ", ".join(f"{p}:{d}" for p, d in missing) if missing else "site manifest references extra publication documents: " + ", ".join(f"{p}:{d}" for p, d in extra))
    if not nav_pages or (nav_pages[0]["publication"], nav_pages[0]["document"]) != home or nav_pages[0]["destination"] != PurePosixPath("index.md"):
        raise AssemblyError("site home page must generate index.md")
    home_doc = publications[home[0]][1][home[1]]
    if not home_doc["home"]:
        raise AssemblyError("global home must be the selected publication home")
    if output_root.is_symlink():
        raise AssemblyError("output root must not be a symlink")
    if output_root.exists():
        shutil.rmtree(output_root)
    docs_root = output_root / "docs"; docs_root.mkdir(parents=True)
    included: list[dict[str, Any]] = []; skipped: set[tuple[str, str] = set()
    for page in nav_pages:
        root, docs, _ = publications[page["publication"]]
        doc = docs[page["document"]]
        source = resolve(root, doc["source"], f"{page['publication']}:{page['document']}")
        if not source.is_file():
            if doc["optional"] and not source.exists():
                skipped.add((page["publication"], page["document"])); continue
            raise AssemblyError(f"required publication document does not exist: {source}")
        target = docs_root.joinpath(*page["destination"].parts); target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists(): raise AssemblyError(f"output collision: {target}")
        shutil.copy2(source, target); included.append(page)
    def filter_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out = []
        for node in nodes:
            if "children" in node:
                children = filter_nodes(node["children"])
                if children: out.append({"title": node["title"], "children": children})
            elif (node["publication"], node["document"]) not in skipped:
                out.append(node)
        return out
    filtered = filter_nodes(navigation)
    for name, (root, _, assets) in publications.items():
        for asset in assets:
            source = resolve(root, asset["source"], f"{name} asset")
            if not source.exists() and asset["optional"]: continue
            copy_asset(source, docs_root / name / asset["destination"], f"{name} asset")
        # Catalog v1 predates explicit asset roots. Preserve its established
        # convention by publishing a provider-owned top-level assets directory.
        legacy_assets = root / "assets"
        if name != "site" and not assets and legacy_assets.is_dir():
            copy_asset(legacy_assets, docs_root / name / "assets", f"{name} legacy assets")
    site_assets = site_root / "assets"
    if site_assets.is_dir(): copy_asset(site_assets, docs_root, "site assets")
    template_path = site_root / "zensical.template.toml"
    template = template_path.read_text(encoding="utf-8")
    if template.count(NAV_PLACEHOLDER) != 1:
        raise AssemblyError(f"{template_path.name} must contain {NAV_PLACEHOLDER!r} exactly once")
    (output_root / "zensical.toml").write_text(template.replace(NAV_PLACEHOLDER, render_nav(filtered)), encoding="utf-8")
    result = [f"assembled {len(included)} page(s)", f"publications: {len(publications)}", f"catalog documents: {len(catalog_keys)}", f"output: {output_root.resolve()}"]
    if skipped: result.append("optional documents skipped: " + ", ".join(f"{p}:{d}" for p, d in sorted(skipped)))
    return result

def parse_publications(values: list[str]) -> dict[str, Path]:
    out: dict[str, Path] = {}
    for index, value in enumerate(values):
        if "=" not in value: raise AssemblyError(f"--publication[{index}] must use NAME=PATH")
        name, raw = value.split("=", 1); name = parse_name(name, f"--publication[{index}].name")
        if not raw or name in out: raise AssemblyError(f"invalid or duplicate publication: {value!r}")
        out[name] = Path(raw)
    if not out: raise AssemblyError("at least one --publication is required")
    return out

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--publication", action="append", default=[])
    parser.add_argument("--site-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    args = parser.parse_args()
    try:
        print("\n".join(assemble(parse_publications(args.publication), args.site_root, args.output_root)))
    except (AssemblyError, OSError) as exc:
        print(f"assemble_publications.py: {exc}", file=sys.stderr); return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
