#!/usr/bin/env python3
"""Audience context resolver and runtime state engine for templates publication."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path, PurePosixPath
from typing import Any

from publication_bundle.paths import public_path, audience_routes
from integration.publication_model import AssemblyError, Manifest, load_manifest

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "site-manifest.json"


class AudienceContextError(RuntimeError):
    """Raised when audience context resolution or runtime mapping fails."""


class AudienceContextResolver:
    """Normative audience context resolution engine conforming to audience-model.md."""

    def __init__(
        self,
        manifest: Manifest,
        *,
        documents: list[dict[str, Any]] | None = None,
    ) -> None:
        self.manifest = manifest
        self.documents = manifest.documents if documents is None else documents
        self.audiences = list(manifest.audiences)
        self.home_key = manifest.home
        self.landing_destination = PurePosixPath("index.md")

        # Map destinations (and normalized routes) to document entries
        self.docs_by_destination: dict[PurePosixPath, dict[str, Any]] = {}
        self.docs_by_route: dict[str, dict[str, Any]] = {}
        self.docs_by_key: dict[tuple[str, str], dict[str, Any]] = {}

        for doc in self.documents:
            dest = PurePosixPath(doc["destination"])
            self.docs_by_destination[dest] = doc
            self.docs_by_key[(doc["publication"], doc["document"])] = doc

        try:
            self.docs_by_route = {
                route: self.docs_by_destination[PurePosixPath(destination)]
                for route, destination in audience_routes(self.docs_by_destination).items()
            }
        except ValueError as exc:
            raise AudienceContextError(str(exc)) from exc

    def find_document(self, target: str | PurePosixPath) -> dict[str, Any] | None:
        """Find a canonical document by destination, route, or key."""
        if isinstance(target, PurePosixPath):
            return self.docs_by_destination.get(target)
        target_str = str(target).strip()
        if not target_str:
            return self.docs_by_destination.get(self.landing_destination)

        # Check direct route table
        if target_str in self.docs_by_route:
            return self.docs_by_route[target_str]

        # Strip query and fragment if present
        clean_target = target_str.split("?", 1)[0].split("#", 1)[0]
        if clean_target in self.docs_by_route:
            return self.docs_by_route[clean_target]

        # Check as PurePosixPath
        posix = PurePosixPath(clean_target.lstrip("/"))
        if posix in self.docs_by_destination:
            return self.docs_by_destination[posix]

        # Check as publication:document key
        if ":" in target_str:
            parts = target_str.split(":", 1)
            key = (parts[0].strip(), parts[1].strip())
            if key in self.docs_by_key:
                return self.docs_by_key[key]

        return None

    def is_landing_page(self, doc: dict[str, Any]) -> bool:
        """Check if the document is the root landing page."""
        dest = PurePosixPath(doc["destination"])
        key = (doc["publication"], doc["document"])
        return dest == self.landing_destination or key == self.home_key

    def resolve_audience(
        self,
        target: str | PurePosixPath,
        *,
        explicit_audience: str | None = None,
        current_journey: str | None = None,
        query_param: str | None = None,
    ) -> str | None:
        """Resolve the semantic audience according to the 4-step hierarchy in audience-model.md.

        Hierarchy:
        1. On root landing route, render neutral shell (None).
        2. Honor explicit supported audience if document belongs to that audience.
        3. Otherwise preserve existing journey context if document belongs to it.
        4. Otherwise choose document's primary audience.
        """
        doc = self.find_document(target)
        if doc is None:
            # Fallback for unrecognized route
            return None

        # Step 1: Root landing route renders neutral shell (None)
        if self.is_landing_page(doc):
            return None

        doc_primary = doc["primary_audience"]
        doc_audiences = {doc_primary, *doc.get("additional_audiences", [])}

        # Candidate explicit audience (query param takes precedence or explicit param)
        candidate_explicit = query_param or explicit_audience
        if candidate_explicit and candidate_explicit in self.audiences:
            # Step 2: Honor explicit supported audience if document belongs to it
            if candidate_explicit in doc_audiences:
                return candidate_explicit

        # Step 3: Preserve existing journey context if document belongs to it
        if current_journey and current_journey in self.audiences:
            if current_journey in doc_audiences:
                return current_journey

        # Step 4: Otherwise choose the document's primary audience
        return doc_primary

    def switch_audience(
        self,
        current_target: str | PurePosixPath,
        desired_audience: str,
        *,
        current_fragment: str = "",
    ) -> tuple[str, str | None]:
        """Calculate transition when switching to desired_audience.

        Returns (destination_route, resolved_audience):
        - If document declares desired_audience: stays on current document route, resolved_audience is desired_audience.
        - If document is single-audience: redirects to desired audience overview route, resolved_audience is desired_audience.
        """
        if desired_audience not in self.audiences:
            raise AudienceContextError(f"Invalid desired audience: {desired_audience}")

        doc = self.find_document(current_target)
        if doc is None or self.is_landing_page(doc):
            overview = self.get_audience_overview(desired_audience)
            return (overview, desired_audience)

        doc_audiences = {doc["primary_audience"], *doc.get("additional_audiences", [])}

        # Case 1: Document belongs to both audiences or desired audience
        if desired_audience in doc_audiences:
            dest = str(doc["destination"])
            route = f"{dest}{current_fragment}" if current_fragment else dest
            return (route, desired_audience)

        # Case 2: Document is single audience and not in desired audience -> redirect to overview
        overview = self.get_audience_overview(desired_audience)
        return (overview, desired_audience)

    def get_audience_overview(self, audience: str) -> str:
        """Return the canonical entry overview route for a given audience."""
        if audience == "use":
            # Primary entry for Use templates journey
            return "web/index.md"
        if audience == "maintain":
            # Primary entry for Maintain templates journey
            return "repository-trees/index.md"
        return "index.md"

    def export_runtime_map(self) -> dict[str, Any]:
        """Export runtime map for browser execution and static qualification."""
        doc_map: dict[str, Any] = {}
        for doc in self.documents:
            dest = str(doc["destination"])
            is_landing = self.is_landing_page(doc)
            doc_map[dest] = {
                "key": f"{doc['publication']}:{doc['document']}",
                "title": doc["title"],
                "destination": dest,
                "primary": doc["primary_audience"],
                "audiences": [doc["primary_audience"], *doc.get("additional_audiences", [])],
                "is_landing": is_landing,
            }

        routes_map: dict[str, str] = {}
        for route_str, doc in self.docs_by_route.items():
            routes_map[route_str] = str(doc["destination"])

        def project_navigation(nodes):
            result = []
            for node in nodes:
                if "children" in node:
                    children = project_navigation(node["children"])
                    if children:
                        result.append({"title": node["title"], "children": children})
                elif str(node["destination"]) in doc_map:
                    result.append({"title": node["title"], "destination": str(node["destination"]),
                                   "href": public_path(node["destination"])})
            return result

        return {
            "schema_version": 1,
            "navigation": {aud: project_navigation(self.manifest.navigation[aud]) for aud in self.audiences},
            "audiences": self.audiences,
            "landing_destination": str(self.landing_destination),
            "overviews": {
                aud: public_path(self.get_audience_overview(aud)) for aud in self.audiences
            },
            "documents": doc_map,
            "routes": routes_map,
        }


def write_runtime_map(path: Path, resolver: AudienceContextResolver) -> None:
    data = resolver.export_runtime_map()
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def create_resolver(manifest_path: Path = DEFAULT_MANIFEST) -> AudienceContextResolver:
    manifest = load_manifest(manifest_path)
    return AudienceContextResolver(manifest)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audience context resolution and runtime export.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST, help="Path to site-manifest.json")
    parser.add_argument("--resolve", type=str, help="Destination or route to resolve audience for")
    parser.add_argument("--explicit", type=str, help="Explicit audience candidate")
    parser.add_argument("--current", type=str, help="Current journey context")
    parser.add_argument("--query-param", type=str, help="Query parameter audience")
    parser.add_argument("--export-runtime-map", action="store_true", help="Print runtime map JSON")

    args = parser.parse_args(argv)
    resolver = create_resolver(args.manifest)

    if args.export_runtime_map:
        data = resolver.export_runtime_map()
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0

    if args.resolve:
        result = resolver.resolve_audience(
            args.resolve,
            explicit_audience=args.explicit,
            current_journey=args.current,
            query_param=args.query_param,
        )
        print(json.dumps({"target": args.resolve, "resolved_audience": result}))
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
