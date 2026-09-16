#!/usr/bin/env python3
"""Run the real renderer with Integration code and provider directories absent."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from publication_bundle.contract import validate


def qualify(site_root,bundle,identity,output):
    site_root=site_root.resolve();bundle=bundle.resolve();output=output.resolve()
    validate(bundle,expected_identity=identity)
    head=subprocess.check_output(['git','-C',str(site_root),'rev-parse','HEAD'],text=True).strip()
    if subprocess.check_output(['git','-C',str(site_root),'status','--porcelain','--untracked-files=no']):
        raise RuntimeError('isolation qualification requires a committed Site candidate')
    with tempfile.TemporaryDirectory(prefix='site-bundle-isolation-') as tmp:
        root=Path(tmp);source=root/'site-source';material=root/'bundle'
        subprocess.run(['git','-C',str(site_root),'worktree','add','--detach',str(source),head],check=True,capture_output=True)
        try:
            subprocess.run(['git','-C',str(source),'sparse-checkout','set','--no-cone','/*','!/integration/'],check=True,capture_output=True)
            shutil.copytree(bundle,material)
            assert not (source/'integration').exists()
            assert not (root/'composition-source').exists()
            assert not (root/'policy-source').exists()
            env=dict(os.environ)
            for key in ('PYTHONPATH','COMPOSITION_SOURCE_ROOT','POLICY_SOURCE_ROOT','SITE_PUBLICATION_ROOT'):
                env.pop(key,None)
            subprocess.run([sys.executable,str(source/'scripts/render_publication_bundle.py'),'--bundle',str(material),'--bundle-identity',identity,'--site-root',str(source),'--output',str(output)],cwd=root,env=env,check=True)
            if not (output/'site/index.html').is_file():raise RuntimeError('isolation renderer omitted Site')
            print(json.dumps({'isolation':'passed','site_revision':head,'bundle_identity':identity,'provider_checkouts_present':False,'integration_implementation_present':False}))
        finally:
            subprocess.run(['git','-C',str(site_root),'worktree','remove','--force',str(source)],check=True,capture_output=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--site-root',type=Path,required=True)
    p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--bundle-identity',required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();qualify(args.site_root,args.bundle,args.bundle_identity,args.output)
