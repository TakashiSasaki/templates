#!/usr/bin/env python3
"""Offline record validation and deterministic, non-normative discovery projections."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path, PurePosixPath
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry
from referencing.exceptions import NoSuchResource

ROOT = Path(__file__).resolve().parents[1]
OWNER = "https://github.com/TakashiSasaki/templates/tree/modeling"
SCHEMAS = {
    "record": "schemas/resource-record-0.1.schema.json",
    "collection": "schemas/collection-0.1.schema.json",
}


class CatalogError(ValueError):
    """An input or projection violates the local catalog contract."""


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CatalogError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def safe_file(root: Path, relative: str) -> Path:
    """Require a normalized contained regular file, with no symlink components."""
    part = PurePosixPath(relative)
    if not relative or "\\" in relative or part.is_absolute() or part.as_posix() != relative or any(p in (".", "..") for p in part.parts):
        raise CatalogError(f"unsafe relative path: {relative!r}")
    current = root
    for name in part.parts:
        current = current / name
        if current.is_symlink():
            raise CatalogError(f"symlink is not allowed: {relative}")
    if not current.is_file() or not current.resolve().is_relative_to(root.resolve()):
        raise CatalogError(f"missing, non-file, or escaping path: {relative}")
    return current


def read_json(root: Path, relative: str) -> Any:
    try:
        return json.loads(safe_file(root, relative).read_text(encoding="utf-8"), object_pairs_hook=_unique_pairs,
                          parse_constant=lambda value: (_ for _ in ()).throw(CatalogError(f"non-JSON constant: {value}")))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CatalogError(f"{relative}: {exc}") from exc


def _deny_remote(uri: str) -> Any:
    raise NoSuchResource(ref=uri)


def _validator(root: Path, kind: str) -> Draft202012Validator:
    schema = read_json(root, SCHEMAS[kind])
    try:
        Draft202012Validator.check_schema(schema)
    except Exception as exc:
        raise CatalogError(f"invalid {kind} schema: {exc}") from exc
    return Draft202012Validator(schema, format_checker=FormatChecker(), registry=Registry(retrieve=_deny_remote))


def _paths(root: Path, folder: str) -> list[str]:
    directory = root / folder
    if directory.is_symlink() or not directory.is_dir():
        raise CatalogError(f"missing or unsafe directory: {folder}")
    files = sorted(directory.iterdir())
    if not files:
        raise CatalogError(f"empty input directory: {folder}")
    for path in files:
        if path.suffix != ".json" or not path.is_file() or path.is_symlink():
            raise CatalogError(f"unexpected catalog input: {path.name}")
    return [f"{folder}/{path.name}" for path in files]


def _validate_document(validator: Draft202012Validator, data: Any, path: str) -> None:
    try:
        errors = list(validator.iter_errors(data))
    except Exception as exc:
        raise CatalogError(f"{path}: validation could not complete: {exc}") from exc
    if errors:
        error = errors[0]
        location = "/".join(str(p) for p in error.absolute_path)
        raise CatalogError(f"{path}:{location}: {error.message}")


def load(root: Path = ROOT) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    root = root.resolve()
    record_validator = _validator(root, "record")
    records = []
    by_id: dict[str, dict[str, Any]] = {}
    by_resource: dict[str, dict[str, Any]] = {}
    for path in _paths(root, "records"):
        record = read_json(root, path)
        _validate_document(record_validator, record, path)
        key = record["id"]
        if key != Path(path).stem or key in by_id:
            raise CatalogError(f"{path}: duplicate or filename-mismatched record id")
        if record["resourceId"] in by_resource:
            raise CatalogError(f"{path}: duplicate resource identity")
        by_id[key] = record
        by_resource[record["resourceId"]] = record
        editions = [edition["id"] for edition in record["editions"]]
        if len(editions) != len(set(editions)):
            raise CatalogError(f"{path}: duplicate edition id")
        distribution_ids = [dist["id"] for dist in record["distributions"]]
        if len(distribution_ids) != len(set(distribution_ids)):
            raise CatalogError(f"{path}: duplicate distribution id")
        for check in record["provenance"]["sourceChecks"]:
            if check["observedOn"] is not None and check["observedOn"] > record["provenance"]["recordedOn"]:
                raise CatalogError(f"{path}: observation postdates record")
        for dist in record["distributions"]:
            if dist["edition"] is not None and dist["edition"] not in editions:
                raise CatalogError(f"{path}: distribution names an unknown edition")
            retrieval = dist["retrieval"]
            if retrieval["mode"] == "local":
                artifact = safe_file(root, retrieval["path"])
                actual = hashlib.sha256(artifact.read_bytes()).hexdigest()
                if actual != retrieval["sha256"]:
                    raise CatalogError(f"{path}: local artifact digest mismatch")
        records.append(record)
    for record in records:
        for relation in record["relationships"]:
            local = relation["assertedBy"]["id"] == OWNER
            if local != (relation["assertionOrigin"] == "local"):
                raise CatalogError(f"{record['id']}: inconsistent assertion owner/origin")
            subject_editions = {e["id"] for e in record["editions"]}
            if relation["subjectEdition"] is not None and relation["subjectEdition"] not in subject_editions:
                raise CatalogError(f"{record['id']}: unknown relationship subject edition")
            target = by_resource.get(relation["object"])
            if target and relation["objectEdition"] is not None and relation["objectEdition"] not in {e["id"] for e in target["editions"]}:
                raise CatalogError(f"{record['id']}: unknown relationship object edition")
            if relation["normativity"] == "normative":
                observed = {c["url"] for c in record["provenance"]["sourceChecks"] if c["state"] == "metadata-observed"}
                if relation["subjectEdition"] is None or relation["objectEdition"] is None or not set(relation["evidence"]).issubset(observed):
                    raise CatalogError(f"{record['id']}: normative relationship requires editions and observed evidence")
    collection_validator = _validator(root, "collection")
    collections = []
    ids: set[str] = set()
    for path in _paths(root, "collections"):
        collection = read_json(root, path)
        _validate_document(collection_validator, collection, path)
        if collection["id"] in ids or collection["id"] != Path(path).stem:
            raise CatalogError(f"{path}: duplicate or filename-mismatched collection id")
        ids.add(collection["id"])
        missing = set(collection["members"]) - by_id.keys()
        if missing:
            raise CatalogError(f"{path}: unknown members: {sorted(missing)}")
        collections.append(collection)
    return records, collections


def _md(text: str) -> str:
    return text.replace("\\", "\\\\").replace("|", "\\|").replace("[", "\\[").replace("]", "\\]").replace("<", "&lt;").replace(">", "&gt;").replace("\n", " ").replace("\r", " ")


def render(record: dict[str, Any]) -> str:
    ja = record["canonicalLanguage"] == "ja"
    labels = ("識別と規範的所有者", "版", "配布物と参照", "確認範囲", "注意事項") if ja else ("Identity and normative owner", "Editions", "Distributions and references", "Verification scope", "Cautions")
    out = [f"# {_md(record['title'])}", "", "<!-- Generated from records/" + record["id"] + ".json; do not edit. -->", "", record["description"], "", f"## {labels[0]}", ""]
    if ja:
        out += [f"記述レコード: `{record['id']}`。記述の所有者: Modeling。", f"対象の規範的所有者: [{_md(record['normativeAuthority']['name'])}]({record['normativeAuthority']['id']})。", f"対象の参照先: {record['resourceId']}", "登録は発見のためのものであり、採用・推奨・規範的所有権の移譲を意味しない。"]
    else:
        out += [f"Record: `{record['id']}`; record authority: Modeling.", f"Normative owner of subject: [{_md(record['normativeAuthority']['name'])}]({record['normativeAuthority']['id']}).", f"Resource reference: {record['resourceId']}", "Registration is for discovery, not adoption, endorsement, or transfer of normative ownership."]
    out += ["", f"## {labels[1]}", ""]
    for edition in record["editions"]:
        out.append(f"- [{_md(edition['label'])}]({edition['id']}): {_md(edition['status'])}. {_md(edition['notes'])}")
    if not record["editions"]:
        out.append("特定版を固定していない。" if ja else "No specific edition is pinned by this record.")
    out += ["", f"## {labels[2]}", ""]
    for dist in record["distributions"]:
        retrieval = dist["retrieval"]
        target = retrieval["downloadUrl"] or retrieval["accessUrl"] if retrieval["mode"] == "reference" else "../../" + retrieval["path"]
        out.append(f"- [{_md(dist['id'])}]({target}) — `{dist['role']}`, `{dist['mediaType']}`, `{dist['language']}`.")
    out.append("配布物の権利情報はレコードに個別に記録する。未確認の利用許諾を推定しない。" if ja else "Rights are assessed per distribution in the record. Unassessed rights do not imply permission to redistribute.")
    out += ["", f"## {labels[3]}", ""]
    for check in record["provenance"]["sourceChecks"]:
        state = check["state"]
        if ja: state = "記述情報のみ確認" if state == "metadata-observed" else "参照先の内容は未確認"
        date = check["observedOn"] or ("確認日なし" if ja else "not observed")
        out += [f"- [{_md(state)}]({check['url']}) ({date}): {_md(check['scope'])}"]
    out += ["", f"## {labels[4]}", ""] + ["- " + _md(note) for note in record["notes"]]
    return "\n".join(out) + "\n"


def outputs(root: Path, records: list[dict[str, Any]], collections: list[dict[str, Any]]) -> dict[str, str]:
    result: dict[str, str] = {}
    index: dict[str, Any] = {"formatVersion": 1, "kind": "generated-discovery-index", "membershipMeaning": "discovery-not-dependency-or-adoption", "records": [], "collections": collections}
    lines = ["# Modeling discovery catalog", "", "<!-- Generated by tools/catalog.py; do not edit. -->", "", "Entries retain external normative ownership. Registration is not adoption or endorsement. External bodies are not mirrored. Source verification is scoped per record; unverified references are not described as checked. Canonical resource documentation follows its source language.", "", "[Generated resource documentation](docs/resources/index.md) provides the maintained next-step navigation for the generated record pages.", "", "| Record | Canonical language | Ownership | Source check |", "| --- | --- | --- | --- |"]
    for record in records:
        key = record["id"]
        source = "records/" + key + ".json"
        state = "metadata-observed" if any(c["state"] == "metadata-observed" for c in record["provenance"]["sourceChecks"]) else "reference-not-verified"
        lines.append(f"| [{_md(record['title'])}](docs/resources/{key}.md) | {record['canonicalLanguage']} | {record['ownership']} | {state} |")
        index["records"].append({"id": key, "resourceId": record["resourceId"], "source": source, "sourceSha256": hashlib.sha256(safe_file(root, source).read_bytes()).hexdigest(), "canonicalLanguage": record["canonicalLanguage"], "title": record["title"], "ownership": record["ownership"]})
        result[f"docs/resources/{key}.md"] = render(record)
    resource_paths = sorted(path for path in result if path.startswith("docs/resources/"))
    resource_index = [
        "<!-- generated by maintain-progressive-discovery -->",
        "# Modeling resource documentation index",
        "",
        "## Generated resource documentation",
        "",
    ]
    for path in resource_paths:
        resource_index.extend(
            [
                f"- [{path}]({Path(path).name}) - Declared by an authoritative inventory.",
                "",
            ]
        )
    result["docs/resources/index.md"] = "\n".join(resource_index)
    result["CATALOG.md"] = "\n".join(lines) + "\n"
    result["catalog.json"] = json.dumps(index, ensure_ascii=False, indent=2) + "\n"
    return result


def project(root: Path = ROOT, *, check: bool = True) -> tuple[int, int]:
    records, collections = load(root)
    expected = outputs(root, records, collections)
    generated_dir = root / "docs/resources"
    if (root / "docs").is_symlink() or generated_dir.is_symlink():
        raise CatalogError("generated resource directory or its ancestor is a symlink")
    actual = {p.relative_to(root).as_posix() for p in generated_dir.rglob("*") if p.is_file() or p.is_symlink()} if generated_dir.exists() else set()
    stale = actual - expected.keys()
    if stale:
        raise CatalogError(f"unexpected generated resource files; remove explicitly: {sorted(stale)}")
    for relative, content in expected.items():
        destination = root / relative
        current = root
        for part in PurePosixPath(relative).parts:
            current = current / part
            if current.is_symlink():
                raise CatalogError(f"unsafe generated output: {relative}")
        if check:
            if not destination.is_file() or destination.read_bytes() != content.encode("utf-8"):
                raise CatalogError(f"stale or missing generated output: {relative}; run generate")
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(content, encoding="utf-8", newline="\n")
    return len(records), len(collections)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "generate"))
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        count, collections = project(args.root.resolve(), check=args.command == "check")
    except (CatalogError, OSError, UnicodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"{args.command}: {count} records, {collections} collections; remote retrieval: disabled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
