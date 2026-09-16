#!/usr/bin/env python3
"""Validate the assembled audience contract without importing a browser controller."""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from publication_bundle.paths import public_path

def validate_projection_parity(
    site_root: Path,
    model: dict,
    expected: dict,
    optional_destinations: set[str],
) -> None:
    documents = model.get("documents")
    routes = model.get("routes")
    assert isinstance(documents, dict), "assembled audience documents must be an object"
    assert isinstance(routes, dict), "assembled audience routes must be an object"

    expected_documents = expected["documents"]
    unexpected_documents = set(documents) - set(expected_documents)
    assert not unexpected_documents, f"unexpected assembled audience documents: {sorted(unexpected_documents)}"
    missing_required = set(expected_documents) - set(documents) - optional_destinations
    assert not missing_required, f"missing required audience documents: {sorted(missing_required)}"
    assert all(
        document == expected_documents[destination]
        for destination, document in documents.items()
    ), "assembled document audience projection drift"

    # Assembly may omit catalog documents whose optional source is absent. Keep
    # exactly the canonical routes for the documents that were actually built.
    expected_routes = {
        route: destination
        for route, destination in expected["routes"].items()
        if destination in documents
    }

    # Translation aliases are independently projected from actual published
    # records. Use that generated inventory, and require each alias to resolve to
    # an included canonical document with a real generated HTML page.
    reader_runtime = json.loads(
        (site_root / "reader-navigation-runtime.json").read_text(encoding="utf-8")
    )
    assert reader_runtime.get("schema_version") == 1, "invalid reader navigation runtime"
    assert isinstance(reader_runtime.get("locales"), list), "invalid reader locale inventory"
    aliases: dict[str, str] = {}
    for locale in reader_runtime["locales"]:
        assert isinstance(locale, dict) and isinstance(locale.get("routes"), dict), (
            "invalid reader locale routes"
        )
        for canonical_route, translated_route in locale["routes"].items():
            assert isinstance(canonical_route, str) and isinstance(translated_route, str), (
                "reader locale routes must be strings"
            )
            destination = expected_routes.get(canonical_route)
            assert destination is not None, f"translation aliases omitted document: {canonical_route}"
            assert (
                translated_route.startswith("/")
                and not translated_route.startswith("//")
                and translated_route.endswith("/")
                and ".." not in translated_route.split("/")
                and urlsplit(translated_route).path == translated_route
            ), f"invalid translated route: {translated_route}"
            html = site_root / translated_route.lstrip("/") / "index.html"
            assert html.is_file(), f"translation alias has no published page: {translated_route}"
            for alias in (translated_route, translated_route + "index.html"):
                previous = aliases.setdefault(alias, destination)
                assert previous == destination, f"conflicting translation alias: {alias}"

    complete_expected_routes = {**expected_routes, **aliases}
    assert routes == complete_expected_routes, "assembled audience route projection drift"


def skipped_optional_destinations(
    manifest,
    catalogs: dict[str, dict],
    publication_roots: dict[str, Path],
) -> set[str]:
    """Return destinations assembly may skip because an optional source is absent."""
    from scripts.publication_contract import resolve_without_symlinks

    skipped_destinations: set[str] = set()
    for document in manifest.documents:
        publication = document["publication"]
        catalog_document = catalogs[publication].get(document["document"])
        # Generated manifest documents have no provider-catalog record and are
        # required. Catalog-backed optional documents are skippable only when
        # the exact provider checkout lacks their declared source, matching the
        # successful assembly boundary rather than trusting the runtime output.
        if catalog_document is None or not catalog_document.optional:
            continue
        source = resolve_without_symlinks(
            publication_roots[publication],
            catalog_document.source,
            f"{publication}:{document['document']}",
        )
        if not source.exists():
            skipped_destinations.add(str(document["destination"]))
    return skipped_destinations



def check_artifact(site_root: Path, bundle: Path) -> dict:
    from site_renderer.bundle import validate_locked, load_lock
    validate_locked(bundle,load_lock(Path(__file__).resolve().parents[1]/'integration-source.json'))
    model=json.loads((site_root/'audience-runtime.json').read_text())
    expected=json.loads((bundle/'navigation.json').read_text())['audience_runtime']
    validate_projection_parity(site_root,model,expected,set())
    assert model["overviews"] == expected["overviews"], "assembled audience overview drift"
    assert model["audiences"] == ["use", "maintain"]
    # Every canonical published page must load the single generated controller.
    documents = model["documents"]
    for destination in documents:
        canonical_route = public_path(destination)
        assert model["routes"].get(canonical_route) == destination, (
            f"canonical route drift for {destination}: {canonical_route}"
        )
        html = site_root / canonical_route.lstrip("/") / "index.html"
        assert html.is_file(), f"missing canonical document: {html}"
        assert len(re.findall(r'<script\b[^>]*src="[^"]*javascripts/audience-context\.js"', html.read_text())) == 1, str(html)
    return model


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site-root', type=Path, required=True)
    parser.add_argument('--bundle',type=Path,required=True)
    args=parser.parse_args()
    model=check_artifact(args.site_root,args.bundle)
    print(json.dumps({'stage': 'audience-static', 'documents': len(model['documents'])}))


if __name__ == '__main__':
    main()
