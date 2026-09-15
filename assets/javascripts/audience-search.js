/** Audience presentation adapter for the existing Zensical search Shadow DOM. */
(() => {
  "use strict";
  if (window.TemplatesAudienceSearch) return;
  const states = new WeakMap();
  const pendingRoots = new WeakMap();
  const resultIds = new WeakMap();
  let nextResultId = 0;
  let model;
  const results = root => [...root.querySelectorAll("ol a[href]")].filter(a => !a.closest("[data-site-search-history]"));
  const visibleHits = root => results(root).filter(a => !a.closest("[hidden], [data-audience-filtered]") && a.getClientRects().length);
  function clearSelection(root, state) {
    state.selection = null;
    state.input.removeAttribute("aria-activedescendant");
    root.querySelectorAll("[data-audience-search-current]").forEach(a => a.removeAttribute("data-audience-search-current"));
  }
  function selectHit(root, state, hit) {
    clearSelection(root, state);
    state.selection = {hit, href:hit.href, id:hit.id};
    state.input.setAttribute("aria-activedescendant", hit.id);
    hit.setAttribute("data-audience-search-current", "");
  }
  const strings = () => document.documentElement.lang?.startsWith("ja")
    ? {filter:"検索する目的", all:"すべての目的", use:"Use templates · 使う", maintain:"Maintain templates · 保守する", authority:"正本", primary:"主な目的", empty:"この目的の検索結果はありません。すべての目的も検索できます。"}
    : {filter:"Search audience", all:"All audiences", use:"Use templates", maintain:"Maintain templates", authority:"Authority", primary:"Primary", empty:"No matches for this audience. Try All audiences."};
  function refresh(root, state) {
    state.observer.disconnect();
    const text = strings();
    state.label.firstChild.textContent = text.filter + " ";
    for (const option of state.select.options) if (option.textContent !== text[option.value]) option.textContent = text[option.value];
    const anchors = results(root);
    for (const anchor of anchors) {
      // Allocate over the complete result set, never the filtered keyboard subset.
      // A replacement/clone is a new node; a retained node keeps its stable ID.
      if (!resultIds.has(anchor)) {
        let id;
        do { id = `audience-search-hit-${nextResultId++}`; }
        while (root.getElementById(id) || document.getElementById(id));
        resultIds.set(anchor, id);
      }
      if (anchor.id !== resultIds.get(anchor)) anchor.id = resultIds.get(anchor);
      const url = new URL(anchor.href, location.href);
      const doc = model?.documents[model.routes[url.pathname]];
      const item = anchor.closest("li") || anchor;
      const visible = state.select.value === "all" || doc?.audiences.includes(state.select.value);
      item.hidden = !visible;
      item.toggleAttribute("data-audience-filtered", !visible);
      let badge = anchor.querySelector("[data-search-audiences]");
      if (!doc) { badge?.remove(); continue; }
      if (!badge) { badge = document.createElement("small"); badge.dataset.searchAudiences = ""; (anchor.firstElementChild || anchor).append(badge); }
      const caption = doc.audiences.map(a => text[a] + (a === doc.primary ? ` (${text.primary})` : "")).join(" · ") + ` · ${text.authority}: ${doc.key.split(":")[0]}`;
      if (badge.textContent !== caption) badge.textContent = caption;
      const active = document.documentElement.dataset.audience;
      // Bind result links to compatible context; the canonical tag remains unchanged.
      const audience = state.select.value !== "all" ? state.select.value : active;
      const context = doc.audiences.includes(audience) ? audience : doc.primary;
      if (state.select.value === "all") url.searchParams.delete("audience");
      else url.searchParams.set("audience", context);
      const trail = window.TemplatesAudienceShell.navigationTrail(model.navigation[context], doc.destination) || [doc.title];
      const menu = anchor.querySelector("menu");
      const names = [text[context], ...trail];
      if (menu && menu.textContent !== names.join("")) {
        menu.replaceChildren(...names.map(name => {const li=document.createElement("li");li.textContent=name;return li;}));
      }
      anchor.href = url.pathname + url.search + url.hash;
    }
    if (state.empty.textContent !== text.empty) state.empty.textContent = text.empty;
    state.empty.hidden = !anchors.length || anchors.some(a => !a.closest("[data-audience-filtered]"));
    const selection = state.selection;
    if (selection && (!visibleHits(root).includes(selection.hit) || selection.hit.href !== selection.href || selection.hit.id !== selection.id)) clearSelection(root, state);
    if (!state.selection) {
      // Do not take ownership of the engine's unfiltered active descendant.
      if (state.select.value !== "all") state.input.removeAttribute("aria-activedescendant");
      root.querySelectorAll("[data-audience-search-current]").forEach(a => a.removeAttribute("data-audience-search-current"));
    }
    state.observer.observe(root, {childList:true, subtree:true, attributes:true, attributeFilter:["href", "id", "hidden"]});
  }
  function bind(root) {
    if (states.has(root)) { refresh(root, states.get(root)); return; }
    const input = root.querySelector('input[role="combobox"]');
    if (!input) {
      if (!pendingRoots.has(root)) {
        const observer = new MutationObserver(() => bind(root));
        pendingRoots.set(root, observer); observer.observe(root, {childList:true, subtree:true});
      }
      return;
    }
    pendingRoots.get(root)?.disconnect(); pendingRoots.delete(root);
    const label = document.createElement("label"); label.dataset.audienceSearchFilter = ""; label.append(document.createTextNode(""));
    const select = document.createElement("select");
    for (const value of ["all", "use", "maintain"]) { const option = document.createElement("option"); option.value = value; select.append(option); }
    const current = document.documentElement.dataset.audience;
    select.value = ["use", "maintain"].includes(current) ? current : "all";
    label.append(select); input.parentElement.after(label); label.parentElement.style.flexWrap = "wrap";
    const empty = document.createElement("p"); empty.setAttribute("role", "status"); empty.hidden = true; label.after(empty);
    const style = document.createElement("style");
    style.textContent = `
      [data-audience-filtered] { display:none !important; }
      [data-audience-search-current] { outline:2px solid var(--audience-accent); outline-offset:-2px; }
      [data-audience-search-filter] { flex-basis:100%; display:flex; align-items:center; gap:.5rem; padding:.4rem .8rem; font:14px/1.5 system-ui; }
      [data-audience-search-filter] select { min-height:44px; padding:.4rem; color:var(--audience-accent-strong); background:var(--audience-accent-soft); border:1px solid currentColor; }
      [data-audience-search-filter] select:focus-visible { outline:3px solid var(--audience-accent); outline-offset:2px; }
      [data-search-audiences] { display:block; font:12px/1.6 system-ui; color:var(--audience-accent-strong); background:var(--audience-accent-soft); border-inline-start:3px solid var(--audience-accent); padding:.2rem .5rem; margin-top:.25rem; }
      @media (forced-colors:active) { [data-search-audiences], [data-audience-search-filter] select { color:CanvasText; background:Canvas; border-color:CanvasText; } }
    `;
    root.append(style);
    const state = {input,label,select,empty,observer:new MutationObserver(() => refresh(root,state))}; states.set(root,state);
    select.addEventListener("change", () => { clearSelection(root,state); refresh(root,state); });
    input.addEventListener("input", () => { if (state.selection || select.value !== "all") clearSelection(root,state); });
    // The engine owns unfiltered keyboard behavior. Filtering must never activate a hidden hit.
    root.addEventListener("keydown", event => {
      if (event.target !== input || select.value === "all" || !["ArrowDown","ArrowUp","Enter"].includes(event.key)) return;
      if (event.defaultPrevented) { event.stopImmediatePropagation(); return; }
      refresh(root,state);
      const hits = visibleHits(root);
      if (!hits.length) { clearSelection(root,state); event.preventDefault(); event.stopImmediatePropagation(); return; }
      const selected = input.getAttribute("aria-activedescendant");
      let index = hits.findIndex(a => a.id === selected);
      if (event.key === "Enter") {
        // Give search-history's capture listener the real query before the link action.
        event.preventDefault(); event.stopImmediatePropagation();
        const hit = hits[Math.max(index,0)]; selectHit(root,state,hit); hit.click(); return;
      }
      event.preventDefault(); event.stopImmediatePropagation();
      index = event.key === "ArrowDown" ? (index + 1) % hits.length : (index < 0 ? hits.length - 1 : (index - 1 + hits.length) % hits.length);
      selectHit(root,state,hits[index]);
      hits[index].scrollIntoView({block:"nearest"});
    });
    refresh(root,state);
  }
  function discover() {
    if (!model) return;
    for (const host of document.body?.children || []) if (host.shadowRoot) bind(host.shadowRoot);
  }
  window.TemplatesAudienceSearch = {discover};
  function start() {
    window.TemplatesAudienceContext.loadRuntimeMap().then(value => {model=value;discover();}).catch(() => {});
    new MutationObserver(discover).observe(document.body, {childList:true});
    window.addEventListener("templates:audience-changed", () => {
      for (const host of document.body.children) {
        const state = states.get(host.shadowRoot);
        if (state) {clearSelection(host.shadowRoot,state);const audience=document.documentElement.dataset.audience; state.select.value=["use","maintain"].includes(audience)?audience:"all";}
      }
      discover();
    });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start, {once:true}); else start();
})();
