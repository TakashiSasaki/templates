"""Successful artifacts are selected independently of upstream branch advancement."""
import subprocess
from unittest.mock import patch
import unittest
from site_renderer.channel import eligible, pages, select, REPOSITORY
from publication_bundle.contract import BundleError


def run(identifier, **values):
    return dict(id=identifier, path='.github/workflows/integration-publish.yml',
                head_branch='integration', event='push', head_repository={'full_name':REPOSITORY},
                head_sha=str(identifier)*40, status='completed', conclusion='success',
                run_attempt=1, **values)


def artifact(value):
    return {'id':value['id']+100, 'name':'integrated-publication','expired':False,
            'workflow_run':{'id':value['id'],'head_sha':value['head_sha']},'digest':'sha256:'+'a'*64}


class ChannelTests(unittest.TestCase):
    def test_unregistered_workflow_does_not_hide_another_channel(self):
        missing = subprocess.CalledProcessError(1, ['gh'], stderr=b'gh: Not Found (HTTP 404)')
        with patch('site_renderer.channel.api', side_effect=missing):
            self.assertEqual(list(pages('actions/workflows/new.yml/runs', 'workflow_runs')), [])
            with self.assertRaises(subprocess.CalledProcessError):
                list(pages('actions/runs/123/artifacts', 'artifacts'))
        denied = subprocess.CalledProcessError(1, ['gh'], stderr=b'gh: Forbidden (HTTP 403)')
        with patch('site_renderer.channel.api', side_effect=denied), self.assertRaises(subprocess.CalledProcessError):
            list(pages('actions/workflows/new.yml/runs', 'workflow_runs'))

    def test_only_successful_canonical_publishing_workflows_are_eligible(self):
        self.assertTrue(eligible(run(1)))
        for key,value in [('conclusion','failure'),('status','in_progress'),('event','pull_request'),
                          ('head_branch','candidate'),('path','.github/workflows/build-pages.yml'),
                          ('head_repository',{'full_name':'fork/templates'})]:
            candidate=run(1);candidate[key]=value
            with self.subTest(key=key):self.assertFalse(eligible(candidate))
        candidate=run(2);candidate.update(path='.github/workflows/refresh-publication.yml',
                                       head_branch='site',event='schedule')
        self.assertTrue(eligible(candidate))

    def test_newest_available_success_survives_failed_and_expired_newer_runs(self):
        older,newer=run(1),run(2)
        def pages(path,key):
            if key=='workflow_runs':return [newer,older] if 'integration-publish' in path else []
            if '/2/' in path:return [{**artifact(newer),'expired':True}]
            return [artifact(older)]
        with patch('site_renderer.channel.pages',side_effect=pages):
            selected,_=select();self.assertEqual(selected['id'],1)
        # Selection never asks for provider/source branch heads or an adoption lock.

    def test_invalid_binding_and_duplicate_artifacts_fail(self):
        current=run(1);valid=artifact(current)
        variants=[[valid,valid],[{**valid,'digest':'missing'}],
                  [{**valid,'workflow_run':{'id':999,'head_sha':current['head_sha']}}]]
        for records in variants:
            with self.subTest(records=records),patch('site_renderer.channel.api',return_value=current), \
                 patch('site_renderer.channel.pages',return_value=records),self.assertRaises(BundleError):
                select(1)

    def test_explicit_failed_run_does_not_fall_back_to_an_unrequested_publication(self):
        current=run(1);current['conclusion']='failure'
        with patch('site_renderer.channel.api',return_value=current),self.assertRaises(BundleError):select(1)
