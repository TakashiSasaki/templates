(() => {
  const manifestHref = "/app.webmanifest";
  const themeColor = "#3f51b5";

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
