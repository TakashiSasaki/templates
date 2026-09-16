#!/usr/bin/env python3
"""Exercise generated translation warnings through navigation and real PWA cache."""
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
import argparse
import json
import sys
import threading
import time
if __package__ in (None,''):sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from publication_bundle.paths import public_path
from site_renderer.bundle import load_lock,validate_locked


def run(site,bundle,output=None):
    lock=load_lock(Path(__file__).resolve().parents[1]/'integration-source.json')
    identity=validate_locked(bundle,lock)
    records=json.loads((bundle/'translation-availability.json').read_text())['records']
    stale=next(r for r in records if r['status']=='stale' and r['language']=='ja')
    current=next(r for r in records if r['status']=='current' and r['language']=='ja')
    missing=next(r for r in records if r['status']=='missing' and r['language']=='ja')
    stale_route=public_path('ja/'+stale['canonical_destination'])
    current_route=public_path('ja/'+current['canonical_destination'])
    missing_route=public_path('ja/'+missing['canonical_destination'])
    canonical_route=public_path(stale['canonical_destination'])
    assert not (site/missing_route.lstrip('/')/'index.html').exists(),'missing translation route fabricated'
    state={'worker':1,'delay':0}
    class Handler(SimpleHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            path=urlsplit(self.path).path
            if path==stale_route and state['delay']:time.sleep(state['delay'])
            if path=='/service-worker.js':
                body=(site/'service-worker.js').read_bytes()+f"\n// acceptance rollout {state['worker']}\n".encode()
                self.send_response(200);self.send_header('Content-Type','text/javascript');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body);return
            # Serve the same artifact under a loopback origin; only anchor origins
            # change so real language links remain inside the test deployment.
            relative=path.lstrip('/')+('index.html' if path.endswith('/') else '')
            candidate=(site/relative).resolve()
            if candidate.is_relative_to(site.resolve()) and candidate.is_file() and candidate.suffix=='.html':
                body=candidate.read_text().replace('href="https://templates.moukaeritai.work/','href="'+base+'/').encode()
                self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body);return
            super().do_GET()
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=str(site)))
    base=f'http://127.0.0.1:{server.server_port}'
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    from playwright.sync_api import sync_playwright
    evidence={'integration':identity['producer']['revision'],'bundle_identity':identity['identity'],'stale_route':stale_route,'current_route':current_route,'missing_route':missing_route,'checks':[]}
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True)
            context=browser.new_context(viewport={'width':390,'height':844})
            page=context.new_page()
            def warning(label):
                box=page.locator('.translation-stale-warning');box.wait_for(state='visible')
                assert box.count()==1 and box.get_attribute('role')=='note'
                assert box.get_attribute('aria-labelledby')=='translation-stale-title'
                assert '非正本' in box.inner_text() and '英語正本が変更' in box.inner_text()
                assert urlsplit(box.locator('a').get_attribute('href')).path==canonical_route
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'),'warning causes horizontal overflow'
                evidence['checks'].append(label)
            page.goto(base+stale_route,wait_until='networkidle');warning('online')
            page.wait_for_function('navigator.serviceWorker.controller !== null',timeout=30000)
            page.reload(wait_until='networkidle');warning('reload')
            page.locator('.translation-switcher a[hreflang="en"]').click();page.wait_for_url(base+canonical_route)
            assert page.locator('.translation-stale-warning').count()==0
            page.locator('.translation-switcher a[hreflang="ja"]').click();page.wait_for_url(base+stale_route);warning('language-switch')
            page.go_back();page.wait_for_url(base+canonical_route)
            page.go_forward();page.wait_for_url(base+stale_route);warning('back-forward')
            page.goto(base+current_route,wait_until='networkidle');assert page.locator('.translation-stale-warning').count()==0
            assert page.locator('.translation-switcher').count()==1;evidence['checks'].append('current-without-warning')
            page.goto(base+stale_route,wait_until='networkidle');warning('return-to-stale')
            page.wait_for_function("""async route => {const cache=await caches.open('templates-portal-documents-v1');return !!(await cache.match(new URL(route,location.origin).href));}""",arg=stale_route,timeout=30000)
            context.set_offline(True);page.reload(wait_until='domcontentloaded');warning('offline-cached-reload')
            context.set_offline(False)
            state['worker']=2
            page.evaluate("""async () => {const reg=await navigator.serviceWorker.ready; await new Promise(async resolve=>{navigator.serviceWorker.addEventListener('controllerchange',resolve,{once:true});await reg.update();});}""")
            page.reload(wait_until='networkidle');warning('worker-update')
            state['delay']=1.0;page.reload(wait_until='domcontentloaded');warning('slow-network-convergence')
            context.set_offline(True);page.reload(wait_until='domcontentloaded');warning('offline-after-worker-update')
            context.set_offline(False);browser.close()
    finally:
        server.shutdown();server.server_close();thread.join(timeout=5)
    if output:output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(evidence,indent=2)+'\n')
    return evidence

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--site-root',type=Path,required=True);p.add_argument('--bundle',type=Path,required=True);p.add_argument('--output',type=Path)
    a=p.parse_args();print(json.dumps(run(a.site_root.resolve(),a.bundle.resolve(),a.output)))
