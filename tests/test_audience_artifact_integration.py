"""Exercise the real loader, assembly, translation publisher and static consumer."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.assemble_publications import assemble, load_catalog, load_manifest
from scripts.check_audience_artifact import check_artifact
from scripts.publish_translations import publish_translations, JA_NOTICE
from scripts.publish_provider_translations import extend_audience_routes
from scripts.reader_navigation_locales import build_runtime_map
from scripts.site_website_contract import public_path


class AudienceArtifactIntegrationTests(unittest.TestCase):
    def fixture(self, root: Path, optional_present: bool):
        source = root / 'source'
        source.mkdir()
        docs = source / 'docs'
        docs.mkdir()
        documents = []
        catalog = []
        for name in ('home', 'optional', 'generated'):
            destination = 'index.md' if name == 'home' else f'{name}/index.md'
            documents.append(dict(publication='site', document=name, title=name,
                                  destination=destination, primary_audience='use',
                                  additional_audiences=['maintain']))
            catalog.append(dict(id=name, source=f'docs/{name}.md',
                                optional=name == 'optional', home=name == 'home'))
            if name != 'optional' or optional_present:
                (docs / f'{name}.md').write_text(f'# {name}\n')
        manifest = dict(schema_version=3, audiences=['use', 'maintain'],
                        home=dict(publication='site', document='home'), documents=documents,
                        navigation={a: [{k: d[k] for k in ('publication', 'document', 'title', 'destination')}
                                        for d in documents] for a in ('use', 'maintain')})
        (source / 'site-manifest.json').write_text(json.dumps(manifest))
        catalog_path = docs / 'publication-catalog.json'
        catalog_path.write_text(json.dumps(dict(schema_version=3, documents=catalog)))
        (source / 'zensical.template.toml').write_text('site_name = "fixture"\nnav = __GENERATED_NAV__\n')
        translations = source / 'translations'
        translations.mkdir()
        (translations / 'ja/docs').mkdir(parents=True)
        (translations / 'ja/docs/home.md').write_text('# ホーム\n\n' + JA_NOTICE + '\n')
        content = (docs / 'home.md').read_bytes()
        blob = hashlib.sha1(f'blob {len(content)}\0'.encode() + content).hexdigest()
        (translations / 'manifest.json').write_text(json.dumps(dict(schema_version=2,
            canonical_language='en', translations=[dict(canonical='docs/home.md', language='ja',
                translation='translations/ja/docs/home.md', canonical_blob_sha=blob, surfaces=['reader'])])))
        build = root / 'build'
        assemble({'site': source}, source, build)
        loaded = load_manifest(source / 'site-manifest.json')
        catalog_documents, assets = load_catalog('site', source)
        records = publish_translations({'site': (source, catalog_documents, assets)},
            [d for d in loaded.documents if (build / 'docs' / d['destination']).is_file()], build / 'docs')
        self.assertEqual(len(records), 1)
        artifact = build / 'docs'
        extend_audience_routes(artifact, records)
        (artifact / 'reader-navigation-runtime.json').write_text(json.dumps(build_runtime_map({'ja': {}}, records)))
        # HTML is the only fixture layer: assembly and translation projection use real entrypoints.
        for markdown in artifact.rglob('*.md'):
            route = public_path(markdown.relative_to(artifact).as_posix())
            html = artifact / route.lstrip('/') / 'index.html'
            html.parent.mkdir(parents=True, exist_ok=True)
            html.write_text('<script src="/javascripts/audience-context.js"></script>')
        # The original provider catalog does not contain the assembly-generated document.
        catalog_path.write_text(json.dumps(dict(schema_version=3, documents=catalog[:-1])))
        return source, artifact

    def test_boundary_family_through_canonical_setup(self):
        for present in (False, True):
            with self.subTest(optional_present=present), tempfile.TemporaryDirectory() as directory:
                source, artifact = self.fixture(Path(directory), present)
                def check():
                    return check_artifact(artifact, {'site': source}, source / 'site-manifest.json')
                model = check()
                self.assertEqual(model['routes']['/ja/'], 'index.md')
                self.assertEqual('optional/index.md' in model['documents'], present)
                original = json.dumps(model)
                path = artifact / 'audience-runtime.json'
                mutations = [('required', 'index.md'), ('generated', 'generated/index.md')]
                if present:
                    mutations.append(('optional-present', 'optional/index.md'))
                for label, destination in mutations:
                    with self.subTest(omission=label):
                        changed = json.loads(original)
                        del changed['documents'][destination]
                        path.write_text(json.dumps(changed))
                        with self.assertRaisesRegex(AssertionError, 'missing required'):
                            check()
                for field, key, value in [('documents', 'alien.md', {}), ('routes', '/alien/', 'index.md')]:
                    with self.subTest(extra=field):
                        changed = json.loads(original)
                        changed[field][key] = value
                        path.write_text(json.dumps(changed))
                        with self.assertRaises(AssertionError):
                            check()
                path.write_text(original)
                alias = artifact / 'ja/index.html'
                alias.unlink()
                with self.assertRaisesRegex(AssertionError, 'translation alias has no published page'):
                    check()
