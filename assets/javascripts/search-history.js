/* Site-local search history integrated through Zensical's open Shadow DOM contract. */
(() => {
  "use strict";

  const SEARCH_INPUT_SELECTOR = 'input[role="combobox"]';
  const SEARCH_HISTORY_STORAGE_KEY = "templates.search-history.v1";
  const SEARCH_HISTORY_LIMIT = 10;
  const PENDING_ENTER_MAX_AGE_MS = 1000;
  const PENDING_ENTER_SESSION_KEY = "templates.search-history.pending-enter.v1";
  const PENDING_ENTER_SESSION_MAX_AGE_MS = 15000;
  const HISTORY_SECTION_SELECTOR = "[data-site-search-history]";
  const STRINGS = Object.freeze({
    en: Object.freeze({ heading: "Recent searches", clear: "Clear history" }),
    ja: Object.freeze({ heading: "最近の検索", clear: "履歴を消去" }),
  });

  const rootState = new WeakMap();
  const observedRoots = new WeakMap();
  let bodyObserver;

  const ZensicalSearchAdapter = Object.freeze({
    shadowRoots(body) {
      const roots = [];
      for (const host of body?.children || []) {
        if (host.shadowRoot) {
          roots.push(host.shadowRoot);
        }
      }
      return roots;
    },

    input(root) {
      const input = root.querySelector(SEARCH_INPUT_SELECTOR);
      return input instanceof HTMLInputElement ? input : undefined;
    },

    resultAnchors(root, section) {
      return Array.from(root.querySelectorAll("ol a[href]")).filter(
        (anchor) => !section.contains(anchor),
      );
    },

    isResultAnchor(root, section, target) {
      const anchor = target.closest("a[href]");
      return Boolean(
        anchor &&
          root.contains(anchor) &&
          !section.contains(anchor) &&
          anchor.closest("ol"),
      );
    },

    replayQuery(input, query) {
      const descriptor = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value");
      if (descriptor?.set) {
        descriptor.set.call(input, query);
      } else {
        input.value = query;
      }
      const inputEvent =
        typeof InputEvent === "function"
          ? new InputEvent("input", { bubbles: true, inputType: "insertText", data: query })
          : new Event("input", { bubbles: true });
      input.dispatchEvent(inputEvent);
    },
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
        if (result.length >= SEARCH_HISTORY_LIMIT) {
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
        JSON.stringify(history.slice(0, SEARCH_HISTORY_LIMIT)),
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
    ].slice(0, SEARCH_HISTORY_LIMIT);
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

  function currentStrings() {
    const language = (document.documentElement?.lang || "en").toLowerCase();
    return language.split("-", 1)[0] === "ja" ? STRINGS.ja : STRINGS.en;
  }

  function createHistoryStyle() {
    const style = document.createElement("style");
    style.dataset.siteSearchHistoryStyle = "true";
    style.textContent = `
      ${HISTORY_SECTION_SELECTOR}[hidden] { display: none !important; }
      ${HISTORY_SECTION_SELECTOR} {
        position: fixed;
        z-index: 3;
        box-sizing: border-box;
        max-height: min(48vh, 28rem);
        overflow: auto;
        border: 1px solid currentColor;
        border-radius: 0.45rem;
        background: var(--md-default-bg-color, Canvas);
        color: var(--md-default-fg-color, CanvasText);
        box-shadow: 0 0.5rem 1.4rem rgba(0, 0, 0, 0.18);
        font-family: system-ui, sans-serif;
        pointer-events: auto;
      }
      .site-search-history__meta {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.75rem;
        padding: 0.65rem 0.8rem 0.45rem;
        font-size: 0.75rem;
        line-height: 1.4;
      }
      .site-search-history__clear,
      .site-search-history__query-button {
        appearance: none;
        border: 0;
        background: transparent;
        color: inherit;
        font: inherit;
        cursor: pointer;
      }
      .site-search-history__clear {
        flex: 0 0 auto;
        padding: 0.15rem 0;
        text-decoration: underline;
        text-underline-offset: 0.12em;
      }
      .site-search-history__list {
        margin: 0;
        padding: 0 0 0.4rem;
        list-style: none;
      }
      .site-search-history__item { margin: 0; padding: 0; }
      .site-search-history__query-button {
        display: block;
        width: 100%;
        padding: 0.55rem 0.8rem;
        text-align: start;
        overflow-wrap: anywhere;
      }
      .site-search-history__query-button:hover,
      .site-search-history__query-button:focus-visible {
        background: color-mix(in srgb, currentColor 10%, transparent);
      }
      .site-search-history__clear:focus-visible,
      .site-search-history__query-button:focus-visible {
        outline: 0.125rem solid currentColor;
        outline-offset: -0.125rem;
      }
    `;
    return style;
  }

  function createHistorySection() {
    const section = document.createElement("section");
    section.dataset.siteSearchHistory = "true";
    section.hidden = true;

    const meta = document.createElement("div");
    meta.className = "site-search-history__meta";

    const heading = document.createElement("span");
    heading.dataset.siteSearchHistoryHeading = "true";
    meta.appendChild(heading);

    const clear = document.createElement("button");
    clear.type = "button";
    clear.className = "site-search-history__clear";
    clear.dataset.siteSearchHistoryClear = "true";
    meta.appendChild(clear);

    const list = document.createElement("ol");
    list.className = "site-search-history__list";
    list.setAttribute("role", "list");
    list.dataset.siteSearchHistoryList = "true";

    section.append(meta, list);
    return section;
  }

  function searchInputIsInteractive(input) {
    if (!input.isConnected) {
      return false;
    }
    const inputStyle = window.getComputedStyle(input);
    if (inputStyle.pointerEvents === "none") {
      return false;
    }
    for (let element = input; element; element = element.parentElement) {
      const style = window.getComputedStyle(element);
      if (
        style.display === "none" ||
        style.visibility === "hidden" ||
        style.visibility === "collapse" ||
        Number.parseFloat(style.opacity) === 0
      ) {
        return false;
      }
    }
    const rect = input.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  }

  function positionSection(state) {
    const controls = state.input.parentElement?.parentElement;
    const rect = (controls || state.input).getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) {
      return false;
    }
    const viewportPadding = 8;
    const left = Math.max(viewportPadding, rect.left);
    const right = Math.min(window.innerWidth - viewportPadding, rect.right);
    state.section.style.left = `${left}px`;
    state.section.style.top = `${Math.min(window.innerHeight - viewportPadding, rect.bottom + 8)}px`;
    state.section.style.width = `${Math.max(0, right - left)}px`;
    return true;
  }

  function renderHistory(state) {
    if (!state.section.isConnected) {
      return;
    }
    if (!state.input.isConnected) {
      state.section.hidden = true;
      return;
    }
    const strings = currentStrings();
    const history = loadHistory();
    const visible =
      searchInputIsInteractive(state.input) &&
      normalizeQuery(state.input.value) === "" &&
      history.length > 0 &&
      positionSection(state);
    state.section.hidden = !visible;
    if (!visible) {
      return;
    }

    const heading = state.section.querySelector("[data-site-search-history-heading]");
    const clear = state.section.querySelector("[data-site-search-history-clear]");
    const list = state.section.querySelector("[data-site-search-history-list]");
    if (!(heading instanceof HTMLElement) || !(clear instanceof HTMLButtonElement) || !list) {
      return;
    }
    state.section.setAttribute("aria-label", strings.heading);
    heading.textContent = strings.heading;
    clear.textContent = strings.clear;

    const existingQueries = Array.from(
      list.querySelectorAll("[data-site-search-history-query]"),
    ).map((button) => normalizeQuery(button.textContent || ""));
    if (
      existingQueries.length === history.length &&
      existingQueries.every((query, index) => query === history[index])
    ) {
      return;
    }

    list.replaceChildren();
    for (const query of history) {
      const item = document.createElement("li");
      item.className = "site-search-history__item";
      const button = document.createElement("button");
      button.type = "button";
      button.className = "site-search-history__query-button";
      button.dataset.siteSearchHistoryQuery = query;
      button.textContent = query;
      button.addEventListener("click", (event) => replayQuery(event, state, button));
      item.appendChild(button);
      list.appendChild(item);
    }
  }

  function renderAll() {
    for (const root of ZensicalSearchAdapter.shadowRoots(document.body)) {
      const state = rootState.get(root);
      if (state) {
        renderHistory(state);
      }
    }
  }

  function navigationKey(value) {
    try {
      const url = new URL(value, window.location.href);
      url.searchParams.delete("h");
      return `${url.origin}${url.pathname}${url.search}${url.hash}`;
    } catch (_error) {
      return "";
    }
  }

  function cancelPendingEnter(state) {
    const pending = state?.pendingEnter;
    if (!pending) {
      return;
    }
    state.pendingEnter = undefined;
    if (pending.timer !== undefined) {
      window.clearTimeout(pending.timer);
    }
  }

  function stagePendingEnter(state) {
    cancelPendingEnter(state);
    const query = normalizeQuery(state.input.value);
    if (!query) {
      return;
    }
    const destinations = new Set();
    for (const anchor of ZensicalSearchAdapter.resultAnchors(state.root, state.section)) {
      const key = navigationKey(anchor.href);
      if (key) {
        destinations.add(key);
      }
    }
    if (!destinations.size) {
      return;
    }
    const maxAgeMs = hasNavigationApi
      ? PENDING_ENTER_MAX_AGE_MS
      : PENDING_ENTER_SESSION_MAX_AGE_MS;
    const pending = {
      query,
      destinations,
      expiresAt: Date.now() + maxAgeMs,
      timer: undefined,
    };
    pending.timer = window.setTimeout(() => {
      if (state.pendingEnter === pending) {
        state.pendingEnter = undefined;
      }
    }, maxAgeMs);
    state.pendingEnter = pending;
  }

  function confirmPendingEnterNavigation(destination) {
    const key = navigationKey(destination);
    if (!key) {
      return;
    }
    for (const root of ZensicalSearchAdapter.shadowRoots(document.body)) {
      const state = rootState.get(root);
      const pending = state?.pendingEnter;
      if (!state || !pending) {
        continue;
      }
      if (Date.now() > pending.expiresAt || !pending.destinations.has(key)) {
        cancelPendingEnter(state);
        continue;
      }
      const query = pending.query;
      cancelPendingEnter(state);
      rememberQuery(query);
      renderHistory(state);
    }
  }

  function storePendingEnterForNextDocument() {
    let stored = false;
    for (const root of ZensicalSearchAdapter.shadowRoots(document.body)) {
      const state = rootState.get(root);
      const pending = state?.pendingEnter;
      if (!state || !pending || Date.now() > pending.expiresAt) {
        continue;
      }
      try {
        window.sessionStorage.setItem(
          PENDING_ENTER_SESSION_KEY,
          JSON.stringify({
            query: pending.query,
            destinations: Array.from(pending.destinations),
            expiresAt: pending.expiresAt,
          }),
        );
        stored = true;
      } catch (_error) {
        stored = false;
      }
      cancelPendingEnter(state);
      break;
    }
    if (!stored) {
      try {
        window.sessionStorage.removeItem(PENDING_ENTER_SESSION_KEY);
      } catch (_error) {
        return;
      }
    }
  }

  function confirmStoredPendingEnterNavigation() {
    let raw;
    try {
      raw = window.sessionStorage.getItem(PENDING_ENTER_SESSION_KEY);
      window.sessionStorage.removeItem(PENDING_ENTER_SESSION_KEY);
    } catch (_error) {
      return false;
    }
    if (!raw) {
      return false;
    }
    let pending;
    try {
      pending = JSON.parse(raw);
    } catch (_error) {
      return false;
    }
    if (
      !pending ||
      typeof pending.query !== "string" ||
      !Array.isArray(pending.destinations) ||
      !Number.isFinite(pending.expiresAt) ||
      Date.now() > pending.expiresAt
    ) {
      return false;
    }
    const key = navigationKey(window.location.href);
    if (!key || !pending.destinations.includes(key)) {
      return false;
    }
    rememberQuery(pending.query);
    return true;
  }

  function replayQuery(event, state, control) {
    event.preventDefault();
    event.stopPropagation();
    cancelPendingEnter(state);
    const query = normalizeQuery(control.dataset.siteSearchHistoryQuery || "");
    if (!query) {
      return;
    }
    rememberQuery(query);
    ZensicalSearchAdapter.replayQuery(state.input, query);
    state.input.focus({ preventScroll: true });
    renderHistory(state);
  }

  function bindRoot(root, input) {
    let state = rootState.get(root);
    if (!state) {
      const style = createHistoryStyle();
      const section = createHistorySection();
      root.append(style, section);
      state = { root, input, style, section, pendingEnter: undefined };
      rootState.set(root, state);

      const clearControl = section.querySelector("[data-site-search-history-clear]");
      if (clearControl instanceof HTMLButtonElement) {
        clearControl.addEventListener("click", (event) => {
          event.preventDefault();
          event.stopPropagation();
          const current = rootState.get(root);
          if (!current) {
            return;
          }
          cancelPendingEnter(current);
          clearHistory();
          current.input.focus({ preventScroll: true });
          renderHistory(current);
        });
      }

      root.addEventListener(
        "pointerdown",
        () => {
          const current = rootState.get(root);
          if (current) {
            cancelPendingEnter(current);
          }
        },
        true,
      );

      root.addEventListener("click", (event) => {
        const target = event.target;
        if (!(target instanceof Element)) {
          return;
        }
        const current = rootState.get(root);
        if (!current) {
          return;
        }
        const historyControl = target.closest("[data-site-search-history-query]");
        if (historyControl instanceof HTMLButtonElement && current.section.contains(historyControl)) {
          replayQuery(event, current, historyControl);
          return;
        }
        if (ZensicalSearchAdapter.isResultAnchor(root, current.section, target)) {
          cancelPendingEnter(current);
          rememberQuery(current.input.value);
          queueMicrotask(() => {
            const latest = rootState.get(root);
            if (!latest) {
              return;
            }
            if (!searchInputIsInteractive(latest.input)) {
              latest.input.blur();
            }
            renderHistory(latest);
          });
        }
      });

      root.addEventListener(
        "keydown",
        (event) => {
          const current = rootState.get(root);
          if (!current) {
            return;
          }
          if (
            event.key !== "Enter" ||
            event.isComposing ||
            root.activeElement !== current.input ||
            normalizeQuery(current.input.value) === ""
          ) {
            cancelPendingEnter(current);
            return;
          }
          stagePendingEnter(current);
        },
        true,
      );
    }

    if (!state.style.isConnected) {
      root.appendChild(state.style);
    }
    if (!state.section.isConnected) {
      root.appendChild(state.section);
    }
    if (state.input !== input) {
      cancelPendingEnter(state);
      state.input = input;
    }
    if (input.dataset.siteSearchHistoryEnhanced !== "true") {
      input.dataset.siteSearchHistoryEnhanced = "true";
      input.addEventListener("input", () => {
        const current = rootState.get(root);
        if (current?.input === input) {
          cancelPendingEnter(current);
          renderHistory(current);
        }
      });
      input.addEventListener("focus", () => {
        const current = rootState.get(root);
        if (current?.input === input) {
          renderHistory(current);
        }
      });
      input.addEventListener("blur", () => {
        const current = rootState.get(root);
        if (current?.input === input) {
          queueMicrotask(() => {
            if (!current.section.contains(root.activeElement)) {
              renderHistory(current);
            }
          });
        }
      });
    }
    renderHistory(state);
  }

  function enhanceShadowRoot(root) {
    const input = ZensicalSearchAdapter.input(root);
    if (!input) {
      return false;
    }
    bindRoot(root, input);
    return true;
  }

  function mutationTargetsSiteOwnedNode(state, record) {
    const target = record.target;
    return (
      target === state.style ||
      target === state.section ||
      (target instanceof Node && state.section.contains(target))
    );
  }

  function observeShadowRoot(root) {
    if (observedRoots.has(root)) {
      enhanceShadowRoot(root);
      return;
    }
    const observer = new MutationObserver((records) => {
      const state = rootState.get(root);
      const input = ZensicalSearchAdapter.input(root);
      if (
        input &&
        (!state ||
          state.input !== input ||
          !state.style.isConnected ||
          !state.section.isConnected)
      ) {
        bindRoot(root, input);
        return;
      }
      if (state && records.some((record) => !mutationTargetsSiteOwnedNode(state, record))) {
        renderHistory(state);
      }
    });
    observer.observe(root, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ["class"],
    });
    observedRoots.set(root, observer);
    enhanceShadowRoot(root);
  }

  function scanSearchRoots() {
    if (!document.body) {
      return;
    }
    for (const root of ZensicalSearchAdapter.shadowRoots(document.body)) {
      observeShadowRoot(root);
    }
    renderAll();
  }

  function observeBody() {
    if (!document.body) {
      return;
    }
    if (!bodyObserver) {
      bodyObserver = new MutationObserver((records) => {
        for (const record of records) {
          for (const node of record.addedNodes) {
            if (node instanceof Element && node.shadowRoot) {
              observeShadowRoot(node.shadowRoot);
            }
          }
        }
      });
    } else {
      bodyObserver.disconnect();
    }
    bodyObserver.observe(document.body, { childList: true });
  }

  function initializeSearchHistory() {
    observeBody();
    scanSearchRoots();
  }

  const hasNavigationApi = Boolean(
    window.navigation && typeof window.navigation.addEventListener === "function",
  );
  if (hasNavigationApi) {
    window.navigation.addEventListener("navigate", (event) => {
      confirmPendingEnterNavigation(event.destination?.url || "");
    });
  } else {
    confirmStoredPendingEnterNavigation();
    window.addEventListener("hashchange", () => {
      confirmPendingEnterNavigation(window.location.href);
    });
    window.addEventListener("pagehide", storePendingEnterForNextDocument);
  }

  initializeSearchHistory();
  window.addEventListener("pageshow", initializeSearchHistory);
  window.addEventListener("popstate", () => {
    if (!hasNavigationApi) {
      confirmPendingEnterNavigation(window.location.href);
    }
    initializeSearchHistory();
  });
  window.addEventListener("resize", renderAll, { passive: true });
  window.addEventListener("storage", (event) => {
    if (event.key === SEARCH_HISTORY_STORAGE_KEY || event.key === null) {
      renderAll();
    }
  });
  const navigationDocument = window.document$;
  if (navigationDocument && typeof navigationDocument.subscribe === "function") {
    navigationDocument.subscribe(() => {
      if (!hasNavigationApi) {
        confirmPendingEnterNavigation(window.location.href);
      }
      initializeSearchHistory();
    });
  }
})();
