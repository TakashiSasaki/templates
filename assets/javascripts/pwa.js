(() => {
  const manifestHref = "/app.webmanifest";
  const themeColor = "#3f51b5";
  const freshnessStatusId = "templates-freshness-status";

  function showCachedUnverifiedStatus() {
    let status = document.getElementById(freshnessStatusId);
    if (!status) {
      status = document.createElement("aside");
      status.id = freshnessStatusId;
      status.className = "freshness-status freshness-status--cached";
      status.setAttribute("role", "status");
      status.setAttribute("aria-live", "polite");
      document.body.prepend(status);
    }
    status.dataset.freshnessState = "cached-unverified";
    status.replaceChildren();
    const label = document.createElement("strong");
    label.textContent = "Saved copy.";
    status.append(label, " The latest version could not be verified.");
  }

  function clearFreshnessStatus() {
    document.getElementById(freshnessStatusId)?.remove();
  }

  function applyFreshnessState(state) {
    if (state === "cached-unverified") {
      showCachedUnverifiedStatus();
      return true;
    }
    if (state === "verified-current") {
      clearFreshnessStatus();
      return true;
    }
    return false;
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

  if (!window.isSecureContext || !("serviceWorker" in navigator)) {
    return;
  }

  navigator.serviceWorker.addEventListener("message", (event) => {
    if (event.data?.type !== "templates:freshness-state") {
      return;
    }
    const applied = applyFreshnessState(event.data.state);
    const acknowledgementPort = event.ports?.[0];
    if (applied && acknowledgementPort) {
      acknowledgementPort.postMessage({
        type: "templates:freshness-state-applied",
        state: event.data.state,
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
