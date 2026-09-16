#!/usr/bin/env python3
"""Qualify audience semantics in the assembled portal and its real navigation lifecycle."""
from __future__ import annotations
import argparse
import re
import functools
import json
import threading
import time
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.check_audience_artifact import (
    check_artifact, skipped_optional_destinations, validate_projection_parity,
)


def check(
    site_root: Path,
    publication_roots: dict[str, Path],
    channel: str | None = "chrome",
) -> dict:
    from playwright.sync_api import sync_playwright
    from scripts.check_search_history import _open_search

    model = check_artifact(site_root, publication_roots)
    documents = model['documents']
    provenance = json.loads((site_root / 'build-provenance.json').read_text())
    class Handler(SimpleHTTPRequestHandler):
        def log_message(self, *_): pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Handler, directory=str(site_root)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    results = []
    def state(page, audience):
        page.wait_for_function("a => document.documentElement.dataset.audience === a", arg=audience)
        if audience != "neutral":
            assert page.evaluate("sessionStorage.getItem('templates-audience-context')") == audience
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(**({"channel": channel} if channel else {}))
            for path, expected in [('/web/', 'use'), ('/policy/contributing/', 'maintain'),
                    ('/composition/architecture/composer-mvp/', 'use'), ('/policy/architecture/', 'maintain'),
                    ('/?audience=maintain', 'neutral'), ('/policy/architecture/?audience=admin', 'maintain'),
                    ('/web/?audience=maintain', 'use'), ('/policy/contributing/?audience=use', 'maintain'),
                    ('/policy/architecture/?audience=use', 'use')]:
                context = browser.new_context(service_workers="block")
                page = context.new_page()
                assert page.goto(base + path).status == 200
                state(page, expected)
                assert page.locator('link[rel="canonical"]').get_attribute('href').split('?')[0].endswith(urlsplit(path).path)
                results.append({'direct': path, 'audience': expected})
                context.close()
            context = browser.new_context(service_workers="block")
            page = context.new_page()
            requests = []
            page.on('request', lambda r: requests.append(r.url) if urlsplit(r.url).path == '/audience-runtime.json' else None)
            native_context = browser.new_context(service_workers="block")
            native_page = native_context.new_page()
            assert native_page.goto(base + '/?audience=maintain').status == 200
            state(native_page, 'neutral')
            native_primary_nav = native_page.locator('nav.md-nav--primary').first
            native_neutral_nav = {
                'html': native_primary_nav.evaluate('nav => nav.innerHTML'),
                'aria_label': native_primary_nav.get_attribute('aria-label'),
            }
            native_context.close()
            page.goto(base + '/composition/architecture/composer-mvp/')
            state(page, 'use')
            page.wait_for_function('!!window.document$')
            page.evaluate("window.audienceProbe = {events: []}; addEventListener('templates:audience-changed', e => audienceProbe.events.push(e.detail.audience))")
            def navigate(path, expected):
                page.evaluate("""path => {
                    const link = document.createElement('a'); link.href = path;
                    link.textContent = 'Audience qualification destination';
                    document.querySelector('main').append(link); link.click();
                }""", path)
                page.wait_for_url(base + path)
                state(page, expected)
                assert page.evaluate('!!window.audienceProbe'), 'navigation reloaded instead of using document$'
            navigate('/policy/contributing/', 'maintain')
            page.go_back(); page.wait_for_url(base + '/composition/architecture/composer-mvp/'); state(page, 'use')
            page.go_forward(); page.wait_for_url(base + '/policy/contributing/'); state(page, 'maintain')
            navigate('/web/', 'use')
            navigate('/policy/architecture/', 'use')
            navigate('/composition/architecture/composer-mvp/', 'use')
            # Switch uses an actual delegated control, preserves fragment and unrelated history state.
            fragment = page.locator('h1').first.get_attribute('id')
            page.evaluate("""fragment => {
                history.replaceState({...history.state, qualification: 42}, '', '#' + fragment);
                const button = document.createElement('button'); button.dataset.audienceSwitch = 'maintain';
                button.id = 'audience-probe-switch'; document.querySelector('main').append(button);
            }""", fragment)
            page.locator('#audience-probe-switch').evaluate('button => button.click()')
            state(page, 'maintain')
            assert urlsplit(page.url).fragment == fragment
            assert page.evaluate('history.state.qualification') == 42
            assert page.evaluate('!!window.audienceProbe')
            navigate('/policy/architecture/', 'maintain')
            # Re-evaluate script + initialization and actual document$ emissions.
            before = page.evaluate('audienceProbe.events.length')
            page.add_script_tag(content=(site_root/'javascripts/audience-context.js').read_text())
            page.evaluate("TemplatesAudienceContext.init(); TemplatesAudienceContext.init(); dispatchEvent(new Event('pageshow'))")
            page.wait_for_timeout(150)
            assert page.evaluate('audienceProbe.events.length') == before, 'duplicate state event after initialization'
            navigate('/web/', 'use')
            assert page.evaluate('audienceProbe.events.length') == before + 1, 'duplicate navigation listeners/events'
            assert len(requests) == 1, f'duplicate runtime fetches: {requests}'
            primary_nav = page.locator('nav.md-nav--primary').first
            assert primary_nav.get_attribute('aria-label') == 'Use templates'
            # Instant navigation to neutral restores the target page's exact native nav state.
            navigate('/?audience=maintain', 'neutral')
            assert primary_nav.evaluate('nav => nav.innerHTML') == native_neutral_nav['html']
            assert primary_nav.get_attribute('aria-label') == native_neutral_nav['aria_label']
            assert page.evaluate("sessionStorage.getItem('templates-audience-context')") == 'use'
            results.append({'instant_navigation': 'use/maintain/neutral, exact native nav restoration, shared journey, history, switch, fragment, repeated initialization passed'})
            context.close()

            # Localized neutral restoration must wait for reader-navigation async work in the
            # target runtime frame. Delay only the /ja/ frame's reader map so a premature
            # snapshot would cache canonical navigation and fail after an explicit re-render.
            native_context = browser.new_context(service_workers='block')
            native_page = native_context.new_page()
            assert native_page.goto(base + '/ja/?audience=maintain').status == 200
            state(native_page, 'neutral')
            native_page.wait_for_function("""() =>
                document.querySelector('nav.md-nav--primary')?.dataset.readerNavigationLanguage === 'ja'
            """)
            native_primary_nav = native_page.locator('nav.md-nav--primary').first
            native_ja_nav = {
                'html': native_primary_nav.evaluate('nav => nav.innerHTML'),
                'aria_label': native_primary_nav.get_attribute('aria-label'),
            }
            native_context.close()

            context = browser.new_context(service_workers='block')
            delayed_reader_requests = []
            def delay_reader_navigation(route):
                if urlsplit(route.request.frame.url).path == '/ja/':
                    delayed_reader_requests.append(route.request.frame.url)
                    time.sleep(0.4)
                route.continue_()
            context.route('**/reader-navigation-runtime.json', delay_reader_navigation)
            page = context.new_page()
            assert page.goto(base + '/web/').status == 200
            state(page, 'use')
            page.wait_for_function('!!window.document$')
            page.wait_for_function("!!document.querySelector('nav.md-nav--primary > .audience-navigation')")
            page.evaluate("""path => {
                const link = document.createElement('a'); link.href = path;
                link.textContent = 'Localized neutral qualification destination';
                document.querySelector('main').append(link); link.click();
            }""", '/ja/?audience=maintain')
            page.wait_for_url(base + '/ja/?audience=maintain')
            state(page, 'neutral')
            primary_nav = page.locator('nav.md-nav--primary').first
            page.wait_for_function("""() =>
                document.querySelector('nav.md-nav--primary')?.dataset.readerNavigationLanguage === 'ja'
            """)
            assert delayed_reader_requests, 'localized native-navigation snapshot did not exercise delayed reader map'
            assert primary_nav.evaluate('nav => nav.innerHTML') == native_ja_nav['html']
            assert primary_nav.get_attribute('aria-label') == native_ja_nav['aria_label']
            page.evaluate('() => TemplatesAudienceShell.render()')
            assert primary_nav.evaluate('nav => nav.innerHTML') == native_ja_nav['html']
            assert primary_nav.get_attribute('aria-label') == native_ja_nav['aria_label']
            results.append({'localized_neutral_navigation': 'delayed reader map -> localized native snapshot remains stable across shell re-render'})
            context.close()

            for path, target, overview in [('/web/', 'maintain', '/repository-trees/'),
                    ('/policy/contributing/', 'use', '/web/'), ('/', 'maintain', '/repository-trees/')]:
                context = browser.new_context(service_workers='block'); page = context.new_page()
                page.goto(base + path)
                state(page, 'neutral' if path == '/' else ('use' if path == '/web/' else 'maintain'))
                page.evaluate("target => TemplatesAudienceContext.switchAudience(target)", target)
                page.wait_for_url(base + overview); state(page, target)
                results.append({'switch_from': path, 'target': target, 'overview': overview})
                context.close()
            context = browser.new_context(service_workers='block')
            context.route('**/audience-runtime.json', lambda route: route.fulfill(
                json={'schema_version': 99, 'audiences': ['admin']}))
            page = context.new_page(); page.goto(base + '/policy/contributing/'); state(page, 'neutral')
            context.close(); results.append({'invalid_projection': 'neutral, no fabricated membership'})
            # Every actual translation alias retains the canonical membership model.
            translated = [(r,d) for r,d in model['routes'].items() if r.startswith('/ja/') and r.endswith('/')]
            assert translated, 'assembled audience map omitted published translation aliases'
            for r,d in translated:
                assert d in documents
            r,d = next((r,d) for r,d in translated if documents[d]['primary'] == 'maintain' and not documents[d]['is_landing'])
            context = browser.new_context(service_workers='block'); page=context.new_page()
            page.goto(base+r); state(page, documents[d]['primary']); context.close()
            results.append({'translation_aliases': len(translated), 'maintain_direct': r})
            # A filtered search owns keyboard/ARIA selection and the mounted result list;
            # returning to All must clear selection and release that same list to native semantics.
            context = browser.new_context(service_workers='block'); page=context.new_page()
            page.goto(base + '/composition/architecture/composer-mvp/?audience=maintain'); state(page, 'maintain')
            _open_search(page)
            search = page.locator('input[role="combobox"]').first
            select = page.locator('[data-audience-search-filter] select').first
            select.wait_for()
            search.fill('policy')
            page.wait_for_function("""() => {
                const root=[...document.body.children].map(h=>h.shadowRoot).find(r=>r?.querySelector('input[role=combobox]'));
                return !!root?.querySelector('ol a[href]:not([data-site-search-history] a)');
            }""")
            select.select_option('maintain')
            page.wait_for_function("""() => {
                const root=[...document.body.children].map(h=>h.shadowRoot).find(r=>r?.querySelector('input[role=combobox]'));
                const input=root?.querySelector('input[role=combobox]');
                const ids=(input?.getAttribute('aria-controls')||'').split(/\s+/).filter(Boolean);
                return ids.some(id => root.getElementById(id)?.getAttribute('role') === 'listbox');
            }""")
            result_list_id = page.evaluate("""() => {
                const root=[...document.body.children].map(h=>h.shadowRoot).find(r=>r?.querySelector('input[role=combobox]'));
                const input=root.querySelector('input[role=combobox]');
                return (input.getAttribute('aria-controls')||'').split(/\s+/).filter(Boolean)
                    .find(id => root.getElementById(id)?.getAttribute('role') === 'listbox') || null;
            }""")
            assert result_list_id, 'filtered search did not expose a controlled result list'
            def filtered_search_state():
                return page.evaluate("""() => {
                    const root=[...document.body.children].map(h=>h.shadowRoot).find(r=>r?.querySelector('input[role=combobox]'));
                    const input=root.querySelector('input[role=combobox]');
                    const anchors=[...root.querySelectorAll('ol a[href]')].filter(a=>!a.closest('[data-site-search-history]'));
                    const visible=anchors.filter(a=>!a.closest('[hidden], [data-audience-filtered]') && a.getClientRects().length);
                    return {
                        ids:[...root.querySelectorAll('[id]')].map(e=>e.id).filter(Boolean),
                        active:input.getAttribute('aria-activedescendant'),
                        all:anchors.map(a=>({id:a.id,href:a.href,role:a.getAttribute('role'),selected:a.getAttribute('aria-selected')})),
                        visible:visible.map(a=>({id:a.id,href:a.href,role:a.getAttribute('role'),selected:a.getAttribute('aria-selected')})),
                        styled:[...root.querySelectorAll('[data-audience-search-current]')].map(a=>a.id),
                    };
                }""")
            def assert_filtered_search(require_active=False):
                data = filtered_search_state()
                assert len(data['ids']) == len(set(data['ids'])), ('duplicate search DOM IDs', data)
                assert all(hit['id'] and hit['role'] == 'option' for hit in data['all']), ('filtered hit lost option semantics', data)
                if require_active:
                    assert data['active'] and data['active'] in [hit['id'] for hit in data['visible']], ('invalid active descendant', data)
                    assert sum(hit['selected'] == 'true' for hit in data['all']) == 1, ('active option selection is not unique', data)
                    assert next(hit for hit in data['visible'] if hit['id'] == data['active'])['selected'] == 'true', ('active option is not selected', data)
                    assert data['styled'] == [data['active']], ('active styling does not match active descendant', data)
                else:
                    assert not data['active'] and not data['styled'], ('stale filtered selection', data)
                return data
            cleared = assert_filtered_search()
            stable_ids = [hit['id'] for hit in cleared['all']]
            search.focus(); search.press('ArrowDown')
            assert_filtered_search(require_active=True)
            search.press('ArrowUp')
            assert_filtered_search(require_active=True)
            # The audience adapter must not own composing keys. Other native search listeners may
            # prevent their default action, so assert propagation and adapter-state/navigation
            # neutrality rather than a global defaultPrevented value.
            for key in ('ArrowDown', 'ArrowUp', 'Enter'):
                before = filtered_search_state(); url = page.url
                outcome = search.evaluate("""(input,key) => {
                    let bubbled=false;
                    const observe=()=>{bubbled=true;};
                    document.addEventListener('keydown',observe,{once:true});
                    const event=new KeyboardEvent('keydown',{key,bubbles:true,cancelable:true,composed:true,isComposing:true});
                    input.dispatchEvent(event);
                    document.removeEventListener('keydown',observe);
                    return {isComposing:event.isComposing,bubbled};
                }""", key)
                assert outcome == {'isComposing': True, 'bubbled': True}, (key, outcome)
                assert page.url == url
                after = filtered_search_state()
                assert after['active'] == before['active'] and after['styled'] == before['styled'], (key, before, after)
            active = filtered_search_state()['active']
            clicked = search.evaluate("""input => {
                const root=input.getRootNode();
                const hit=root.getElementById(input.getAttribute('aria-activedescendant'));
                let clicked=null;
                hit.addEventListener('click',event=>{event.preventDefault();clicked=hit.id;},{once:true});
                input.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true,composed:true}));
                return clicked;
            }""")
            assert clicked == active, ('Enter did not activate active descendant', active, clicked)
            select.select_option('use')
            use_state = assert_filtered_search()
            assert [hit['id'] for hit in use_state['all']] == stable_ids, ('result IDs changed across filter transition', stable_ids, use_state)
            select.select_option('maintain')
            maintain_state = assert_filtered_search()
            assert [hit['id'] for hit in maintain_state['all']] == stable_ids, ('result IDs changed after returning to filter', stable_ids, maintain_state)
            search.fill('zzzzs5nomatcheszzzz')
            page.wait_for_function("""id => {
                const root=[...document.body.children].map(h=>h.shadowRoot).find(r=>r?.querySelector('input[role=combobox]'));
                const input=root?.querySelector('input[role=combobox]');
                const list=root?.getElementById(id);
                const anchors=list ? [...list.querySelectorAll('a[href]')].filter(a=>!a.closest('[data-site-search-history]')) : [];
                const controls=(input?.getAttribute('aria-controls')||'').split(/\s+/).filter(Boolean);
                return !!list && anchors.length === 0 && list.getAttribute('role') === 'listbox' && controls.includes(id);
            }""", arg=result_list_id)
            select.select_option('all')
            page.wait_for_function("""id => {
                const root=[...document.body.children].map(h=>h.shadowRoot).find(r=>r?.querySelector('input[role=combobox]'));
                const input=root?.querySelector('input[role=combobox]');
                const list=root?.getElementById(id);
                return !!list && !list.hasAttribute('role') && !input.hasAttribute('aria-controls');
            }""", arg=result_list_id)
            results.append({'search_empty_result_lifecycle': 'filtered keyboard/IME/selection + stable IDs + retained listbox -> all native semantics'})
            context.close()
            # Offline reload uses the actual registered worker and precached projection/controller.
            context = browser.new_context(); page=context.new_page()
            page.goto(base+'/policy/contributing/'); state(page,'maintain')
            page.evaluate('navigator.serviceWorker.ready')
            page.wait_for_function('!!navigator.serviceWorker.controller')
            page.reload(); state(page,'maintain')
            page.wait_for_function("""async () => {
                const names=await caches.keys();
                for(const name of names) {
                    const cache=await caches.open(name);
                    if(await cache.match('/audience-runtime.json') && await cache.match('/javascripts/audience-context.js')) return true;
                } return false;
            }""")
            context.set_offline(True); page.reload(wait_until='domcontentloaded'); state(page,'maintain')
            results.append({'offline_reload': 'maintain page, controller and manifest projection available'})
            context.close(); browser.close()
    finally: server.shutdown(); server.server_close()
    return {'status':'passed', 'provenance':provenance, 'canonical_documents':len(documents), 'checks':results}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site-root',type=Path,default=Path('build/site'))
    parser.add_argument('--output',type=Path,default=Path('build/audience-runtime.json'))
    parser.add_argument('--channel',default='chrome',help='Browser channel; chromium uses Playwright bundled Chromium')
    parser.add_argument('--composition-root',type=Path,default=Path('../composition'))
    parser.add_argument('--policy-root',type=Path,default=Path('../policy'))
    args=parser.parse_args(); result=check(
        args.site_root,
        {"site": Path.cwd(), "composition": args.composition_root, "policy": args.policy_root},
        None if args.channel=='chromium' else args.channel,
    )
    args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()