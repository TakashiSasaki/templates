"""Validate the derived translation projections carried by Publication Bundle v3."""
from pathlib import PurePosixPath

from publication_bundle.authority_content.publish_translations import derivative_destination
from publication_bundle.contract import BundleError, SHA, regular, safe_path


def validate_translations(root, coverage, publication, providers, documents):
    """Validate translation state without requiring provider source checkouts.

    Integration derives and authenticates the provider-owned translation manifests
    while producing the Bundle. The public consumer contract receives only that
    derived closure, its exact blob identities, and the published derivative files.
    """
    pages = {(d["publication"], d["document"]): d for d in documents if not d["slot"]}
    if (
        not isinstance(coverage, dict)
        or set(coverage)
        != {
            "schema_version",
            "canonical_language",
            "surface",
            "languages",
            "summary",
            "by_language",
            "records",
        }
        or coverage["schema_version"] != 1
        or coverage["canonical_language"] != "en"
        or coverage["surface"] != "reader"
    ):
        raise BundleError("invalid translation availability model")
    languages = coverage["languages"]
    if (
        not isinstance(languages, list)
        or len(set(languages)) != len(languages)
        or not all(isinstance(language, str) and language for language in languages)
        or not isinstance(coverage["records"], list)
    ):
        raise BundleError("invalid translation languages/records")
    for language in languages:
        safe_path(language)

    expected = {}
    seen = set()
    counts = {"current": 0, "stale": 0, "missing": 0}
    by_language = {language: dict(counts) for language in languages}
    for record in coverage["records"]:
        required = {
            "publication",
            "document",
            "language",
            "canonical_source",
            "canonical_destination",
            "status",
        }
        if not isinstance(record, dict) or not required <= record.keys():
            raise BundleError("incomplete Integration translation record")
        key = (record["publication"], record["document"])
        language = record["language"]
        status = record["status"]
        document = pages.get(key)
        if (
            document is None
            or key[0] not in providers
            or language not in by_language
            or status not in counts
            or (key[0], key[1], language) in seen
            or record["canonical_source"] != document["source"]
            or record["canonical_destination"] != document["destination"]
        ):
            raise BundleError("misbound Integration translation record")
        safe_path(record["canonical_source"])
        safe_path(record["canonical_destination"])
        seen.add((key[0], key[1], language))
        counts[status] += 1
        by_language[language][status] += 1
        if status in {"current", "stale"}:
            if not {
                "translation_source",
                "canonical_blob_sha",
                "current_blob_sha",
            } <= record.keys():
                raise BundleError("missing translation evidence")
            safe_path(record["translation_source"])
            if any(
                not isinstance(record[field], str) or not SHA.fullmatch(record[field])
                for field in ("canonical_blob_sha", "current_blob_sha")
            ):
                raise BundleError("invalid translation evidence")
            expected[(key[0], language, record["canonical_destination"])] = record
        elif {
            "translation_source",
            "canonical_blob_sha",
            "current_blob_sha",
        } & record.keys():
            raise BundleError("missing translation has declared evidence")

    if counts != coverage["summary"] or by_language != coverage["by_language"]:
        raise BundleError("inconsistent translation summary")
    if seen != {
        (publication, document, language)
        for publication, document in pages
        for language in languages
    }:
        raise BundleError("incomplete translation coverage projection")

    if (
        not isinstance(publication, dict)
        or set(publication)
        != {"schema_version", "canonical_language", "translations"}
        or publication["schema_version"] != 1
        or publication["canonical_language"] != "en"
        or not isinstance(publication["translations"], list)
    ):
        raise BundleError("invalid translation publication map")

    actual = set()
    destinations = set()
    canonical_destinations = {d["destination"] for d in documents}
    for record in publication["translations"]:
        if not isinstance(record, dict) or set(record) != {
            "publication",
            "language",
            "canonical_destination",
            "translation_destination",
        }:
            raise BundleError("invalid derivative record")
        key = (
            record["publication"],
            record["language"],
            record["canonical_destination"],
        )
        target = safe_path(record["translation_destination"]).as_posix()
        if (
            key not in expected
            or key in actual
            or target in destinations
            or target in canonical_destinations
        ):
            raise BundleError("duplicate/unqualified derivative")
        expected_target = derivative_destination(
            record["language"], PurePosixPath(record["canonical_destination"])
        ).as_posix()
        if target != expected_target:
            raise BundleError(
                "derivative destination differs from manifest-derived publication path"
            )
        actual.add(key)
        destinations.add(target)
        regular(root, "publication/" + target)
    if actual != set(expected):
        raise BundleError("missing declared derivative")

    actual_files = {
        path.relative_to(root / "publication").as_posix()
        for language in languages
        for path in (root / "publication" / language).rglob("*")
        if path.is_file()
    }
    if actual_files != destinations:
        raise BundleError("unexpected/missing derivative publication files")

    expected_markdown = {
        d["destination"] for d in documents if not d["slot"]
    } | destinations
    actual_markdown = {
        path.relative_to(root / "publication").as_posix()
        for path in (root / "publication").rglob("*")
        if path.is_file() and path.suffix.lower() == ".md"
    }
    if actual_markdown != expected_markdown:
        raise BundleError("unaccounted/missing Markdown publication files")
