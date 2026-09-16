/** Reader presentation of the existing audience controller's semantic state. */
(() => {
  "use strict";
  if (window.TemplatesAudienceShell) return;
  const labels = {
    en: {use: "Use templates", maintain: "Maintain templates", neutral: "Choose your journey", switch: "Reader journey", current: "Current journey"},
    ja: {use: "Use templates · 使う", maintain: "Maintain templates · 保守する", neutral: "目的を選ぶ", switch: "読者の目的", current: "現在の目的"},
  };
  function strings() {
    return labels[document.documentElement.lang?.split("-")[0]] || labels.en;
  }
  function navigationTrail(nodes, destination, trail = []) {
      for (const node of nodes) {
        if (node.children) {
          const match = navigationTrail(node.children, destination, [...trail, node.title]);
          if (match) return match;
        } else if (node.destination === destination) return [...trail, node.title];
      }
      return null;
    }
  let generation = 0;
  async function render() {
    const turn = ++generation;
    const audience = document.documentElement.dataset.audience || "neutral";
    const text = strings();
    let shell = document.querySelector("[data-audience-shell]");
    if (!shell) {
      shell = document.createElement("section");
      shell.dataset.audienceShell = "";
      shell.className = "audience-shell";
      shell.innerHTML = '<span class="audience-badge" data-audience-label></span><div class="audience-switcher" role="group"><button type="button" data-audience-switch="use"></button><button type="button" data-audience-switch="maintain"></button></div>';
      const main = document.querySelector(".md-container, main") || document.body;
      if (!main) return;
      main.prepend(shell);
    }
    shell.hidden = audience === "neutral" && Boolean(document.querySelector(".audience-landing"));
    shell.querySelector("[data-audience-label]").textContent = text[audience] || text.neutral;
    shell.querySelector(".audience-switcher").setAttribute("aria-label", text.switch);
    for (const button of shell.querySelectorAll("[data-audience-switch]")) {
      const target = button.dataset.audienceSwitch;
      button.textContent = text[target];
      button.setAttribute("aria-pressed", String(target === audience));
      button.title = target === audience ? text.current : text[target];
    }
    let model, locale;
    try {
      model = await window.TemplatesAudienceContext.loadRuntimeMap();
      const reader = window.TemplatesReaderNavigation;
      if (reader) locale = reader.localeFor(await reader.loadRuntimeMap(), reader.currentLanguage());
    } catch { return; }
    if (turn !== generation) return;
    const label = value => locale?.labels[value] || value;
    const href = value => {
      const url = new URL(locale?.routes[value] || value, location.href);
      if (audience !== "neutral") url.searchParams.set("audience", audience);
      return url.pathname + url.search + url.hash;
    };
    const meta = window.TemplatesAudienceContext.getDocumentMetadata(model);
    const tree = model.navigation?.[audience];
    for (const entry of document.querySelectorAll("[data-audience-entry]")) {
      const target = entry.dataset.audienceEntry;
      const route = model.localized_overviews?.[document.documentElement.lang]?.[target] || model.overviews[target];
      if (route) entry.href = route + "?audience=" + target;
    }
    for (const button of shell.querySelectorAll("[data-audience-switch]")) {
      if (!meta.audiences.has(button.dataset.audienceSwitch) || meta.isLanding)
        button.title = (text === labels.ja ? "概要へ: " : "Open overview: ") + text[button.dataset.audienceSwitch];
    }
    let utilities = shell.querySelector(".audience-utilities");
    if (!utilities) { utilities = document.createElement("nav"); utilities.className = "audience-utilities"; shell.append(utilities); }
    utilities.setAttribute("aria-label", text === labels.ja ? "共通ツール" : "Shared tools");
    utilities.replaceChildren();
    for (const [route, en, ja] of [["/glossary/","Glossary","用語集"],["/files/","Source","ソース"],["/guided/","Browse by index","索引から探す"],["/build-provenance.json","Build provenance","ビルド来歴"]]) {
      const link = document.createElement("a"); link.href = href(route); link.textContent = text === labels.ja ? ja : en; utilities.append(link);
    }
    function list(nodes, trail = []) {
      const ul = document.createElement("ul");
      for (const node of nodes) {
        const li = document.createElement("li");
        if (node.children) {
          const details = document.createElement("details");
          const summary = document.createElement("summary");
          summary.textContent = label(node.title);
          details.open = contains(node.children, meta.document?.destination);
          details.append(summary, list(node.children, [...trail, node.title]));
          li.append(details);
        } else {
          const link = document.createElement("a");
          link.href = href(node.href); link.textContent = label(node.title);
          if (node.destination === meta.document?.destination) link.setAttribute("aria-current", "page");
          li.append(link);
        }
        ul.append(li);
      }
      return ul;
    }
    function contains(nodes, destination) {
      return nodes.some(n => n.children ? contains(n.children, destination) : n.destination === destination);
    }
    for (const nav of document.querySelectorAll("nav.md-nav--primary")) {
      // Replace only the Site navigation projection; provider index content stays intact.
      if (!nav.hasAttribute("data-audience-original")) {
        nav.dataset.audienceOriginal = nav.innerHTML;
        const originalLabel = nav.getAttribute("aria-label");
        nav.dataset.audienceOriginalLabel = originalLabel ?? "";
        nav.dataset.audienceOriginalLabelPresent = String(originalLabel !== null);
      }
      if (!tree) {
        nav.innerHTML = nav.dataset.audienceOriginal;
        if (nav.dataset.audienceOriginalLabelPresent === "true") nav.setAttribute("aria-label", nav.dataset.audienceOriginalLabel);
        else nav.removeAttribute("aria-label");
        continue;
      }
      const title = document.createElement("p"); title.className = "audience-navigation__title";
      title.textContent = text[audience];
      const content = document.createElement("div"); content.className = "audience-navigation";
      content.append(title, list(tree)); nav.replaceChildren(content);
      nav.setAttribute("aria-label", text[audience]);
    }
    const article = document.querySelector(".md-content__inner, main");
    let crumbs = article?.querySelector("[data-audience-breadcrumb]");
    if (article && !crumbs) {
      crumbs = document.createElement("nav"); crumbs.dataset.audienceBreadcrumb = "";
      crumbs.className = "audience-breadcrumb"; article.prepend(crumbs);
    }
    if (crumbs) {
      crumbs.replaceChildren(); crumbs.hidden = audience === "neutral";
      crumbs.setAttribute("aria-label", text === labels.ja ? "パンくずリスト" : "Breadcrumb");
      if (tree) {
        const home = document.createElement("a"); home.href = href(model.overviews[audience]); home.textContent = text[audience]; crumbs.append(home);
        for (const item of navigationTrail(tree, meta.document?.destination) || [text === labels.ja ? "共通ツール" : "Shared service"]) {
          const part = document.createElement("span"); part.textContent = " / " + label(item); crumbs.append(part);
        }
        crumbs.lastElementChild?.setAttribute("aria-current", "page");
      }
    }
    // Explicitly announce cross-audience document destinations before activation.
    for (const link of document.querySelectorAll('main a[href], [data-md-component="toc"] a[href], .translation-switcher a[href]')) {
      if (link.getAttribute("href")?.startsWith("#")) continue;
      const url = new URL(link.href, location.href);
      if (url.origin !== location.origin || link.closest(".audience-shell, .audience-breadcrumb")) continue;
      if (url.pathname === location.pathname && url.hash) {
        if (link.matches('.headerlink, [data-md-component="toc"] a')) link.setAttribute("href", url.hash);
        continue;
      }
      const destination = model.routes[url.pathname];
      const doc = model.documents[destination];
      link.querySelector("[data-audience-destination]")?.remove();
      if (doc && !doc.is_landing && audience !== "neutral" && !doc.audiences.includes(audience)) {
        const badge = document.createElement("small"); badge.dataset.audienceDestination = "";
        badge.textContent = " · " + text[doc.primary]; link.append(badge);
      }
      if (doc?.audiences.includes(audience) && !doc.is_landing && !link.hasAttribute("data-audience-entry")) {
        url.searchParams.set("audience", audience); link.href = url.pathname + url.search + url.hash;
      }
    }

  }
  window.TemplatesAudienceShell = {render, strings, navigationTrail};
  window.addEventListener("templates:audience-changed", render);
  window.addEventListener("pageshow", render);
  window.document$?.subscribe(render);
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", render, {once:true});
  else render();
})();
