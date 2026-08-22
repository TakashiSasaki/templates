(() => {
  "use strict";

  const RUNTIME_MAP_URL = "/reader-navigation-runtime.json";
  const PRIMARY_NAV_SELECTOR = "nav.md-nav--primary";
  const LANGUAGE_PATH = /^\/([a-z]{2,3}(?:-[a-z0-9]{2,8})*)\//;
  let runtimePromise;

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
      if (element.classList.contains("md-ellipsis")) {
        element.textContent = canonical;
      } else if (element.matches("label.md-nav__title")) {
        replaceDirectText(element, canonical);
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
    const navigations = document.querySelectorAll(PRIMARY_NAV_SELECTOR);
    if (!navigations.length) {
      return;
    }

    const language = currentLanguage();
    if (!language) {
      for (const nav of navigations) {
        restoreNavigation(nav);
      }
      return;
    }

    let model;
    try {
      model = await loadRuntimeMap();
    } catch (error) {
      console.warn("Reader navigation localization unavailable", error);
      return;
    }
    const locale = localeFor(model, language);
    if (!locale) {
      for (const nav of navigations) {
        restoreNavigation(nav);
      }
      return;
    }
    for (const nav of navigations) {
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
