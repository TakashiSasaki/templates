"""The historical ownership inventory is complete even in shallow CI checkouts.

The fixture is an immutable Git tree proof, exported from audited_site. Rebuilding
its tree and commit identities binds the expected paths without a network fetch.
"""
import copy
import hashlib
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]


def git_hash(kind,raw):
    return hashlib.sha1(kind.encode()+b' '+str(len(raw)).encode()+b'\0'+raw).hexdigest()


def audited_paths(proof,revision):
    commit=proof['commit_object'].encode()
    if git_hash('commit',commit)!=revision:raise ValueError('audited commit mismatch')
    tree={};paths=[]
    for entry in proof['entries']:
        path=entry['path'];parts=path.split('/');node=tree
        if any(p in ('','.','..') or '\0' in p for p in parts):raise ValueError('unsafe proof path')
        for p in parts[:-1]:node=node.setdefault(p,{})
        if parts[-1] in node:raise ValueError('duplicate proof path')
        node[parts[-1]]=(entry['mode'],entry['object']);paths.append(path)
    def identity(node):
        raw=b''
        for name,value in sorted(node.items(),key=lambda item:(item[0]+('/' if isinstance(item[1],dict) else '')).encode()):
            mode,oid=('40000',identity(value)) if isinstance(value,dict) else value
            raw+=mode.encode()+b' '+name.encode()+b'\0'+bytes.fromhex(oid)
        return git_hash('tree',raw)
    if commit.splitlines()[0]!=b'tree '+identity(tree).encode():raise ValueError('audited tree mismatch')
    return set(paths)


def validate_inventory(inventory,proof):
    expected=audited_paths(proof,inventory['audited_site'])
    records=inventory['paths'];paths=[r['path'] for r in records]
    if len(paths)!=len(set(paths)):raise ValueError('duplicate ownership path')
    if set(paths)!=expected:raise ValueError('missing or extra ownership path')
    if any(not isinstance(r['intended_owner'],str) or not r['intended_owner'].strip() for r in records):raise ValueError('missing owner')
    lock=proof['composition_lock_object'].encode()
    entry=next(e for e in proof['entries'] if e['path']=='.template-composition/lock.json')
    if git_hash('blob',lock)!=entry['object']:raise ValueError('audited Composition lock mismatch')
    owners={r['path']:r['intended_owner'] for r in records}
    for managed in json.loads(lock)['files']:
        if managed['ownership']=='managed' and owners.get(managed['destination'])!='Composition-owned managed semantics / Site consumer projection':
            raise ValueError('managed destination lost Composition ownership')


class OwnershipInventoryTests(unittest.TestCase):
    def setUp(self):
        self.inventory=json.loads((ROOT/'migration/ownership.json').read_text())
        self.proof=json.loads((ROOT/'migration/audited-tree.json').read_text())

    def test_exact_audited_tree_is_completely_classified(self):
        validate_inventory(self.inventory,self.proof)

    def test_missing_extra_duplicate_and_changed_revision_fail(self):
        for mutation in ('missing','extra','duplicate','revision','owner','managed-owner'):
            with self.subTest(mutation=mutation):
                data=copy.deepcopy(self.inventory)
                if mutation=='missing':data['paths'].pop()
                elif mutation=='extra':data['paths'].append({'path':'invented','intended_owner':'site'})
                elif mutation=='duplicate':data['paths'].append(data['paths'][0])
                elif mutation=='owner':data['paths'][0]['intended_owner']=''
                elif mutation=='managed-owner':next(r for r in data['paths'] if r['path']=='schemas/routes.schema.json')['intended_owner']='future Site presentation/runtime-owned'
                else:data['audited_site']='0'*40
                with self.assertRaises(ValueError):validate_inventory(data,self.proof)

    def test_forged_tree_proof_fails(self):
        for mutation in ('missing','extra','identity'):
            with self.subTest(mutation=mutation):
                proof=copy.deepcopy(self.proof)
                if mutation=='missing':proof['entries'].pop()
                elif mutation=='extra':proof['entries'].append({'path':'invented','mode':'100644','object':'0'*40})
                else:proof['entries'][0]['object']='0'*40
                with self.assertRaises(ValueError):validate_inventory(self.inventory,proof)

    def test_managed_relation_cannot_be_forged(self):
        proof=copy.deepcopy(self.proof)
        proof['composition_lock_object']=proof['composition_lock_object'].replace('"ownership": "managed"','"ownership": "scaffold"')
        with self.assertRaisesRegex(ValueError,'Composition lock mismatch'):validate_inventory(self.inventory,proof)
