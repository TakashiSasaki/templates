"""Synthetic Publication Bundle wire fixture; no provider producer is executed."""
from pathlib import Path
from publication_bundle.contract import canonical,digest,inventory,MODELS
from publication_bundle.paths import audience_routes
PRODUCER={'authority':'integration','revision':'a'*40}
PROVIDERS={'composition':'b'*40,'policy':'c'*40}
def fixture(root):
    root.mkdir()
    models={name:{} for name in MODELS}
    models['documents.json']=[{'publication':'composition','document':'intro','source':'docs/index.md','destination':'intro.md','slot':False}]
    models['navigation.json']={'schema_version':1,'navigation':{'use':[{'publication':'composition','document':'intro','destination':'intro.md','title':'Intro'}]},'locale_labels':{'schema_version':1,'canonical_language':'en','locales':[{'language':'ja','labels':[{'id':'intro','canonical':'Intro','localized':'はじめに'},{'id':'use','canonical':'Use templates','localized':'利用'}]}]},'audience_runtime':{'schema_version':1,'audiences':['use'],'documents':{'intro.md':{'destination':'intro.md','key':'composition:intro','audiences':['use'],'primary':'use','is_landing':False,'title':'Intro'}},'routes':audience_routes(['intro.md']),'navigation':{'use':[{'title':'Intro','destination':'intro.md','href':'/intro/'}]},'overviews':{'use':'/intro/'},'landing_destination':'intro.md'}}
    models['guided-locales.json']={'schema_version':1,'canonical_graph_schema_version':1,'canonical_language':'en','locales':[]}
    models['reader-navigation-runtime.json']={'schema_version':1,'canonical_language':'en','locales':[{'language':'ja','labels':{'Intro':'はじめに','Use templates':'利用'},'routes':{}}]}
    models['guided-navigation.json']={'schema_version':1,'repository':'TakashiSasaki/templates','providers':[{'name':k,'revision':v,'root_index':'docs/index.md','indexes':[{'path':'docs/index.md','title':'Intro','sections':[],'depth':0,'object_id':'f'*40}],'edges':[],'diagnostics':{'index_count':1,'edge_count':0,'max_index_depth':0,'cycle_edges':[],'multiple_parent_indexes':[]}} for k,v in PROVIDERS.items()]}
    models['translation-availability.json']={'schema_version':1,'canonical_language':'en','surface':'reader','languages':[],'summary':{'current':0,'stale':0,'missing':0},'by_language':{},'records':[]}
    models['translation-publication.json']={'schema_version':1,'canonical_language':'en','translations':[]}
    models['glossary.json']={'schema_version':1,'repository':'TakashiSasaki/templates','terms':[]}
    models['provenance.json']={'schema_version':1,'producer':PRODUCER,'providers':PROVIDERS}
    for name,value in models.items():(root/name).write_bytes(canonical(value))
    (root/'publication').mkdir();(root/'publication/intro.md').write_text('# Intro\n')
    return root


def finish(root):
    files=inventory(root)
    data={'schema_version':3,'producer':PRODUCER,'providers':PROVIDERS,'configuration_digest':'d'*64,'files':files,'content_digest':digest(canonical(files))}
    data['identity']=digest(canonical(data));(root/'bundle.json').write_bytes(canonical(data));return data

def lock(manifest):
    return {'schema_version':1,'repository':'TakashiSasaki/templates','revision':manifest['producer']['revision'],'bundle_schema':3,'bundle_identity':manifest['identity'],'content_digest':manifest['content_digest']}
