#!/usr/bin/env python3
"""Check that Bundle-declared reader surfaces survived static rendering."""
import argparse
import json
from pathlib import Path
import sys
if __package__ in (None, ''):sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from site_renderer.bundle import load_lock,validate_locked
from site_renderer.guided import project_immutable_source_links
from publication_bundle.paths import public_path


def check(site,bundle,lock):
    manifest=validate_locked(bundle,lock)
    graph=project_immutable_source_links(json.loads((bundle/'guided-navigation.json').read_text()))
    if json.loads((site/'guided/graph.json').read_text())!=graph:raise ValueError('guided graph projection drift')
    if json.loads((site/'glossary/index.json').read_text())!=json.loads((bundle/'glossary.json').read_text()):raise ValueError('glossary projection drift')
    translations=json.loads((bundle/'translation-publication.json').read_text())['translations']
    for record in translations:
        route=public_path(record['translation_destination'])
        if not (site/route.lstrip('/')/'index.html').is_file():raise ValueError('missing declared translation route: '+route)
    for forbidden in ('ja/guided/graph.json',):
        if (site/forbidden).exists():raise ValueError('localized semantic graph must not be fabricated')
    expected={'schema_version':3,'repository':lock['repository'],'site_commit':json.loads((site/'build-provenance.json').read_text())['site_commit'],'integration':{k:manifest[k] for k in ('schema_version','identity','content_digest','producer','providers')}}
    if json.loads((site/'build-provenance.json').read_text())!=expected:raise ValueError('build provenance differs from selected Bundle')
    return {'providers':len(manifest['providers']),'translations':len(translations)}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--site-root',type=Path,required=True);p.add_argument('--bundle',type=Path,required=True)
    a=p.parse_args();print(json.dumps(check(a.site_root,a.bundle,load_lock(Path(__file__).resolve().parents[1]/'integration-source.json'))))
