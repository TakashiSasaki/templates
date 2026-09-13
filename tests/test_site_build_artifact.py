"""Exercise immutable identity, producer binding and real archive trust boundary."""
from copy import deepcopy
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import yaml
from scripts import site_build_artifact as artifact


def inputs(**overrides):
    values = dict(repository='TakashiSasaki/templates', site='a'*40,
                  composition='b'*40, policy='c'*40, workflow=b'workflow', runtime='python|runner')
    values.update(overrides)
    return artifact.identity(**values)


def bundle(root, expected, *, extra=None, provenance=None, manifest=None):
    files = {'index.html': b'<html>Site</html>',
             artifact.MANIFEST: json.dumps(manifest if manifest is not None else {'inputs': expected, 'identity': artifact.identity_key(expected)}).encode(),
             'build-provenance.json': json.dumps(provenance if provenance is not None else dict(
                 schema_version=2, repository=expected['repository'], site_commit=expected['site'],
                 publication_commits={'composition': expected['composition'], 'policy': expected['policy']})).encode()}
    with tarfile.open(root / 'artifact.tar', 'w') as tar:
        for name, data in files.items():
            member = tarfile.TarInfo('./' + name)
            member.size = len(data)
            tar.addfile(member, io.BytesIO(data))
        if extra:
            tar.addfile(extra, io.BytesIO(b''))
    archive = root / 'pages.zip'
    with zipfile.ZipFile(archive, 'w') as zip_file:
        zip_file.write(root / 'artifact.tar', 'artifact.tar')
    return archive, 'sha256:' + artifact.digest(archive.read_bytes())


def producer():
    run = dict(id=42, path=artifact.WORKFLOW, head_sha='a'*40, event='pull_request',
               head_repository={'full_name': 'TakashiSasaki/templates'}, pull_requests=[{'number': 1}],
               run_number=10, run_attempt=2, status='in_progress')
    job = dict(name='build', status='completed', conclusion='success',
               started_at='2026-09-13T12:00:00Z', completed_at='2026-09-13T12:03:00Z')
    file = dict(id=12, name='github-pages', expired=False, digest='sha256:'+'d'*64,
                workflow_run=dict(id=42, head_sha='a'*40), created_at='2026-09-13T12:02:59Z')
    return run, job, file


class BuildIdentityTests(unittest.TestCase):
    def test_every_material_input_changes_identity(self):
        original = inputs()
        for key, value in dict(site='d'*40, composition='d'*40, policy='d'*40,
                               repository='other/templates', workflow=b'changed', staging='candidate', staging_ids='one,two',
                               deployment_timestamp='timestamp', public_url='https://example.com/', runtime='new runner').items():
            with self.subTest(key=key):
                self.assertNotEqual(artifact.identity_key(original), artifact.identity_key(inputs(**{key: value})))
        self.assertEqual(artifact.identity_key(original), artifact.identity_key(dict(reversed(list(original.items())))))

    def test_mutable_revision_rejected(self):
        for name in ['site', 'composition', 'policy']:
            with self.assertRaises(artifact.ArtifactError):
                inputs(**{name: 'site'})

    def test_freshness_equivalence_and_provider_mismatch(self):
        expected = inputs()
        locked = dict(composition='b'*40, policy='c'*40)
        self.assertTrue(artifact.reuse_applicable(expected, locked, requested=True, event='pull_request'))
        for key, value in [('composition','d'*40), ('policy','d'*40), ('staging','candidate'), ('staging_ids','one,two'), ('deployment_timestamp','now')]:
            with self.subTest(key=key):
                self.assertFalse(artifact.reuse_applicable(inputs(**{key: value}), locked, requested=True, event='pull_request'))
        self.assertFalse(artifact.reuse_applicable(expected, locked, requested=True, event='schedule'))
        self.assertFalse(artifact.reuse_applicable(expected, locked, requested=False, event='pull_request'))


class ArtifactArchiveTests(unittest.TestCase):
    def test_exact_archive_validates_and_extracts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive, checksum = bundle(root, inputs())
            artifact.validate_and_extract(archive, inputs(), checksum, root/'site')
            self.assertEqual((root/'site/index.html').read_text(), '<html>Site</html>')

    def test_mismatched_inputs_and_provenance_never_extract(self):
        for change in [{'manifest': {}}, {'provenance': {}}, {}]:
            with self.subTest(change=change), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                archive, checksum = bundle(root, inputs(), **change)
                expected = inputs(site='e'*40) if not change else inputs()
                with self.assertRaises(artifact.ArtifactError):
                    artifact.validate_and_extract(archive, expected, checksum, root/'site')
                self.assertFalse((root/'site').exists())

    def test_archive_digest_and_existing_destination_are_not_bypassed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            archive, checksum=bundle(root, inputs())
            with self.assertRaisesRegex(artifact.ArtifactError, 'digest'):
                artifact.validate_and_extract(archive, inputs(), 'sha256:'+'0'*64, root/'site')
            (root/'site').mkdir()
            (root/'site/owned').write_text('preserve')
            with self.assertRaisesRegex(artifact.ArtifactError, 'already exists'):
                artifact.validate_and_extract(archive, inputs(), checksum, root/'site')
            self.assertEqual((root/'site/owned').read_text(), 'preserve')

    def test_paths_links_duplicates_and_special_files_rejected_before_extraction(self):
        cases = [('../outside',tarfile.REGTYPE), ('/absolute',tarfile.REGTYPE),
                 ('link',tarfile.SYMTYPE), ('hardlink',tarfile.LNKTYPE),
                 ('pipe',tarfile.FIFOTYPE), ('index.html',tarfile.REGTYPE)]
        for name, kind in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary)
                extra=tarfile.TarInfo(name); extra.type=kind; extra.linkname='../outside'
                archive, checksum=bundle(root, inputs(), extra=extra)
                with self.assertRaises(artifact.ArtifactError):
                    artifact.validate_and_extract(archive, inputs(), checksum, root/'site')
                self.assertFalse((root/'site').exists())


class ProducerBindingTests(unittest.TestCase):
    def test_only_canonical_same_pr_repository_head_run_is_selected(self):
        run, _, _ = producer()
        kwargs=dict(repository='TakashiSasaki/templates', head='a'*40, pr=1, current_run=99)
        self.assertEqual(artifact.select_run([run], **kwargs), run)
        for field, value in [('id',99), ('path','other.yml'), ('head_sha','e'*40),
                             ('event','push'), ('head_repository',{'full_name':'other/templates'}),
                             ('pull_requests',[{'number':2}])]:
            bad=dict(run, **{field:value})
            with self.subTest(field=field):
                self.assertIsNone(artifact.select_run([bad], **kwargs))

    def test_successful_build_can_supply_artifact_before_browser_completion(self):
        run, job, file=producer()
        self.assertEqual(artifact.qualified_artifact(run, [job], [file], inputs()), file)
        self.assertIsNone(artifact.qualified_artifact(run, [dict(job,status='in_progress')], [], inputs()))

    def test_failure_skip_stale_attempt_expiry_and_missing_digest_fail_closed(self):
        run, job, file=producer()
        for conclusion in ['failure','cancelled','skipped']:
            with self.assertRaises(artifact.ArtifactError):
                artifact.qualified_artifact(run,[dict(job,conclusion=conclusion)],[file],inputs())
        for update in [dict(expired=True), dict(digest=''), dict(created_at='2026-09-13T11:00:00Z'),
                       dict(workflow_run=dict(id=43,head_sha='a'*40)),
                       dict(workflow_run=dict(id=42,head_sha='e'*40))]:
            with self.subTest(update=update), self.assertRaises(artifact.ArtifactError):
                artifact.qualified_artifact(run,[job],[dict(file,**update)],inputs())
        for files in [[], [file,file]]:
            with self.assertRaises(artifact.ArtifactError):
                artifact.qualified_artifact(run,[job],files,inputs())

    @patch.object(artifact, 'list_all', return_value=[])
    def test_discovery_timeout_cannot_silently_rebuild(self, _):
        with self.assertRaisesRegex(artifact.ArtifactError, 'timed out'):
            artifact.reuse(inputs(), Path('/unused'),pr=1,current_run=99,timeout=0)


class ReuseWorkflowTests(unittest.TestCase):
    def test_reuse_skips_all_producer_steps_and_preserves_local_artifact_contract(self):
        root=Path(__file__).resolve().parents[1]
        workflow=yaml.safe_load((root/artifact.WORKFLOW).read_text())
        steps=workflow['jobs']['build']['steps']
        reuse_step=next(s for s in steps if s.get('id') == 'artifact')
        self.assertIn('github.event.pull_request.head.repo.full_name == github.repository', reuse_step['env']['REUSE_PR_BUILD'])
        start=next(i for i,s in enumerate(steps) if s.get('name')=='Install pinned site dependencies')
        end=next(i for i,s in enumerate(steps) if s.get('name')=='Upload Pages artifact')
        for step in steps[start:end]:
            self.assertIn("steps.artifact.outputs.reused != 'true'",step['if'],step['name'])
        self.assertNotIn('if', steps[end])
        for name in ['reference-consumer.yml','site-composition-playground-cross-authority.yml',
                     'site-composition-materialization-cross-authority.yml','check-publication-freshness.yml']:
            text=(root/'.github/workflows'/name).read_text()
            self.assertIn('reuse_pr_build: true', text)
        self.assertNotIn('reuse_pr_build: true', (root/'.github/workflows/deploy-pages.yml').read_text())

class CanonicalProducerReuseTests(unittest.TestCase):
    @patch.object(artifact, 'list_all', return_value=[])
    def test_first_canonical_run_builds_without_waiting_for_itself(self, _):
        self.assertEqual(artifact.reuse(inputs(), Path('/unused'), pr=1, current_run=99, wait=False), {})

    @patch.object(artifact, 'list_all')
    def test_prior_docs_skip_does_not_block_escalated_producer(self, listing):
        run, job, _ = producer()
        listing.side_effect = [[run], [dict(job, conclusion='skipped')]]
        self.assertEqual(artifact.reuse(inputs(), Path('/unused'), pr=1, current_run=99, wait=False), {})

class ChangedRecipeTests(unittest.TestCase):
    def test_valid_prior_recipe_is_distinct_from_corrupt_manifest(self):
        prior=inputs(workflow=b'prior workflow')
        with self.assertRaises(artifact.InputMismatch):
            artifact.validate_manifest({'inputs': prior, 'identity': artifact.identity_key(prior)}, inputs())
        with self.assertRaises(artifact.ArtifactError) as raised:
            artifact.validate_manifest({'inputs': prior, 'identity': artifact.identity_key(inputs())}, inputs())
        self.assertNotIsInstance(raised.exception, artifact.InputMismatch)
