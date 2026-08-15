(() => {
  const manifestHref = "/app.webmanifest";
  const themeColor = "#3f51b5";
  const freshnessStatusId = "templates-freshness-status";
  let pendingDocumentCommit = null;
  let lastCommitGeneration = 0;
  let preserveInitialEmbeddedCachedCommit =
    document.documentElement?.dataset.templatesCachedFallback === "true" ||
    document.getElementById(freshnessStatusId)?.dataset.freshnessState ===
      "cached-unverified";

  function normalizedDocumentUrl(url) {
    try {
      const normalized = new URL(url, window.location.href);
      normalized.hash = "";
      return normalized.href;
    } catch (error) {
      return null;
    }
  }

  function showCachedUnverifiedStatus() {
    let status = document.getElementById(freshnessStatusId);
    if (!status) {
      status = document.createElement("aside");
      status.id = freshnessStatusId;
      status.className = "freshness-status freshness-status--cached";
      status.setAttribute("role", "status");
      status.setAttribute("aria-live", "polite");
      const target = document.body || document.documentElement;
      if (!target) {
        return false;
      }
      target.prepend(status);
    }
    status.dataset.freshnessState = "cached-unverified";
    status.replaceChildren();
    const label = document.createElement("strong");
    label.textContent = "Saved copy.";
    status.append(label, " The latest version could not be verified.");
    return true;
  }

  function clearFreshnessStatus() {
    document.getElementById(freshnessStatusId)?.remove();
  }

  function clearInitialCachedMarker() {
    if (document.documentElement) {
      delete document.documentElement.dataset.templatesCachedFallback;
    }
    preserveInitialEmbeddedCachedCommit = false;
  }

  function setPendingDocumentCommit(url, representation, generation) {
    const normalizedUrl = normalizedDocumentUrl(url);
    if (!normalizedUrl || !Number.isSafeInteger(generation) || generation <= 0) {
      return false;
    }
    if (generation < lastCommitGeneration) {
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

  function applyCachedFreshnessState(url, generation) {
    if (!setPendingDocumentCommit(url, "cached", generation)) {
      return false;
    }
    return showCachedUnverifiedStatus();
  }

  function handleCommittedDocument() {
    const committedUrl = normalizedDocumentUrl(window.location.href);
    const pending = pendingDocumentCommit;
    if (pending && committedUrl === pending.url) {
      pendingDocumentCommit = null;
      clearInitialCachedMarker();
      if (pending.representation === "cached") {
        return;
      }
      clearFreshnessStatus();
      return;
    }

    const embeddedStatus = document.getElementById(freshnessStatusId);
    if (
      !pending &&
      preserveInitialEmbeddedCachedCommit &&
      embeddedStatus?.dataset.freshnessState === "cached-unverified"
    ) {
      clearInitialCachedMarker();
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

  navigator.serviceWorker.addEventListener("controllerchange", () => {
    lastCommitGeneration = 0;
  });

  navigator.serviceWorker.addEventListener("message", (event) => {
    const data = event.data;
    if (data?.type === "templates:document-commit") {
      if (data.representation !== "network") {
        return;
      }
      setPendingDocumentCommit(data.url, "network", data.requestGeneration);
      return;
    }

    if (
      data?.type !== "templates:freshness-state" ||
      data.state !== "cached-unverified"
    ) {
      return;
    }
    const applied = applyCachedFreshnessState(data.url, data.requestGeneration);
    const acknowledgementPort = event.ports?.[0];
    if (applied && acknowledgementPort) {
      acknowledgementPort.postMessage({
        type: "templates:freshness-state-applied",
        state: data.state,
        requestGeneration: data.requestGeneration,
      });
    }
  });

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
