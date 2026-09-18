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
        self.maintainer_entrypoint={
            'repository':'TakashiSasaki/templates',
            'branch':'site',
            'path':'docs/maintainer-onboarding.md',
        }
        self.bundle={'schema_version':3,'identity':'a'*64,'content_digest':'b'*64,'producer':{'authority':'integration','revision':'c'*40},'providers':{'composition':'d'*40,'policy':'e'*40}}

    def v4_bundle(self):
        return {
            'schema_version':4,
            'identity':'a'*64,
            'content_digest':'b'*64,
            'producer':{'authority':'integration','revision':'c'*40},
            'providers':{'modeling':'f'*40,'composition':'d'*40,'policy':'e'*40},
        }
    def test_repository_and_public_projections_are_identical(self):
        self.assertFalse((ROOT/'assets/agent.json').exists())
        self.assertFalse((ROOT/'assets/schemas/agent-bootstrap.schema.json').exists())
        schema=json.loads((ROOT/'schemas/agent-bootstrap.schema.json').read_text())
        jsonschema.validate(self.template,schema)
        jsonschema.validate(project(self.template,self.bundle),schema)

    def test_maintainer_entrypoint_is_stable_and_survives_projection(self):
        schema=json.loads((ROOT/'schemas/agent-bootstrap.schema.json').read_text())
        self.assertEqual(self.template['maintainer_entrypoint'],self.maintainer_entrypoint)
        for bundle in (self.bundle,self.v4_bundle()):
            result=project(self.template,bundle)
            jsonschema.validate(result,schema)
            self.assertEqual(result['maintainer_entrypoint'],self.maintainer_entrypoint)

    def test_maintainer_entrypoint_is_required_by_schema(self):
        schema=json.loads((ROOT/'schemas/agent-bootstrap.schema.json').read_text())
        invalid=copy.deepcopy(self.template)
        del invalid['maintainer_entrypoint']
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(invalid,schema)
    def test_exact_provider_facts_come_only_from_bundle(self):
        result=project(self.template,self.bundle)
        self.assertEqual(result['integration_source'],self.bundle)
        for name,revision in self.bundle['providers'].items():
            self.assertNotIn('publication_revision',self.template['authorities'][name])
            self.assertEqual(result['authorities'][name]['publication_revision'],revision)
            self.assertIn(revision,result['authorities'][name]['canonical_repository_url'])
        self.assertNotIn('composition_bootstrap',result)
        self.assertNotIn('policy_bootstrap',result)

    def test_current_v4_bundle_projects_and_validates_without_downgrading(self):
        schema=json.loads((ROOT/'schemas/agent-bootstrap.schema.json').read_text())
        result=project(self.template,self.v4_bundle())
        jsonschema.validate(result,schema)
        self.assertEqual(result['integration_source']['schema_version'],4)
        self.assertEqual(result['authorities']['modeling']['publication_revision'],'f'*40)
        self.assertEqual(result['authorities']['integration']['contract'],'Integrated Publication Bundle v4')
    def test_site_asset_pipeline_places_discovery_contract_at_public_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(ROOT,Path(tmp),self.bundle)
            self.assertEqual(json.loads((Path(tmp)/'agent.json').read_text()),project(self.template,self.bundle))
    def test_invalid_authority_template_and_unknown_provider_fail(self):
        invalid=copy.deepcopy(self.template);del invalid['authorities']['integration']
        with self.assertRaises(BundleError):project(invalid,self.bundle)
        invalid=copy.deepcopy(self.bundle);invalid['providers']['unknown']='f'*40
        with self.assertRaises(BundleError):project(self.template,invalid)
