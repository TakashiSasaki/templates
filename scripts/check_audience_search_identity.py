"""Exercise the shipped search adapter in the actual assembled search DOM."""
from urllib.parse import urlsplit

ROOT = "[...document.body.children].map(h => h.shadowRoot).find(r => r?.querySelector('input[role=combobox]'))"
SNAPSHOT = """() => {
 const root=ROOT;
 const input=root.querySelector('input[role=combobox]');
 const filter=root.querySelector('[data-audience-search-filter] select')?.value || 'all';
 const anchors=[...root.querySelectorAll('ol a[href]')].filter(a=>!a.closest('[data-site-search-history]'));
 const visible=anchors.filter(a=>!a.closest('[hidden], [data-audience-filtered]') && a.getClientRects().length);
 const ids=[...root.querySelectorAll('[id]')].map(e=>e.id).filter(Boolean);
 const active=input.getAttribute('aria-activedescendant');
 const matches=active ? [...root.querySelectorAll('[id]')].filter(e=>e.id===active) : [];
 const controls=(input.getAttribute('aria-controls')||'').split(/\s+/).filter(Boolean);
 const controlled=controls.map(id=>root.getElementById(id));
 return {filter,ids,active,matches:matches.length,activeVisible:matches.length===1 && visible.includes(matches[0]),controls,
   controlled:controlled.map(e=>e&&({id:e.id,role:e.getAttribute('role'),containsActive:!!(active&&e.querySelector('#'+CSS.escape(active)))})),
   all:anchors.map(a=>({id:a.id,href:a.href,role:a.getAttribute('role'),selected:a.getAttribute('aria-selected')})),
   visible:visible.map(a=>({id:a.id,href:a.href,role:a.getAttribute('role'),selected:a.getAttribute('aria-selected')})),
   styled:[...root.querySelectorAll('[data-audience-search-current]')].map(a=>({id:a.id,visible:visible.includes(a)}))};
}""".replace('ROOT',ROOT)


def check_search_identity(page, base):
    from scripts.check_search_history import _open_search
    records=[]
    def snapshot():
        data=page.evaluate(SNAPSHOT)
        assert len(data['ids'])==len(set(data['ids'])), ('duplicate search DOM IDs',data)
        visible_ids=[h['id'] for h in data['visible'] if h['id']]
        assert len(visible_ids)==len(set(visible_ids))
        if data['filter']=='all':
            assert not any(h['role']=='option' for h in data['all']), ('all-audience result lost native link semantics',data)
            assert not any(h['selected'] is not None for h in data['all']), ('adapter selection leaked into all-audience results',data)
            assert not any(c and c['role']=='listbox' for c in data['controlled']), ('adapter listbox leaked into all-audience search',data)
        elif data['all']:
            assert data['controls'], ('search results are not controlled by the combobox',data)
            assert all(c and c['role']=='listbox' for c in data['controlled']), ('controlled popup is not a listbox',data)
            assert all(h['role']=='option' for h in data['all']), ('search hit is not exposed as an option',data)
        if data['filter']!='all' and data['active']:
            assert data['matches']==1 and data['activeVisible'], ('invalid active descendant',data)
            assert any(c and c['containsActive'] for c in data['controlled']), ('active descendant is outside aria-controls popup',data)
            assert sum(h['selected']=='true' for h in data['all'])==1, ('active option selection is not unique',data)
            assert next(h for h in data['visible'] if h['id']==data['active'])['selected']=='true', ('active option is not aria-selected',data)
        elif data['filter']!='all':
            assert not any(h['selected']=='true' for h in data['all']), ('aria-selected remained after selection cleared',data)
        assert all(s['visible'] and s['id']==data['active'] for s in data['styled']), ('stale selection style',data)
        return data
    def cleared():
        data=snapshot();assert not data['active'] and not data['styled'], data
    def settled():
        page.wait_for_function("() => {const root="+ROOT+";return root?.querySelector('[data-search-audiences]')}")
    def move(key, index):
        search.focus();search.press(key);data=snapshot()
        assert data['active']==data['visible'][index]['id'] and data['active'],data
        assert len(data['styled'])==1
        return data
    def composed(key):
        before=snapshot();url=page.url
        outcome=search.evaluate("""(input,key) => {
          let bubbled=false;
          const observe=()=>{bubbled=true;};
          document.addEventListener('keydown',observe,{once:true});
          const event=new KeyboardEvent('keydown',{key,bubbles:true,cancelable:true,composed:true,isComposing:true});
          const dispatched=input.dispatchEvent(event);
          document.removeEventListener('keydown',observe);
          return {isComposing:event.isComposing,defaultPrevented:event.defaultPrevented,dispatched,bubbled};
        }""",key)
        assert outcome['isComposing'] is True,outcome
        assert outcome['defaultPrevented'] is False,outcome
        assert outcome['dispatched'] is True,outcome
        assert outcome['bubbled'] is True,('composed key event did not remain unowned',key,outcome)
        page.wait_for_timeout(100)
        assert page.url==url,(key,url,page.url)
        after=snapshot()
        assert after['active']==before['active'] and after['styled']==before['styled'],(key,before,after)
    for path in ['/composition/architecture/composer-mvp/?audience=maintain','/ja/']:
        page.goto(base+path);_open_search(page)
        search=page.locator('input[role="combobox"]');search.fill('policy')
        select=page.locator('[data-audience-search-filter] select');select.wait_for();settled()
        if path=='/ja/':assert '検索する目的' in page.locator('[data-audience-search-filter]').inner_text()
        subsets={};stable={}
        for audience in ['all','use','maintain','all','use','maintain','use']:
            select.select_option(audience);cleared()
            data=snapshot()
            for h in data['all']:
                # Audience query changes presentation context, not result identity.
                key=urlsplit(h['href']).path+'#'+urlsplit(h['href']).fragment
                if h['id'] and key in stable:assert h['id']==stable[key],('unstable result ID',h)
                if h['id']:stable[key]=h['id']
            subsets[audience]=[h['href'].split('?')[0] for h in data['visible']]
            if audience=='all' and data['visible']:
                # Native engine owns unfiltered keyboard behavior; adapter roles must stay restored.
                search.focus();search.press('ArrowDown');snapshot()
            elif audience!='all':
                assert len(data['visible'])>=2
                move('ArrowDown',0);move('ArrowDown',1);move('ArrowUp',0)
                if audience=='use':
                    # Select a Use-only hit so the next Maintain transition hides it.
                    exclusive=page.evaluate("async () => {const r="+ROOT+";const m=await window.TemplatesAudienceContext.loadRuntimeMap();return [...r.querySelectorAll('ol a[href]')].filter(a=>!a.closest('[hidden], [data-audience-filtered], [data-site-search-history]') && a.getClientRects().length).findIndex(a=>!m.documents[m.routes[new URL(a.href).pathname]].audiences.includes('maintain'));}")
                    assert exclusive>=0, 'fixture requires a Use-only result'
                    for index in range(1,exclusive+1):move('ArrowDown',index)
        assert subsets['use']!=subsets['maintain'], 'fixture must expose different audience subsets'
        # Both default-prevented and fully cancelled key events leave selection intact.
        for cancel in ['event.preventDefault()', 'event.preventDefault();event.stopImmediatePropagation()']:
            before=snapshot();url=page.url
            search.evaluate('input => input.addEventListener("keydown", event => {'+cancel+'}, {capture:true,once:true})')
            search.press('Enter');assert page.url==url;assert snapshot()['active']==before['active']
        # A semantic audience event must clear selection just like the native select.
        page.evaluate("() => {document.documentElement.dataset.audience='maintain';window.dispatchEvent(new CustomEvent('templates:audience-changed'));}")
        assert select.input_value()=='maintain';cleared();move('ArrowDown',0)
        # Clone replacement copies the old DOM ID; the observer must assign a new identity.
        old=snapshot()['active']
        page.evaluate("() => {const root="+ROOT+";const input=root.querySelector('input[role=combobox]');const hit=root.getElementById(input.getAttribute('aria-activedescendant'));hit.replaceWith(hit.cloneNode(true));}")
        page.wait_for_function("() => {const r="+ROOT+";return !r.querySelector('input[role=combobox]').hasAttribute('aria-activedescendant')}")
        cleared();assert old not in [h['id'] for h in snapshot()['all']]
        move('ArrowDown',0)
        # In-place href changes are another engine result-reuse path.
        page.evaluate("() => {const r="+ROOT+";r.getElementById(r.querySelector('input[role=combobox]').getAttribute('aria-activedescendant')).hash='replacement-hit';}")
        page.wait_for_function("() => !(("+ROOT+").querySelector('input[role=combobox]').hasAttribute('aria-activedescendant'))")
        cleared();move('ArrowDown',0)
        # Real engine query updates and empty results must discard stale ARIA/style state.
        previous=[h['href'] for h in snapshot()['all']]
        search.fill('composition');cleared()
        page.wait_for_function("previous => {const r="+ROOT+";const links=[...r.querySelectorAll('ol a[href]')].filter(a=>!a.closest('[data-site-search-history]'));return links.length && JSON.stringify(links.map(a=>a.href))!==JSON.stringify(previous)}",arg=previous)
        settled();snapshot();move('ArrowDown',0)
        search.fill('zzzzs5nomatcheszzzz');cleared()
        page.wait_for_function("() => ![...("+ROOT+").querySelectorAll('ol a[href]')].some(a=>!a.closest('[data-site-search-history]'))")
        url=page.url;search.press('ArrowDown');search.press('Enter');assert page.url==url;cleared()
        search.fill('policy');settled();select.select_option('maintain');cleared()
        # IME composition keystrokes belong to the input method, not filtered-result navigation.
        for key in ['ArrowDown','ArrowUp','Enter']:composed(key)
        data=move('ArrowUp',-1);target=data['visible'][-1]['href']
        with page.expect_navigation(wait_until='domcontentloaded'):search.press('Enter')
        assert page.url==target, ('Enter differs from active descendant',page.url,target)
        records.append({'locale': 'ja' if path=='/ja/' else 'en','identity_transitions':'all/native links; use/maintain/repeat; controlled listbox/options; observer replacement; href reuse; audience event; engine refresh/empty; Arrow order; cancellation; IME composition; Enter passed'})
    return records
