#!/usr/bin/env python3
"""Report optional Japanese translation work without changing source or review evidence."""

import argparse
import hashlib
import json
from pathlib import Path


def blob(path):
    content = path.read_bytes()
    return hashlib.sha1(f"blob {len(content)}\0".encode() + content).hexdigest()


def report(root):
    catalog = json.loads((root / "docs/publication-catalog.json").read_text())
    path = root / "translations/manifest.json"
    diagnostics = []
    declared = {}
    try:
        manifest = json.loads(path.read_text()) if path.exists() else {"translations": []}
        for item in manifest["translations"]:
            if item["language"] == "ja" and "reader" in item["surfaces"]:
                for field in ("canonical", "translation", "canonical_blob_sha"):
                    if not isinstance(item[field], str):
                        raise ValueError(f"translation {field} must be a string")
                declared[item["canonical"]] = item
    except (OSError, ValueError, KeyError, TypeError) as exc:
        diagnostics.append(f"Reference metadata needs review: {exc}")
        declared = {}
    records = []
    for document in catalog["documents"]:
        source = document["source"]
        entry = declared.get(source)
        state = "missing"
        if entry and (root / entry["translation"]).is_file() and (root / source).is_file():
            state = "current" if blob(root / source) == entry["canonical_blob_sha"] else "stale"
        records.append(
            {
                "canonical": source,
                "status": state,
                "translation": entry["translation"] if entry else None,
            }
        )
    return {
        "canonical_language": "en",
        "reference_language": "ja",
        "summary": {
            state: sum(r["status"] == state for r in records)
            for state in ["current", "stale", "missing"]
        },
        "records": records,
        "diagnostics": diagnostics,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = report(args.root)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("Japanese reference translations:", result["summary"])
        for diagnostic in result["diagnostics"]:
            print(diagnostic)
        for item in result["records"]:
            print(f"{item['status']:8} {item['canonical']}")
        print(
            "Canonical changes may proceed. "
            "Update review hashes only after reviewing the translation."
        )


if __name__ == "__main__":
    main()
