"""Exercise the shipped search adapter in the actual assembled search DOM."""
from urllib.parse import urlsplit

ROOT = "[...document.body.children].map(h => h.shadowRoot).find(r => r?.querySelector('input[role=combobox]'))"
SNAPSHOT = """() => {
 const root=ROOT;
 const input=root.querySelector('input[role=combobox]');
 const filter=root.querySelector('[data-audience-search-filter] select')?.value || 'all';
 const anchors=[...root.querySelectorAll('ol a[href]')].filter(a=>!a.closest('[data-site-search-history]'));
 const visible=anchors.filter(a=>!a.closest('[hidden], [data-audience-filtered]') && a.getClientRects().length);
 const lists=[...root.querySelectorAll('ol')].filter(list=>!list.closest('[data-site-search-history]'));
 const ids=[...root.querySelectorAll('[id]')].map(e=>e.id).filter(Boolean);
 const active=input.getAttribute('aria-activedescendant');
 const matches=active ? [...root.querySelectorAll('[id]')].filter(e=>e.id===active) : [];
 const controls=(input.getAttribute('aria-controls')||'').split(/\s+/).filter(Boolean);
 const controlled=controls.map(id=>root.getElementById(id));
 return {filter,ids,active,matches:matches.length,activeVisible:matches.length===1 && visible.includes(matches[0]),controls,
   lists:lists.map(list=>({id:list.id,role:list.getAttribute('role')})),
   controlled:controlled.map(e=>e&&({id:e.id,role:e.getAttribute('role'),containsActive:!!(active&&e.querySelector('#'+CSS.escape(active)))})),
   all:anchors.map(a=>({id:a.id,href:a.href,role:a.getAttribute('role'),selected:a.getAttribute('aria-selected')})),
   visible:visible.map(a=>({id:a.id,href:a.href,role:a.getAttribute('role'),selected:a.getAttribute('aria-selected')})),
   styled:[...root.querySelectorAll('[data-audience-search-current]')].map(a=>({id:a.id,visible:visible.includes(a)}))};
}""".replace('ROOT', ROOT)


def check_search_identity(page, base):
    from scripts.check_search_history import _open_search

    records = []

    def snapshot():
        data = page.evaluate(SNAPSHOT)
        assert len(data['ids']) == len(set(data['ids'])), ('duplicate search DOM IDs', data)
        visible_ids = [hit['id'] for hit in data['visible'] if hit['id']]
        assert len(visible_ids) == len(set(visible_ids)), ('duplicate visible result IDs', data)
        if data['filter'] == 'all':
            assert not data['controls'], ('adapter aria-controls leaked into all-audience search', data)
            assert not any(hit['role'] == 'option' for hit in data['all']), ('all-audience result lost native link semantics', data)
            assert not any(hit['selected'] is not None for hit in data['all']), ('adapter selection leaked into all-audience results', data)
            assert not any(item['role'] == 'listbox' for item in data['lists']), ('adapter listbox leaked into all-audience search', data)
        elif data['all']:
            assert data['controls'], ('search results are not controlled by the combobox', data)
            assert all(item and item['role'] == 'listbox' for item in data['controlled']), ('controlled popup is not a listbox', data)
            assert all(hit['role'] == 'option' for hit in data['all']), ('search hit is not exposed as an option', data)
        if data['filter'] != 'all' and data['active']:
            assert data['matches'] == 1 and data['activeVisible'], ('invalid active descendant', data)
            assert any(item and item['containsActive'] for item in data['controlled']), ('active descendant is outside aria-controls popup', data)
            assert sum(hit['selected'] == 'true' for hit in data['all']) == 1, ('active option selection is not unique', data)
            assert next(hit for hit in data['visible'] if hit['id'] == data['active'])['selected'] == 'true', ('active option is not aria-selected', data)
        elif data['filter'] != 'all':
            assert not any(hit['selected'] == 'true' for hit in data['all']), ('aria-selected remained after selection cleared', data)
        assert all(item['visible'] and item['id'] == data['active'] for item in data['styled']), ('stale selection style', data)
        return data

    def cleared():
        data = snapshot()
        assert not data['active'] and not data['styled'], data
        return data

    def settled():
        page.wait_for_function("() => {const root=" + ROOT + ";return root?.querySelector('[data-search-audiences]')}")

    def move(key, index):
        search.focus()
        search.press(key)
        data = snapshot()
        assert data['active'] == data['visible'][index]['id'] and data['active'], data
        assert len(data['styled']) == 1, data
        return data

    def composed(key):
        before = snapshot()
        url = page.url
        outcome = search.evaluate("""(input,key) => {
          let bubbled=false;
          const observe=()=>{bubbled=true;};
          document.addEventListener('keydown',observe,{once:true});
          const event=new KeyboardEvent('keydown',{key,bubbles:true,cancelable:true,composed:true,isComposing:true});
          const dispatched=input.dispatchEvent(event);
          document.removeEventListener('keydown',observe);
          return {isComposing:event.isComposing,defaultPrevented:event.defaultPrevented,dispatched,bubbled};
        }""", key)
        assert outcome == {'isComposing': True, 'defaultPrevented': False, 'dispatched': True, 'bubbled': True}, (key, outcome)
        page.wait_for_timeout(100)
        assert page.url == url, (key, url, page.url)
        after = snapshot()
        assert after['active'] == before['active'] and after['styled'] == before['styled'], (key, before, after)

    for path in ['/composition/architecture/composer-mvp/?audience=maintain', '/ja/']:
        page.goto(base + path)
        _open_search(page)
        search = page.locator('input[role="combobox"]')
        search.fill('policy')
        select = page.locator('[data-audience-search-filter] select')
        select.wait_for()
        settled()
        if path == '/ja/':
            assert '検索する目的' in page.locator('[data-audience-search-filter]').inner_text()
        subsets, stable = {}, {}
        for audience in ['all', 'use', 'maintain', 'all', 'use', 'maintain', 'use']:
            select.select_option(audience)
            cleared()
            data = snapshot()
            for hit in data['all']:
                key = urlsplit(hit['href']).path + '#' + urlsplit(hit['href']).fragment
                if hit['id'] and key in stable:
                    assert hit['id'] == stable[key], ('unstable result ID', hit)
                if hit['id']:
                    stable[key] = hit['id']
            subsets[audience] = [hit['href'].split('?')[0] for hit in data['visible']]
            if audience == 'all' and data['visible']:
                search.focus()
                search.press('ArrowDown')
                snapshot()
            elif audience != 'all':
                assert len(data['visible']) >= 2
                move('ArrowDown', 0)
                move('ArrowDown', 1)
                move('ArrowUp', 0)
                if audience == 'use':
                    exclusive = page.evaluate("async () => {const r=" + ROOT + ";const m=await window.TemplatesAudienceContext.loadRuntimeMap();return [...r.querySelectorAll('ol a[href]')].filter(a=>!a.closest('[hidden], [data-audience-filtered], [data-site-search-history]') && a.getClientRects().length).findIndex(a=>!m.documents[m.routes[new URL(a.href).pathname]].audiences.includes('maintain'));}")
                    assert exclusive >= 0, 'fixture requires a Use-only result'
                    for index in range(1, exclusive + 1):
                        move('ArrowDown', index)
        assert subsets['use'] != subsets['maintain'], 'fixture must expose different audience subsets'
        for cancellation in ['event.preventDefault()', 'event.preventDefault();event.stopImmediatePropagation()']:
            before, url = snapshot(), page.url
            search.evaluate('input => input.addEventListener("keydown", event => {' + cancellation + '}, {capture:true,once:true})')
            search.press('Enter')
            assert page.url == url and snapshot()['active'] == before['active']
        page.evaluate("() => {document.documentElement.dataset.audience='maintain';window.dispatchEvent(new CustomEvent('templates:audience-changed'));}")
        assert select.input_value() == 'maintain'
        cleared()
        move('ArrowDown', 0)
        old = snapshot()['active']
        page.evaluate("() => {const root=" + ROOT + ";const input=root.querySelector('input[role=combobox]');const hit=root.getElementById(input.getAttribute('aria-activedescendant'));hit.replaceWith(hit.cloneNode(true));}")
        page.wait_for_function("() => {const r=" + ROOT + ";return !r.querySelector('input[role=combobox]').hasAttribute('aria-activedescendant')}")
        cleared()
        assert old not in [hit['id'] for hit in snapshot()['all']]
        move('ArrowDown', 0)
        page.evaluate("() => {const r=" + ROOT + ";r.getElementById(r.querySelector('input[role=combobox]').getAttribute('aria-activedescendant')).hash='replacement-hit';}")
        page.wait_for_function("() => !(" + ROOT + ").querySelector('input[role=combobox]').hasAttribute('aria-activedescendant')")
        cleared()
        move('ArrowDown', 0)
        previous = [hit['href'] for hit in snapshot()['all']]
        search.fill('composition')
        cleared()
        page.wait_for_function("previous => {const r=" + ROOT + ";const links=[...r.querySelectorAll('ol a[href]')].filter(a=>!a.closest('[data-site-search-history]'));return links.length && JSON.stringify(links.map(a=>a.href))!==JSON.stringify(previous)}", arg=previous)
        settled()
        snapshot()
        move('ArrowDown', 0)
        search.fill('zzzzs5nomatcheszzzz')
        cleared()
        page.wait_for_function("() => ![...(" + ROOT + ").querySelectorAll('ol a[href]')].some(a=>!a.closest('[data-site-search-history]'))")
        select.select_option('all')
        snapshot()
        url = page.url
        search.press('ArrowDown')
        search.press('Enter')
        assert page.url == url
        cleared()
        search.fill('policy')
        settled()
        select.select_option('maintain')
        cleared()
        for key in ['ArrowDown', 'ArrowUp', 'Enter']:
            composed(key)
        data = move('ArrowUp', -1)
        target = data['visible'][-1]['href']
        with page.expect_navigation(wait_until='domcontentloaded'):
            search.press('Enter')
        assert page.url == target, ('Enter differs from active descendant', page.url, target)
        records.append({'locale': 'ja' if path == '/ja/' else 'en', 'identity_transitions': 'all/native links; use/maintain/repeat; controlled listbox/options; observer replacement; href reuse; audience event; engine refresh/empty/all; Arrow order; cancellation; IME composition; Enter passed'})
    return records
