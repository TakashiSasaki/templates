"""Prove rendering binds immutable inputs and a safe publication destination."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from publication_bundle.contract import BundleError, validate
from site_renderer.render import render, require_clean_site, publish_build
from tests.test_publication_bundle import fixture, finish


class RendererInputTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.site=self.root/'source';self.site.mkdir()
        self.git('init','-q');self.git('config','user.name','Fixture');self.git('config','user.email','fixture@example.invalid')
        (self.site/'input').write_text('committed');self.git('add','input');self.git('commit','-qm','fixture')
        self.revision=self.git('rev-parse','HEAD').strip()
        self.bundle=fixture(self.root/'bundle');self.identity=finish(self.bundle)['identity']
        self.output=self.root/'parent'/'output';self.output.parent.mkdir()

    def git(self,*args):return subprocess.check_output(['git','-C',str(self.site),*args],text=True)
    def render(self):return render(bundle=self.bundle,site_root=self.site,output=self.output,expected_identity=self.identity)
    def stamp(self):
        stat=self.output.parent.stat();return stat.st_dev,stat.st_ino

    def test_alias_into_either_input_is_rejected_before_writes(self):
        for source in (self.site,self.bundle):
            with self.subTest(source=source):
                alias=self.root/'alias';alias.symlink_to(source,target_is_directory=True)
                self.output=alias/'nested'/'output'
                with self.assertRaisesRegex(BundleError,'symlink'):self.render()
                self.assertFalse((source/'nested').exists());alias.unlink()

    def test_renderer_reads_only_the_validated_private_bundle_snapshot(self):
        def consume(**args):
            (self.bundle/'publication/intro.md').write_text('changed after snapshot')
            self.assertNotEqual(args['bundle'],self.bundle)
            self.assertEqual(validate(args['bundle'])['identity'],self.identity)
            self.assertEqual((args['bundle']/'publication/intro.md').read_text(),'# Intro\n')
            return 'snapshot used'
        with patch('site_renderer.render.consume_snapshot',side_effect=consume):self.assertEqual(self.render(),'snapshot used')

    def test_copy_time_mutation_is_rejected_by_snapshot_validation(self):
        def tamper(root,**kwargs):
            result=validate(root,**kwargs)
            (self.bundle/'publication/intro.md').write_text('changed after validation')
            return result
        with patch('site_renderer.render.validate',side_effect=tamper),self.assertRaisesRegex(BundleError,'changed during snapshot'):self.render()
        self.assertFalse(self.output.exists())

    def test_site_transient_edits_cannot_change_private_source_bytes(self):
        def consume(**args):
            (self.site/'input').write_text('transient uncommitted bytes')
            self.assertNotEqual(args['site_root'],self.site)
            self.assertEqual((args['site_root']/'input').read_text(),'committed')
            self.assertEqual(require_clean_site(args['site_root']),self.revision)
            (self.site/'input').write_text('committed')
            self.assertEqual((args['site_root']/'input').read_text(),'committed')
            return 'immutable source used'
        with patch('site_renderer.render.consume_snapshot',side_effect=consume):self.assertEqual(self.render(),'immutable source used')

    def test_atomic_publish_preserves_concurrent_empty_directory(self):
        from site_renderer.render import rename_noreplace
        build=self.root/'build';build.mkdir();(build/'result').write_text('artifact')
        def competing(directory,source,target):
            self.output.mkdir()
            return rename_noreplace(directory,source,target)
        with patch('site_renderer.render.rename_noreplace',side_effect=competing),self.assertRaisesRegex(BundleError,'concurrently created'):
            publish_build(build,self.output,self.stamp(),(self.bundle,self.site),self.revision)
        self.assertTrue(self.output.is_dir());self.assertEqual(list(self.output.iterdir()),[])
        self.assertEqual(list(self.output.parent.iterdir()),[self.output])

    def test_dirty_and_untracked_inputs_are_rejected_before_rendering(self):
        for path in ('input','untracked'):
            with self.subTest(path=path):
                p=self.site/path;p.write_text('not committed')
                with self.assertRaisesRegex(BundleError,'clean committed'):self.render()
                if path=='input':p.write_text('committed')
                else:p.unlink()

    def test_publication_rechecks_site_and_parent_and_preserves_existing_output(self):
        build=self.root/'build';build.mkdir();(build/'result').write_text('artifact')
        stamp=self.stamp();sources=(self.bundle,self.site)
        self.output.parent.rename(self.root/'old-parent');self.output.parent.mkdir()
        with self.assertRaisesRegex(BundleError,'parent changed'):publish_build(build,self.output,stamp,sources,self.revision)
        stamp=self.stamp();copy=shutil.copytree
        def dirty(source,target,**kwargs):
            result=copy(source,target,**kwargs);(self.site/'input').write_text('changed during staging');return result
        with patch('site_renderer.render.shutil.copytree',side_effect=dirty),self.assertRaisesRegex(BundleError,'clean committed'):publish_build(build,self.output,stamp,sources,self.revision)
        self.assertFalse(self.output.exists());self.assertEqual(list(self.output.parent.iterdir()),[])
        (self.site/'input').write_text('committed')
        publish_build(build,self.output,stamp,sources,self.revision)
        self.assertEqual((self.output/'result').read_text(),'artifact')
        with self.assertRaisesRegex(BundleError,'existing'):publish_build(build,self.output,stamp,sources,self.revision)

    def test_head_movement_invalidates_site_identity(self):
        self.git('commit','--allow-empty','-qm','moved')
        with self.assertRaisesRegex(BundleError,'revision changed'):require_clean_site(self.site,self.revision)

    def test_missing_output_parent_cannot_be_rebound_into_inputs(self):
        from site_renderer.render import snapshot_bundle
        for source in (self.bundle,self.site):
            with self.subTest(source=source):
                ancestor=self.root/'missing'
                self.output=ancestor/'nested'/'output'
                def inject(*args,**kwargs):
                    result=snapshot_bundle(*args,**kwargs)
                    ancestor.symlink_to(source,target_is_directory=True)
                    return result
                with patch('site_renderer.render.snapshot_bundle',side_effect=inject),self.assertRaisesRegex(BundleError,'unsafe render output parent'):
                    self.render()
                self.assertFalse((source/'nested').exists())
                self.assertTrue(ancestor.is_symlink());ancestor.unlink()

    def test_missing_output_parents_are_created_without_aliases(self):
        from site_renderer.render import prepare_output_parent
        self.output=self.root/'missing'/'nested'/'output'
        identity=prepare_output_parent(self.output,(self.bundle,self.site))
        stat=self.output.parent.stat()
        self.assertEqual(identity,(stat.st_dev,stat.st_ino))
        self.assertFalse(self.output.exists())
