(() => {
  "use strict";

  const RUNTIME_MAP_URL = "/reader-navigation-runtime.json";
  const PRIMARY_NAV_SELECTOR = "nav.md-nav--primary";
  const LANGUAGE_PATH = /^\/([a-z]{2,3}(?:-[a-z0-9]{2,8})*)\//;
  let runtimePromise;
  let applyGeneration = 0;

  function currentLanguage() {
    const match = window.location.pathname.match(LANGUAGE_PATH);
    return match ? match[1] : undefined;
  }

  function validStringMap(value) {
    if (!value || typeof value !== "object" || Array.isArray(value)) {
      return false;
    }
    return Object.entries(value).every(
      ([key, item]) => typeof key === "string" && key && typeof item === "string" && item,
    );
  }

  function validateRuntimeMap(model) {
    if (
      !model ||
      model.schema_version !== 1 ||
      model.canonical_language !== "en" ||
      !Array.isArray(model.locales)
    ) {
      throw new Error("Reader navigation runtime map is invalid");
    }
    const seen = new Set();
    for (const locale of model.locales) {
      if (
        !locale ||
        typeof locale.language !== "string" ||
        locale.language === "en" ||
        seen.has(locale.language) ||
        !validStringMap(locale.labels) ||
        !validStringMap(locale.routes)
      ) {
        throw new Error("Reader navigation locale record is invalid");
      }
      seen.add(locale.language);
    }
    return model;
  }

  function loadRuntimeMap() {
    if (!runtimePromise) {
      runtimePromise = fetch(RUNTIME_MAP_URL, {
        credentials: "same-origin",
        cache: "no-cache",
      })
        .then((response) => {
          if (!response.ok) {
            throw new Error(`Reader navigation map request failed: ${response.status}`);
          }
          return response.json();
        })
        .then(validateRuntimeMap)
        .catch((error) => {
          runtimePromise = undefined;
          throw error;
        });
    }
    return runtimePromise;
  }

  function localeFor(model, language) {
    return model.locales.find((locale) => locale.language === language);
  }

  function replaceDirectText(element, replacement) {
    for (const node of element.childNodes) {
      if (node.nodeType !== Node.TEXT_NODE || !node.nodeValue.trim()) {
        continue;
      }
      const leading = node.nodeValue.match(/^\s*/)?.[0] || "";
      const trailing = node.nodeValue.match(/\s*$/)?.[0] || "";
      node.nodeValue = `${leading}${replacement}${trailing}`;
      return true;
    }
    return false;
  }

  function restoreNavigation(nav) {
    for (const element of nav.querySelectorAll("[data-reader-nav-canonical-label]")) {
      const canonical = element.dataset.readerNavCanonicalLabel;
      if (!canonical) {
        continue;
      }
      if (element.matches("label.md-nav__title")) {
        replaceDirectText(element, canonical);
      } else if (element.classList.contains("md-ellipsis")) {
        element.textContent = canonical;
      }
      delete element.dataset.readerNavCanonicalLabel;
    }
    for (const link of nav.querySelectorAll("a[data-reader-nav-canonical-href]")) {
      const canonicalHref = link.dataset.readerNavCanonicalHref;
      if (canonicalHref) {
        link.setAttribute("href", canonicalHref);
      }
      delete link.dataset.readerNavCanonicalHref;
    }
    delete nav.dataset.readerNavigationLanguage;
  }

  function localizeEllipsisLabels(nav, labels) {
    for (const element of nav.querySelectorAll(".md-ellipsis")) {
      if (element.childElementCount !== 0) {
        continue;
      }
      const canonical = element.textContent.trim();
      const localized = labels[canonical];
      if (!localized || localized === canonical) {
        continue;
      }
      element.dataset.readerNavCanonicalLabel = canonical;
      element.textContent = localized;
    }
  }

  function localizeNestedTitles(nav, labels) {
    for (const label of nav.querySelectorAll("label.md-nav__title")) {
      let canonical;
      for (const node of label.childNodes) {
        if (node.nodeType === Node.TEXT_NODE && node.nodeValue.trim()) {
          canonical = node.nodeValue.trim();
          break;
        }
      }
      const localized = canonical ? labels[canonical] : undefined;
      if (!localized || localized === canonical) {
        continue;
      }
      label.dataset.readerNavCanonicalLabel = canonical;
      replaceDirectText(label, localized);
    }
  }

  function localizeLinks(nav, routes) {
    for (const link of nav.querySelectorAll("a.md-nav__link[href]")) {
      const rawHref = link.getAttribute("href");
      if (!rawHref) {
        continue;
      }
      let target;
      try {
        target = new URL(rawHref, window.location.href);
      } catch (_error) {
        continue;
      }
      if (target.origin !== window.location.origin) {
        continue;
      }
      const localizedPath = routes[target.pathname];
      if (!localizedPath || localizedPath === target.pathname) {
        continue;
      }
      link.dataset.readerNavCanonicalHref = rawHref;
      link.setAttribute("href", `${localizedPath}${target.search}${target.hash}`);
    }
  }

  function localizeNavigation(nav, locale) {
    restoreNavigation(nav);
    localizeEllipsisLabels(nav, locale.labels);
    localizeNestedTitles(nav, locale.labels);
    localizeLinks(nav, locale.routes);
    nav.dataset.readerNavigationLanguage = locale.language;
  }

  async function applyReaderNavigation() {
    const generation = ++applyGeneration;
    const initialNavigations = document.querySelectorAll(PRIMARY_NAV_SELECTOR);
    if (!initialNavigations.length) {
      return;
    }

    const initialLanguage = currentLanguage();
    if (!initialLanguage) {
      for (const nav of initialNavigations) {
        restoreNavigation(nav);
      }
      return;
    }

    let model;
    try {
      model = await loadRuntimeMap();
    } catch (error) {
      if (generation === applyGeneration) {
        console.warn("Reader navigation localization unavailable", error);
      }
      return;
    }

    if (generation !== applyGeneration) {
      return;
    }

    const activeLanguage = currentLanguage();
    const currentNavigations = document.querySelectorAll(PRIMARY_NAV_SELECTOR);
    if (!activeLanguage) {
      for (const nav of currentNavigations) {
        restoreNavigation(nav);
      }
      return;
    }

    const locale = localeFor(model, activeLanguage);
    if (!locale) {
      for (const nav of currentNavigations) {
        restoreNavigation(nav);
      }
      return;
    }
    for (const nav of currentNavigations) {
      localizeNavigation(nav, locale);
    }
  }

  void applyReaderNavigation();
  window.addEventListener("pageshow", () => void applyReaderNavigation());
  window.addEventListener("popstate", () => void applyReaderNavigation());

  const navigationDocument = window.document$;
  if (navigationDocument && typeof navigationDocument.subscribe === "function") {
    navigationDocument.subscribe(() => void applyReaderNavigation());
  }
})();

/* Site-local search history. Kept in the pre-cached reader runtime so it also works offline. */
(() => {
  "use strict";

  const SEARCH_ROOT_SELECTOR = '[data-md-component="search"]';
  const SEARCH_INPUT_SELECTOR = '[data-md-component="search-query"]';
  const SEARCH_SCROLL_SELECTOR = ".md-search__scrollwrap";
  const SEARCH_RESULT_LINK_SELECTOR = "a.md-search-result__link[href]";
  const SEARCH_HISTORY_STORAGE_KEY = "templates.search-history.v1";
  const MAX_SEARCH_HISTORY = 10;
  const STRINGS = Object.freeze({
    en: Object.freeze({
      heading: "Recent searches",
      clear: "Clear history",
    }),
    ja: Object.freeze({
      heading: "最近の検索",
      clear: "履歴を消去",
    }),
  });

  function normalizeQuery(value) {
    if (typeof value !== "string") {
      return "";
    }
    return value.normalize("NFC").trim().replace(/\s+/gu, " ");
  }

  function queryKey(value) {
    return normalizeQuery(value).toLowerCase();
  }

  function loadHistory() {
    try {
      const raw = window.localStorage.getItem(SEARCH_HISTORY_STORAGE_KEY);
      if (!raw) {
        return [];
      }
      const parsed = JSON.parse(raw);
      if (!Array.isArray(parsed)) {
        return [];
      }
      const result = [];
      const seen = new Set();
      for (const item of parsed) {
        const query = normalizeQuery(item);
        const key = queryKey(query);
        if (!query || seen.has(key)) {
          continue;
        }
        seen.add(key);
        result.push(query);
        if (result.length >= MAX_SEARCH_HISTORY) {
          break;
        }
      }
      return result;
    } catch (_error) {
      return [];
    }
  }

  function storeHistory(history) {
    try {
      window.localStorage.setItem(
        SEARCH_HISTORY_STORAGE_KEY,
        JSON.stringify(history.slice(0, MAX_SEARCH_HISTORY)),
      );
      return true;
    } catch (_error) {
      return false;
    }
  }

  function rememberQuery(value) {
    const query = normalizeQuery(value);
    if (!query) {
      return loadHistory();
    }
    const key = queryKey(query);
    const next = [
      query,
      ...loadHistory().filter((item) => queryKey(item) !== key),
    ].slice(0, MAX_SEARCH_HISTORY);
    storeHistory(next);
    return next;
  }

  function clearHistory() {
    try {
      window.localStorage.removeItem(SEARCH_HISTORY_STORAGE_KEY);
    } catch (_error) {
      return;
    }
  }

  function stringsForDocument() {
    const language = (document.documentElement?.lang || "en").toLowerCase();
    return language.split("-", 1)[0] === "ja" ? STRINGS.ja : STRINGS.en;
  }

  function createHistorySection() {
    const section = document.createElement("section");
    section.className = "md-search-result site-search-history";
    section.dataset.siteSearchHistory = "true";
    section.hidden = true;

    const meta = document.createElement("div");
    meta.className = "md-search-result__meta";

    const heading = document.createElement("span");
    heading.dataset.siteSearchHistoryHeading = "true";
    meta.appendChild(heading);

    const separator = document.createTextNode(" · ");
    meta.appendChild(separator);

    const clear = document.createElement("a");
    clear.href = "#";
    clear.dataset.siteSearchHistoryClear = "true";
    meta.appendChild(clear);

    const list = document.createElement("ol");
    list.className = "md-search-result__list";
    list.setAttribute("role", "list");
    list.dataset.siteSearchHistoryList = "true";

    section.append(meta, list);
    return section;
  }

  function historySection(root) {
    return root.querySelector("[data-site-search-history]");
  }

  function renderSearchHistory(root) {
    const input = root.querySelector(SEARCH_INPUT_SELECTOR);
    const section = historySection(root);
    if (!input || !section) {
      return;
    }

    const history = loadHistory();
    const visible = normalizeQuery(input.value) === "" && history.length > 0;
    section.hidden = !visible;
    if (!visible) {
      return;
    }

    const strings = stringsForDocument();
    const heading = section.querySelector("[data-site-search-history-heading]");
    const clear = section.querySelector("[data-site-search-history-clear]");
    const list = section.querySelector("[data-site-search-history-list]");
    if (!heading || !clear || !list) {
      return;
    }
    heading.textContent = strings.heading;
    clear.textContent = strings.clear;
    list.replaceChildren();

    for (const query of history) {
      const item = document.createElement("li");
      item.className = "md-search-result__item";

      const link = document.createElement("a");
      link.href = "#";
      link.className = "md-search-result__link";
      link.dataset.siteSearchHistoryQuery = query;

      const article = document.createElement("article");
      article.className = "md-search-result__article md-typeset";
      const title = document.createElement("h2");
      title.textContent = query;
      article.appendChild(title);
      link.appendChild(article);
      item.appendChild(link);
      list.appendChild(item);
    }
  }

  function selectHistoryQuery(event, root, input, link) {
    event.preventDefault();
    const query = normalizeQuery(link.dataset.siteSearchHistoryQuery || "");
    if (!query) {
      return;
    }
    rememberQuery(query);
    input.value = query;
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.focus({ preventScroll: true });
    renderSearchHistory(root);
  }

  function enhanceSearchRoot(root) {
    if (root.dataset.siteSearchHistoryEnhanced === "true") {
      renderSearchHistory(root);
      return;
    }
    const input = root.querySelector(SEARCH_INPUT_SELECTOR);
    const scroll = root.querySelector(SEARCH_SCROLL_SELECTOR);
    if (!input || !scroll) {
      return;
    }

    const section = createHistorySection();
    scroll.prepend(section);
    root.dataset.siteSearchHistoryEnhanced = "true";

    input.addEventListener("input", () => renderSearchHistory(root));
    input.addEventListener("focus", () => renderSearchHistory(root));
    input.form?.addEventListener("reset", () => {
      queueMicrotask(() => renderSearchHistory(root));
    });

    root.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof Element)) {
        return;
      }

      const clear = target.closest("[data-site-search-history-clear]");
      if (clear && root.contains(clear)) {
        event.preventDefault();
        clearHistory();
        renderSearchHistory(root);
        return;
      }

      const historyLink = target.closest("[data-site-search-history-query]");
      if (historyLink && root.contains(historyLink)) {
        selectHistoryQuery(event, root, input, historyLink);
        return;
      }

      const resultLink = target.closest(SEARCH_RESULT_LINK_SELECTOR);
      if (
        resultLink &&
        root.contains(resultLink) &&
        !resultLink.closest("[data-site-search-history]")
      ) {
        rememberQuery(input.value);
      }
    });

    renderSearchHistory(root);
  }

  function enhanceSearchHistory() {
    for (const root of document.querySelectorAll(SEARCH_ROOT_SELECTOR)) {
      enhanceSearchRoot(root);
    }
  }

  enhanceSearchHistory();
  window.addEventListener("pageshow", enhanceSearchHistory);
  window.addEventListener("popstate", enhanceSearchHistory);
  window.addEventListener("storage", (event) => {
    if (event.key !== SEARCH_HISTORY_STORAGE_KEY) {
      return;
    }
    for (const root of document.querySelectorAll(SEARCH_ROOT_SELECTOR)) {
      renderSearchHistory(root);
    }
  });

  const navigationDocument = window.document$;
  if (navigationDocument && typeof navigationDocument.subscribe === "function") {
    navigationDocument.subscribe(enhanceSearchHistory);
  }
})();
