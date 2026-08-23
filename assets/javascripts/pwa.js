(() => {
  const manifestHref = "/app.webmanifest";
  const themeColor = "#3f51b5";
  const freshnessStatusId = "templates-freshness-status";
  const siteChromeLocalesHref = "/site-chrome-locales.json";
  const pwaFreshnessFields = Object.freeze([
    "saved_copy",
    "checking",
    "unverified",
    "update_available",
    "published_changed",
    "reload",
    "offline_unavailable",
  ]);
  let siteChromeLocalesPromise = null;
  let pendingDocumentCommit = null;
  let workerInstanceId = null;
  let lastCommitGeneration = 0;
  let lastFreshnessGeneration = 0;
  let preserveInitialEmbeddedCachedCommit =
    document.documentElement?.dataset.templatesCachedFallback === "true" ||
    ["checking", "cached-unverified", "update-available"].includes(
      document.getElementById(freshnessStatusId)?.dataset.freshnessState
    );

  function parseSiteChromeLocales(value) {
    if (
      !value ||
      typeof value !== "object" ||
      Array.isArray(value) ||
      value.schema_version !== 1 ||
      value.canonical_language !== "en" ||
      !Array.isArray(value.locales) ||
      value.locales.length === 0
    ) {
      throw new Error("invalid Site chrome locale root");
    }
    const locales = new Map();
    for (const locale of value.locales) {
      if (
        !locale ||
        typeof locale !== "object" ||
        Array.isArray(locale) ||
        typeof locale.language !== "string" ||
        !/^[a-z]{2,3}(?:-[a-z0-9]{2,8})*$/.test(locale.language) ||
        !locale.pwa_freshness ||
        typeof locale.pwa_freshness !== "object" ||
        Array.isArray(locale.pwa_freshness) ||
        Object.keys(locale.pwa_freshness).length !== pwaFreshnessFields.length ||
        pwaFreshnessFields.some(
          (field) =>
            typeof locale.pwa_freshness[field] !== "string" ||
            locale.pwa_freshness[field].trim().length === 0
        )
      ) {
        throw new Error("invalid Site chrome locale entry");
      }
      if (
        Object.keys(locale.pwa_freshness).some(
          (field) => !pwaFreshnessFields.includes(field)
        ) ||
        locales.has(locale.language)
      ) {
        throw new Error("ambiguous Site chrome locale entry");
      }
      locales.set(locale.language, Object.freeze({ ...locale.pwa_freshness }));
    }
    if (!locales.has(value.canonical_language)) {
      throw new Error("missing canonical Site chrome locale");
    }
    return Object.freeze({
      canonicalLanguage: value.canonical_language,
      locales,
    });
  }

  async function loadSiteChromeLocales() {
    if (!siteChromeLocalesPromise) {
      siteChromeLocalesPromise = fetch(siteChromeLocalesHref, { cache: "no-cache" })
        .then(async (response) => {
          if (!response.ok) {
            throw new Error(`Site chrome locale request failed: ${response.status}`);
          }
          return parseSiteChromeLocales(await response.json());
        })
        .catch((error) => {
          siteChromeLocalesPromise = null;
          console.warn("PWA chrome locale load failed", error);
          return null;
        });
    }
    return await siteChromeLocalesPromise;
  }

  function pwaFreshnessStrings(model, language) {
    if (!model || typeof language !== "string") {
      return null;
    }
    const exact = model.locales.get(language);
    if (exact) {
      return exact;
    }
    const primary = language.split("-", 1)[0];
    return (
      model.locales.get(primary) ||
      model.locales.get(model.canonicalLanguage) ||
      null
    );
  }

  async function currentPwaFreshnessStrings() {
    const model = await loadSiteChromeLocales();
    return pwaFreshnessStrings(model, document.documentElement?.lang || "");
  }

  function normalizedDocumentUrl(url) {
    try {
      const normalized = new URL(url, window.location.href);
      normalized.hash = "";
      return normalized.href;
    } catch (error) {
      return null;
    }
  }

  function ensureFreshnessStatus() {
    let status = document.getElementById(freshnessStatusId);
    if (!status) {
      status = document.createElement("aside");
      status.id = freshnessStatusId;
      status.setAttribute("role", "status");
      status.setAttribute("aria-live", "polite");
      const target = document.body || document.documentElement;
      if (!target) {
        return null;
      }
      target.prepend(status);
    }
    return status;
  }

  async function showFreshnessStatus(state) {
    const strings = await currentPwaFreshnessStrings();
    if (!strings) {
      return false;
    }
    const status = ensureFreshnessStatus();
    if (!status) {
      return false;
    }
    status.className = `freshness-status freshness-status--${state}`;
    status.dataset.freshnessState = state;
    status.replaceChildren();

    const label = document.createElement("strong");
    if (state === "checking") {
      label.textContent = strings.saved_copy;
      status.append(label, ` ${strings.checking}`);
      return true;
    }
    if (state === "cached-unverified") {
      label.textContent = strings.saved_copy;
      status.append(label, ` ${strings.unverified}`);
      return true;
    }
    if (state === "update-available") {
      label.textContent = strings.update_available;
      status.append(label, ` ${strings.published_changed} `);
      const reload = document.createElement("button");
      reload.type = "button";
      reload.className = "freshness-status__reload";
      reload.textContent = strings.reload;
      reload.addEventListener("click", () => window.location.reload());
      status.append(reload);
      return true;
    }
    return false;
  }

  function clearFreshnessStatus() {
    document.getElementById(freshnessStatusId)?.remove();
  }

  function clearInitialCachedMarker() {
    if (document.documentElement) {
      delete document.documentElement.dataset.templatesCachedFallback;
      delete document.documentElement.dataset.templatesFreshnessState;
    }
    preserveInitialEmbeddedCachedCommit = false;
  }

  function resetWorkerOrdering(nextWorkerInstanceId = null) {
    workerInstanceId = nextWorkerInstanceId;
    pendingDocumentCommit = null;
    lastCommitGeneration = 0;
    lastFreshnessGeneration = 0;
  }

  function adoptWorkerInstance(nextWorkerInstanceId) {
    if (
      typeof nextWorkerInstanceId !== "string" ||
      nextWorkerInstanceId.length === 0
    ) {
      return false;
    }
    if (workerInstanceId !== nextWorkerInstanceId) {
      resetWorkerOrdering(nextWorkerInstanceId);
    }
    return true;
  }

  function acceptGeneration(generation, current) {
    return (
      Number.isSafeInteger(generation) &&
      generation > 0 &&
      generation >= current
    );
  }

  function setPendingDocumentCommit(url, representation, generation) {
    const normalizedUrl = normalizedDocumentUrl(url);
    if (
      !normalizedUrl ||
      !acceptGeneration(generation, lastCommitGeneration)
    ) {
      return false;
    }
    lastCommitGeneration = generation;
    pendingDocumentCommit = {
      url: normalizedUrl,
      representation,
      generation,
    };
    return true;
  }

  async function applyFreshnessState(data) {
    const normalizedUrl = normalizedDocumentUrl(data.url);
    if (!normalizedUrl) {
      return false;
    }
    if (
      data.awaitingCommit !== true &&
      normalizedUrl !== normalizedDocumentUrl(window.location.href)
    ) {
      return false;
    }
    if (
      !acceptGeneration(data.requestGeneration, lastFreshnessGeneration)
    ) {
      return false;
    }
    lastFreshnessGeneration = data.requestGeneration;

    if (data.state === "verified-current") {
      const pending = pendingDocumentCommit;
      if (
        pending &&
        pending.representation === "cached" &&
        pending.url === normalizedUrl &&
        pending.generation === data.requestGeneration
      ) {
        return true;
      }
      pendingDocumentCommit = null;
      clearInitialCachedMarker();
      clearFreshnessStatus();
      return true;
    }
    if (
      data.awaitingCommit === true &&
      (data.state === "checking" || data.state === "cached-unverified")
    ) {
      if (
        !setPendingDocumentCommit(
          data.url,
          "cached",
          data.requestGeneration
        )
      ) {
        return false;
      }
    }
    return await showFreshnessStatus(data.state);
  }

  function handleCommittedDocument() {
    const committedUrl = normalizedDocumentUrl(window.location.href);
    const pending = pendingDocumentCommit;
    if (pending && committedUrl === pending.url) {
      pendingDocumentCommit = null;
      clearInitialCachedMarker();
      if (pending.representation === "cached") {
        requestCurrentFreshnessState();
        return;
      }
      lastFreshnessGeneration = Math.max(
        lastFreshnessGeneration,
        pending.generation
      );
      clearFreshnessStatus();
      requestCurrentFreshnessState();
      return;
    }

    if (pending && committedUrl !== pending.url) {
      pendingDocumentCommit = null;
      clearInitialCachedMarker();
      clearFreshnessStatus();
      requestCurrentFreshnessState();
      return;
    }

    const embeddedStatus = document.getElementById(freshnessStatusId);
    if (
      !pending &&
      preserveInitialEmbeddedCachedCommit &&
      ["checking", "cached-unverified", "update-available"].includes(
        embeddedStatus?.dataset.freshnessState
      )
    ) {
      clearInitialCachedMarker();
      requestCurrentFreshnessState();
      return;
    }

    pendingDocumentCommit = null;
    clearInitialCachedMarker();
  }

  if (!document.querySelector('link[rel="manifest"]')) {
    const manifest = document.createElement("link");
    manifest.rel = "manifest";
    manifest.href = manifestHref;
    document.head.appendChild(manifest);
  }

  if (!document.querySelector('meta[name="theme-color"]')) {
    const theme = document.createElement("meta");
    theme.name = "theme-color";
    theme.content = themeColor;
    document.head.appendChild(theme);
  }

  const documentObservable =
    typeof document$ !== "undefined" ? document$ : globalThis.document$;
  if (documentObservable && typeof documentObservable.subscribe === "function") {
    documentObservable.subscribe(handleCommittedDocument);
  }

  void loadSiteChromeLocales();

  if (!window.isSecureContext || !("serviceWorker" in navigator)) {
    return;
  }

  function requestCurrentFreshnessState() {
    const controller = navigator.serviceWorker?.controller;
    if (!controller) {
      return;
    }
    const currentState = document.getElementById(freshnessStatusId)?.dataset.freshnessState;
    controller.postMessage({
      type: "templates:get-current-freshness-state",
      url: window.location.href,
      currentState: typeof currentState === "string" ? currentState : null,
    });
  }

  navigator.serviceWorker.addEventListener("controllerchange", () => {
    resetWorkerOrdering();
    requestCurrentFreshnessState();
  });

  navigator.serviceWorker.addEventListener("message", async (event) => {
    const data = event.data;
    const controller = navigator.serviceWorker.controller;
    if (
      controller &&
      event.source &&
      event.source !== controller
    ) {
      return;
    }
    if (
      data?.type !== "templates:document-commit" &&
      data?.type !== "templates:freshness-state"
    ) {
      return;
    }
    if (!adoptWorkerInstance(data.workerInstanceId)) {
      return;
    }

    if (data.type === "templates:document-commit") {
      if (data.representation !== "network") {
        return;
      }
      setPendingDocumentCommit(
        data.url,
        "network",
        data.requestGeneration
      );
      return;
    }

    const applied = await applyFreshnessState(data);
    const acknowledgementPort = event.ports?.[0];
    if (applied && acknowledgementPort) {
      acknowledgementPort.postMessage({
        type: "templates:freshness-state-applied",
        state: data.state,
        requestGeneration: data.requestGeneration,
        workerInstanceId: data.workerInstanceId,
      });
    }
  });

  requestCurrentFreshnessState();

  const register = async () => {
    let registration;
    try {
      registration = await navigator.serviceWorker.register("/service-worker.js", {
        scope: "/",
        updateViaCache: "none",
      });
    } catch (error) {
      console.warn("Service worker registration failed", error);
      return;
    }

    if (!registration.active) {
      return;
    }

    requestCurrentFreshnessState();
    try {
      await registration.update();
    } catch (error) {
      console.warn("Service worker update check failed", error);
    }
  };

  if (document.readyState === "complete") {
    register();
  } else {
    window.addEventListener("load", register, { once: true });
  }
})();