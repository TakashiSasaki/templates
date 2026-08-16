(() => {
  const manifestHref = "/app.webmanifest";
  const themeColor = "#3f51b5";
  const freshnessStatusId = "templates-freshness-status";
  let pendingDocumentCommit = null;
  let workerInstanceId = null;
  let lastCommitGeneration = 0;
  let lastFreshnessGeneration = 0;
  let preserveInitialEmbeddedCachedCommit =
    document.documentElement?.dataset.templatesCachedFallback === "true" ||
    ["checking", "cached-unverified"].includes(
      document.getElementById(freshnessStatusId)?.dataset.freshnessState
    );

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

  function showFreshnessStatus(state) {
    const status = ensureFreshnessStatus();
    if (!status) {
      return false;
    }
    status.className = `freshness-status freshness-status--${state}`;
    status.dataset.freshnessState = state;
    status.replaceChildren();

    const label = document.createElement("strong");
    if (state === "checking") {
      label.textContent = "Saved copy.";
      status.append(label, " Checking for the latest version…");
      return true;
    }
    if (state === "cached-unverified") {
      label.textContent = "Saved copy.";
      status.append(label, " The latest version could not be verified.");
      return true;
    }
    if (state === "update-available") {
      label.textContent = "Update available.";
      status.append(label, " The published page changed. ");
      const reload = document.createElement("button");
      reload.type = "button";
      reload.className = "freshness-status__reload";
      reload.textContent = "Reload";
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

  function applyFreshnessState(data) {
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
    return showFreshnessStatus(data.state);
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

  if (!window.isSecureContext || !("serviceWorker" in navigator)) {
    return;
  }

  function requestCurrentFreshnessState() {
    const controller = navigator.serviceWorker.controller;
    if (!controller) {
      return;
    }
    controller.postMessage({
      type: "templates:get-current-freshness-state",
      url: window.location.href,
    });
  }

  navigator.serviceWorker.addEventListener("controllerchange", () => {
    resetWorkerOrdering();
    requestCurrentFreshnessState();
  });

  navigator.serviceWorker.addEventListener("message", (event) => {
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

    const applied = applyFreshnessState(data);
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