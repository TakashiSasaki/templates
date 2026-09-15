/** Site audience state; membership comes only from the assembled manifest projection. */
(() => {
  "use strict";
  // Instant navigation or repeated script evaluation must not install another controller.
  if (window.TemplatesAudienceContext) return;

  const STORAGE_KEY = "templates-audience-context";
  const HISTORY_KEY = "templatesAudienceContext";
  const CHANGE_EVENT = "templates:audience-changed";
  const RUNTIME_MAP_URL = "/audience-runtime.json";
  const VALID_AUDIENCES = new Set(["use", "maintain"]);
  let runtimePromise = null;
  let applyGeneration = 0;
  let initialized = false;
  let lastState = null;

  // Zensical replaces history.state with scroll offsets before pushing an
  // instant-navigation entry and on scroll. Preserve only our namespaced field
  // on same-document replacements; new documents must resolve their own state.
  const replaceState = history.replaceState.bind(history);
  history.replaceState = function (state, title, url) {
    const path = url == null ? location.pathname : new URL(url, location.href).pathname;
    const recorded = history.state?.[HISTORY_KEY];
    if (path === location.pathname && recorded?.path === path &&
        !Object.prototype.hasOwnProperty.call(state || {}, HISTORY_KEY)) {
      state = { ...state, [HISTORY_KEY]: recorded };
    }
    return replaceState(state, title, url);
  };

  function loadRuntimeMap() {
    if (!runtimePromise) {
      runtimePromise = fetch(RUNTIME_MAP_URL, { credentials: "same-origin", cache: "no-cache" })
        .then(response => {
          if (!response.ok) throw new Error("Audience runtime map unavailable");
          return response.json();
        })
        .then(data => {
          if (data.schema_version !== 1 || JSON.stringify(data.audiences) !== '["use","maintain"]' ||
              !data.documents || !data.routes || !data.overviews) {
            throw new Error("Invalid audience runtime map");
          }
          return data;
        });
    }
    return runtimePromise;
  }

  function getDocumentMetadata(runtimeMap) {
    const path = location.pathname;
    const destination = runtimeMap?.routes[path] || runtimeMap?.routes[path.replace(/index\.html$/, "")];
    const doc = runtimeMap?.documents[destination];
    const audiences = new Set(Array.isArray(doc?.audiences) ? doc.audiences.filter(a => VALID_AUDIENCES.has(a)) : []);
    const primary = audiences.has(doc?.primary) ? doc.primary : null;
    return {
      primary, audiences,
      isLanding: Boolean(doc?.is_landing) || path === "/" || path === "/index.html",
    };
  }

  function getStoredJourney() {
    try {
      const value = sessionStorage.getItem(STORAGE_KEY);
      return VALID_AUDIENCES.has(value) ? value : null;
    } catch { return null; }
  }

  function setStoredJourney(audience) {
    try {
      if (VALID_AUDIENCES.has(audience)) sessionStorage.setItem(STORAGE_KEY, audience);
    } catch { /* Storage may be unavailable; URL and history still work. */ }
  }

  function resolveAudienceWithMetadata(meta) {
    if (meta.isLanding) return null;
    const explicit = new URL(location.href).searchParams.get("audience");
    const recorded = history.state?.[HISTORY_KEY];
    const journey = recorded?.path === location.pathname && VALID_AUDIENCES.has(recorded.audience)
      ? recorded.audience : getStoredJourney();
    if (meta.audiences.has(explicit)) return explicit;
    if (meta.audiences.has(journey)) return journey;
    // A stored journey never creates membership for an unmapped/unclassified route.
    return meta.primary || null;
  }

  function applyAudience(audience) {
    const semanticAudience = VALID_AUDIENCES.has(audience) ? audience : "neutral";
    document.documentElement.dataset.audience = semanticAudience;
    document.querySelectorAll("[data-audience-switch]").forEach(el => {
      const selected = el.getAttribute("data-audience-switch") === audience;
      el.setAttribute("aria-pressed", String(selected));
      el.classList.toggle("is-active", selected);
    });
    const state = `${location.pathname}${location.search}${location.hash}:${semanticAudience}`;
    if (state !== lastState) {
      lastState = state;
      window.dispatchEvent(new CustomEvent(CHANGE_EVENT, { detail: { audience: semanticAudience } }));
    }
  }

  function recordAudience(audience) {
    setStoredJourney(audience);
    try {
      history.replaceState({ ...history.state, [HISTORY_KEY]: { path: location.pathname, audience } }, "");
    } catch { /* Browser navigation remains usable without writable history. */ }
  }

  async function applyCurrentAudience(generation = ++applyGeneration) {
    let map;
    try { map = await loadRuntimeMap(); } catch { /* Fail neutral if the projection cannot be read. */ }
    if (generation !== applyGeneration) return;
    const resolved = map ? resolveAudienceWithMetadata(getDocumentMetadata(map)) : null;
    recordAudience(resolved);
    applyAudience(resolved);
  }

  async function switchAudience(targetAudience) {
    if (!VALID_AUDIENCES.has(targetAudience)) return;
    const generation = ++applyGeneration;
    let map;
    try { map = await loadRuntimeMap(); } catch { return; }
    if (generation !== applyGeneration) return;
    const meta = getDocumentMetadata(map);
    if (!meta.isLanding && meta.audiences.has(targetAudience)) {
      const url = new URL(location.href);
      url.searchParams.set("audience", targetAudience);
      history.replaceState({ ...history.state }, "", url);
      recordAudience(targetAudience);
      applyAudience(targetAudience);
    } else {
      const overview = map.overviews[targetAudience];
      if (typeof overview !== "string" || !overview.startsWith("/") || overview.startsWith("//")) return;
      setStoredJourney(targetAudience);
      location.assign(overview);
    }
  }

  function handleNavigation() {
    void applyCurrentAudience(++applyGeneration);
  }

  function init() {
    if (initialized) return;
    initialized = true;
    document.addEventListener("click", event => {
      const switcher = event.target.closest?.("[data-audience-switch]");
      if (!switcher) return;
      event.preventDefault();
      void switchAudience(switcher.getAttribute("data-audience-switch"));
    });
    window.addEventListener("pageshow", handleNavigation);
    window.addEventListener("popstate", handleNavigation);
    const navigationDocument = window.document$;
    if (navigationDocument && typeof navigationDocument.subscribe === "function") {
      navigationDocument.subscribe(handleNavigation);
    }
    handleNavigation();
  }

  window.TemplatesAudienceContext = {
    STORAGE_KEY, CHANGE_EVENT, RUNTIME_MAP_URL,
    loadRuntimeMap, getDocumentMetadata, resolveAudienceWithMetadata,
    getStoredJourney, switchAudience, init,
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
  else init();
})();
