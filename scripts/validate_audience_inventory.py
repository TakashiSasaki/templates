#!/usr/bin/env python3
"""Validate the design inventory against its exact audited Git objects.

This is not a production manifest reader. It never checks out an authority,
changes a publication lock, or executes code from the historical revisions.
"""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError, ValidationError

try:
    from .publication_contract import (
        PublicationContractError, parse_publication_catalog, read_json_object,
        safe_relative_path,
    )
except ImportError:
    from publication_contract import (
        PublicationContractError, parse_publication_catalog, read_json_object,
        safe_relative_path,
    )

ROOT = Path(__file__).resolve().parents[1]
AREA = ROOT / "docs/architecture/audience"
FORMATS = FormatChecker()


@FORMATS.checks("date-time", raises=ValueError)
def utc_timestamp(value):
    # Do not silently depend on jsonschema's optional RFC3339 extra being installed.
    if not isinstance(value, str):
        return True  # The schema's type constraint reports this error.
    datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    return True


class InventoryError(ValueError):
    """The inventory or its immutable evidence is incomplete or inconsistent."""


def require(condition, message):
    if not condition:
        raise InventoryError(message)


def validate_structure(matrix, schema):
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema, format_checker=FORMATS).validate(matrix)
    memberships = {}
    for authority, rows in matrix["documents"].items():
        sources = set()
        for identifier, row in rows.items():
            identity = f"{authority}:{identifier}"
            require(row["notes"].strip(), f"{identity}: empty decision rationale")
            source = row["source"]
            if source is not None:
                safe_relative_path(source, identity)
                require(source not in sources, f"{identity}: duplicated canonical source")
                sources.add(source)
            if row["current_destination"]:
                safe_relative_path(row["current_destination"], identity)
            audiences = {row["primary_audience"], *row["additional_audiences"]}
            require(
                {nav["audience"] for nav in row["proposed_navigation"]} == audiences,
                f"{identity}: navigation must cover exactly the declared audiences",
            )
            for nav in row["proposed_navigation"]:
                require(all(label.strip() == label and label for label in nav["path"]),
                        f"{identity}: empty or padded navigation label")
                key = (nav["audience"], tuple(nav["path"]))
                require(key not in memberships, f"{identity}: conflicting navigation path {key}")
                memberships[key] = identity
            owner_action = row["site_action"] if authority == "site" else row["provider_action"]
            if row["status"] == "candidate":
                expected = "publish-existing" if source else "author-and-publish"
                require(owner_action == expected, f"{identity}: candidate needs {expected}")
            else:
                sufficient = row["provider_action"] == "none" and row["site_action"] == "project"
                require(row["site_projection_sufficient"] == sufficient,
                        f"{identity}: projection sufficiency contradicts required action")
            require(row["status"] != "generated" or authority == "site",
                    f"{identity}: generated tree documents are Site-owned")


class GitEvidence:
    def __init__(self, repository):
        self.repository = Path(repository)

    def git(self, *args):
        result = subprocess.run(
            ["git", "--no-replace-objects", "-C", str(self.repository), *args],
            capture_output=True, check=False,
        )
        if result.returncode:
            raise InventoryError(
                f"Git evidence unavailable for {args}: {result.stderr.decode('utf-8', errors='replace').strip()}"
            )
        return result.stdout

    def commit(self, revision):
        require(self.git("cat-file", "-t", revision).strip() == b"commit",
                f"audited revision is not a commit: {revision}")

    def read(self, revision, path):
        safe_relative_path(path, "audited source")
        record = self.git("ls-tree", "-z", revision, "--", path)
        require(record.endswith(b"\0") and record.count(b"\0") == 1,
                f"missing audited regular file: {revision}:{path}")
        metadata, actual_path = record[:-1].split(b"\t", 1)
        mode, kind, blob = metadata.split()
        require(mode in (b"100644", b"100755") and kind == b"blob"
                and actual_path.decode("utf-8") == path,
                f"audited source is not a regular file: {revision}:{path}")
        return self.git("cat-file", "blob", blob.decode("ascii"))


def tree_declarations(raw):
    """Read literal declaration data, never import/execute historical scripts."""
    names = {"TREE_DOCUMENTS", "TREE_NAVIGATION"}
    found = {}
    for node in ast.parse(raw.decode("utf-8")).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in names:
                    require(target.id not in found, "duplicate generated declaration")
                    found[target.id] = ast.literal_eval(node.value)
    require(found.keys() == names, "audited tree declaration contract changed")
    return found["TREE_DOCUMENTS"], found["TREE_NAVIGATION"]


def derive_surface(matrix, evidence):
    """Union three exact catalogs and exact Site-generated/manifest exposure."""
    audit = matrix["audit"]
    revisions = audit["revisions"]
    for revision in revisions.values():
        evidence.commit(revision)
    with tempfile.TemporaryDirectory(prefix="audience-evidence-") as temporary:
        scratch = Path(temporary) / "input.json"

        def read_json(authority, path):
            scratch.write_bytes(evidence.read(revisions[authority], path))
            return read_json_object(scratch, f"{authority}:{path}")

        surface = {}
        for authority, revision in revisions.items():
            scratch.write_bytes(evidence.read(revision, audit["catalog_path"]))
            catalog = parse_publication_catalog(scratch, label=f"{authority} audited catalog")
            for document in catalog.documents:
                source = document.source.as_posix()
                evidence.read(revision, source).decode("utf-8")
                surface[(authority, document.document_id)] = {
                    "source": source, "status": "published",
                }
        manifest = read_json("site", audit["site_manifest_path"])
        require(manifest.get("schema_version") == 2, "audited Site manifest version changed")
        lock = read_json("site", audit["provider_lock_path"])
        require(lock.get("repository") == audit["repository"] and lock.get("schema_version") == 1,
                "malformed audited provider lock")
        require(set(lock["publications"]) == {"composition", "policy"}, "unknown locked authority")
        for authority in ("composition", "policy"):
            require(lock["publications"][authority]["revision"] == revisions[authority],
                    "audited provider head differs from publication lock; inventory needs a separately bound surface")
        generated, tree_nav = tree_declarations(evidence.read(
            revisions["site"], audit["generated_publication_path"],
        ))
        for document in generated:
            key = ("site", document["id"])
            require(key not in surface, f"duplicate generated identity {key}")
            evidence.read(revisions["site"], document["source"]).decode("utf-8")
            surface[key] = {"source": document["source"], "status": "generated"}

        exposed = set()
        destinations = set()

        def walk(nodes, prefix=()):
            for node in nodes:
                path = [*prefix, node["title"]]
                if "children" in node:
                    walk(node["children"], path)
                    continue
                key = (node["publication"], node["document"])
                require(key in surface, f"manifest references uncataloged document {key}")
                require(key not in exposed, f"duplicate audited manifest identity {key}")
                destination = node["destination"]
                safe_relative_path(destination, "audited destination")
                require(destination not in destinations, f"duplicate destination {destination}")
                exposed.add(key)
                destinations.add(destination)
                surface[key].update(current_destination=destination, current_navigation=[path])

        walk(manifest["navigation"])
        walk([tree_nav])
        require(exposed == set(surface), f"catalog/manifest exposure mismatch: {set(surface) - exposed}")
        home = manifest["home"]
        require((home["publication"], home["document"]) in exposed, "missing manifest home")
        return surface


def validate_inventory(matrix, schema, evidence):
    validate_structure(matrix, schema)
    surface = derive_surface(matrix, evidence)
    actual = {(a, i): row for a, rows in matrix["documents"].items() for i, row in rows.items()}
    published = {key for key, row in actual.items() if row["status"] != "candidate"}
    require(published == set(surface),
            f"publication coverage mismatch: missing={sorted(set(surface) - published)}, "
            f"nonexistent={sorted(published - set(surface))}")
    for key, expected in surface.items():
        for field, value in expected.items():
            require(actual[key][field] == value, f"{key}: audited {field} mismatch")
    for (authority, identifier), row in actual.items():
        if row["status"] == "candidate" and row["source"] is not None:
            evidence.read(matrix["audit"]["revisions"][authority], row["source"]).decode("utf-8")
    return {"published": len(surface), "candidates": len(actual) - len(surface),
            "audited_revisions": matrix["audit"]["revisions"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=ROOT)
    parser.add_argument("--matrix", type=Path, default=AREA / "migration-matrix.json")
    parser.add_argument("--schema", type=Path, default=AREA / "migration-matrix.schema.json")
    parser.add_argument("--fetch-audit", action="store_true",
                        help="fetch exact audit objects from the named public repository; never update authority refs")
    args = parser.parse_args()
    try:
        matrix = read_json_object(args.matrix, "audience matrix")
        schema = read_json_object(args.schema, "audience schema")
        validate_structure(matrix, schema)
        evidence = GitEvidence(args.repository)
        if args.fetch_audit:
            for revision in matrix["audit"]["revisions"].values():
                evidence.git("fetch", "--no-tags", "--no-write-fetch-head",
                             "https://github.com/TakashiSasaki/templates.git", revision)
        result = validate_inventory(matrix, schema, evidence)
        result["validated_checkout_head"] = evidence.git("rev-parse", "HEAD").decode().strip()
        result["checkout_dirty"] = bool(evidence.git("status", "--porcelain"))
        print(json.dumps(result, indent=2))
    except (InventoryError, PublicationContractError, ValidationError, SchemaError,
            OSError, UnicodeError, SyntaxError, ValueError, KeyError, TypeError) as exc:
        print(f"Audience inventory invalid: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
