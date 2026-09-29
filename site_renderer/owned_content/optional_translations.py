"""Publish optional reference translations without blocking canonical documents."""
from pathlib import Path
import shutil
import sys
import tempfile

from site_renderer.owned_content.publish_translations import publish_translations
from site_renderer.owned_content.translation_coverage import build_reader_coverage
from site_renderer.owned_content.translation_fragment_reconciliation import reconcile_translation_fragments


def publish_optional_translations(publications, pages, docs_root):
    accepted, records = {}, []
    for name, source in publications.items():
        selected = {name: source}
        with tempfile.TemporaryDirectory(prefix='optional-translations-') as temporary:
            staging = Path(temporary) / 'docs'
            shutil.copytree(docs_root, staging)
            try:
                candidates = publish_translations(selected, pages, staging)
                reconcile_translation_fragments(selected, pages, candidates, staging)
                build_reader_coverage(selected, pages)
            except (ValueError, RuntimeError, OSError) as exc:
                print(f'Reference translations omitted for {name}; canonical content is unchanged: {exc}', file=sys.stderr)
                continue
            for record in candidates:
                target = docs_root / record.translation_destination
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(staging / record.translation_destination, target)
            records.extend(candidates)
            accepted[name] = source
    coverage = build_reader_coverage(publications, pages, translation_publications=accepted)
    return records, coverage
