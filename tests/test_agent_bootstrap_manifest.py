"""Machine discovery must be a projection of the selected immutable Bundle."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
import jsonschema
from site_renderer.discovery import project,write
from publication_bundle.contract import BundleError
ROOT=Path(__file__).resolve().parents[1]

class AgentBootstrapManifestTests(unittest.TestCase):
    def setUp(self):
        self.template=json.loads((ROOT/'agent.json').read_text())
        self.bundle={'schema_version':2,'identity':'a'*64,'content_digest':'b'*64,'producer':{'authority':'integration','revision':'c'*40},'providers':{'composition':'d'*40,'policy':'e'*40}}
    def test_repository_and_public_projections_are_identical(self):
        self.assertFalse((ROOT/'assets/agent.json').exists())
        self.assertFalse((ROOT/'assets/schemas/agent-bootstrap.schema.json').exists())
        schema=json.loads((ROOT/'schemas/agent-bootstrap.schema.json').read_text())
        jsonschema.validate(self.template,schema)
        jsonschema.validate(project(self.template,self.bundle),schema)
    def test_exact_provider_facts_come_only_from_bundle(self):
        result=project(self.template,self.bundle)
        self.assertEqual(result['integration_source'],self.bundle)
        for name,revision in self.bundle['providers'].items():
            self.assertNotIn('publication_revision',self.template['authorities'][name])
            self.assertEqual(result['authorities'][name]['publication_revision'],revision)
            self.assertIn(revision,result['authorities'][name]['canonical_repository_url'])
        self.assertNotIn('composition_bootstrap',result)
        self.assertNotIn('policy_bootstrap',result)
    def test_site_asset_pipeline_places_discovery_contract_at_public_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(ROOT,Path(tmp),self.bundle)
            self.assertEqual(json.loads((Path(tmp)/'agent.json').read_text()),project(self.template,self.bundle))
    def test_invalid_authority_template_and_unknown_provider_fail(self):
        invalid=copy.deepcopy(self.template);del invalid['authorities']['integration']
        with self.assertRaises(BundleError):project(invalid,self.bundle)
        invalid=copy.deepcopy(self.bundle);invalid['providers']['unknown']='f'*40
        with self.assertRaises(BundleError):project(self.template,invalid)
