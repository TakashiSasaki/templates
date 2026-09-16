"""Supply explicit current availability for legacy reader-presentation fixtures."""
import json
from pathlib import Path
import tempfile
from finalize_translation_reader import finalize as finalize_reader

def finalize(site, mapping, canonical, *args):
    # These tests exercise presentation with an already-qualified current model;
    # adversarial status/closure tests call finalize_reader directly.
    data=json.loads(Path(mapping).read_text())
    records=[{'publication':r.get('publication'),'language':r.get('language'),'canonical_destination':r.get('canonical_destination'),'status':'current'} for r in data.get('translations',[]) if isinstance(r,dict)]
    with tempfile.TemporaryDirectory() as tmp:
        p=Path(tmp)/'availability.json';p.write_text(json.dumps({'schema_version':1,'canonical_language':'en','surface':'reader','records':records}))
        return finalize_reader(site,mapping,canonical,*args,availability_paths=(p,))
