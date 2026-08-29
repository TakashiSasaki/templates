(() => {
  "use strict";

  const browser = document.querySelector("[data-repository-browser]");
  if (!(browser instanceof HTMLElement)) {
    return;
  }

  const tree = browser.querySelector("[data-repository-tree]");
  const content = browser.querySelector("[data-repository-content]");
  const filesButton = browser.querySelector("[data-show-files]");
  const selectedFileLabel = browser.querySelector("[data-selected-file]");
  if (
    !(tree instanceof HTMLElement) ||
    !(content instanceof HTMLElement) ||
    !(filesButton instanceof HTMLButtonElement) ||
    !(selectedFileLabel instanceof HTMLElement)
  ) {
    return;
  }

  const frame = content.querySelector("iframe[name='repository-file-viewer']");
  const managedFrame =
    typeof HTMLIFrameElement !== "undefined" && frame instanceof HTMLIFrameElement
      ? frame
      : null;
  const browserHeader = tree.querySelector(".browser-header");
  const mobileToolbar = content.querySelector(".viewer-mobile-toolbar");
  const initialSrcdoc = managedFrame?.getAttribute("srcdoc") || "";
  const mobileViewport = window.matchMedia("(max-width: 800px)");
  const fileLinks = Array.from(
    tree.querySelectorAll("a[data-repository-file]")
  ).filter((link) => link instanceof HTMLAnchorElement);
  const linksByPath = new Map();
  for (const link of fileLinks) {
    const path = link.dataset.filePath;
    if (path && !linksByPath.has(path)) {
      linksByPath.set(path, link);
    }
  }

  let selectedLink = null;
  let appliedHash = null;
  let shareControls = null;
  let shareStatus = null;
  let shareButtons = [];

  function mobileMode() {
    return browser.dataset.mobileView === "content" ? "content" : "files";
  }

  function syncInteractivity() {
    if (!mobileViewport.matches) {
      tree.inert = false;
      content.inert = false;
      return;
    }

    // data-mobile-view is the preferred narrow-viewport pane. Keep it while
    // desktop shows both panes so rotating or resizing back to mobile restores
    // the user's prior Files/Content context instead of discarding it.
    const showingContent = mobileMode() === "content";
    tree.inert = showingContent;
    content.inert = !showingContent;
  }

  function setMobileMode(mode) {
    browser.dataset.mobileView = mode === "content" ? "content" : "files";
    syncInteractivity();
  }

  function selectedPathFromLocation() {
    if (!window.location.hash || window.location.hash === "#") {
      return null;
    }
    const params = new URLSearchParams(window.location.hash.slice(1));
    const path = params.get("file");
    return path || null;
  }

  function hashForPath(path) {
    const params = new URLSearchParams();
    params.set("file", path);
    return `#${params.toString()}`;
  }

  function viewerLinkForPath(path) {
    const url = new URL(window.location.href);
    url.hash = hashForPath(path);
    return url.href;
  }

  function sourceLinkForFile(link) {
    const row = link.parentElement;
    if (!(row instanceof HTMLElement)) {
      return null;
    }
    const source = row.querySelector("a.tree-source");
    return source instanceof HTMLAnchorElement ? source.href : null;
  }

  function openAncestorDirectories(link) {
    let current = link.parentElement;
    while (current && current !== tree) {
      if (
        typeof HTMLDetailsElement !== "undefined" &&
        current instanceof HTMLDetailsElement
      ) {
        current.open = true;
      }
      current = current.parentElement;
    }
  }

  function syncShareAvailability() {
    const available = selectedLink instanceof HTMLAnchorElement;
    for (const button of shareButtons) {
      button.disabled = !available;
    }
    if (!available && shareStatus instanceof HTMLElement) {
      shareStatus.textContent = "";
    }
  }

  function clearSelection({ resetFrame = true } = {}) {
    if (selectedLink instanceof HTMLAnchorElement) {
      selectedLink.removeAttribute("aria-current");
    }
    selectedLink = null;
    selectedFileLabel.textContent = "Selected file";
    syncShareAvailability();
    setMobileMode("files");

    if (resetFrame && managedFrame) {
      managedFrame.removeAttribute("src");
      managedFrame.setAttribute("srcdoc", initialSrcdoc);
    }
  }

  function selectLink(link, { navigateFrame = true, focusBackButton = false } = {}) {
    if (selectedLink instanceof HTMLAnchorElement && selectedLink !== link) {
      selectedLink.removeAttribute("aria-current");
    }
    selectedLink = link;
    selectedLink.setAttribute("aria-current", "true");
    selectedFileLabel.textContent =
      link.dataset.filePath || link.textContent?.trim() || "Selected file";
    openAncestorDirectories(link);
    syncShareAvailability();

    if (navigateFrame && managedFrame) {
      managedFrame.removeAttribute("srcdoc");
      managedFrame.setAttribute("src", link.href);
    }

    setMobileMode("content");
    if (focusBackButton && mobileViewport.matches) {
      window.requestAnimationFrame(() => {
        filesButton.focus({ preventScroll: true });
      });
    }
  }

  function syncFromLocation() {
    if (!managedFrame || window.location.hash === appliedHash) {
      return;
    }
    appliedHash = window.location.hash;
    const path = selectedPathFromLocation();
    if (path === null) {
      clearSelection();
      return;
    }
    const link = linksByPath.get(path);
    if (!(link instanceof HTMLAnchorElement)) {
      clearSelection();
      return;
    }
    selectLink(link, { navigateFrame: true, focusBackButton: false });
  }

  function pushFileLocation(path) {
    const nextHash = hashForPath(path);
    if (window.location.hash === nextHash) {
      appliedHash = nextHash;
      return;
    }
    window.history.pushState(null, "", nextHash);
    appliedHash = window.location.hash;
  }

  function copyWithFallback(value) {
    if (!document.body || typeof document.createElement !== "function") {
      throw new Error("clipboard fallback is unavailable");
    }
    const field = document.createElement("textarea");
    field.value = value;
    field.setAttribute("readonly", "");
    field.style.position = "fixed";
    field.style.opacity = "0";
    field.style.pointerEvents = "none";
    document.body.appendChild(field);
    field.focus();
    field.select();
    const copied = document.execCommand("copy");
    field.remove();
    if (!copied) {
      throw new Error("legacy clipboard copy failed");
    }
  }

  async function copyText(value) {
    if (
      window.isSecureContext &&
      typeof navigator !== "undefined" &&
      navigator.clipboard &&
      typeof navigator.clipboard.writeText === "function"
    ) {
      await navigator.clipboard.writeText(value);
      return;
    }
    copyWithFallback(value);
  }

  function copyValueFor(kind) {
    if (!(selectedLink instanceof HTMLAnchorElement)) {
      return null;
    }
    const path = selectedLink.dataset.filePath;
    if (!path) {
      return null;
    }
    if (kind === "path") {
      return path;
    }
    if (kind === "viewer") {
      return viewerLinkForPath(path);
    }
    if (kind === "source") {
      return sourceLinkForFile(selectedLink);
    }
    return null;
  }

  function syncShareLayout() {
    if (!(shareControls instanceof HTMLElement)) {
      return;
    }
    if (mobileViewport.matches && mobileToolbar instanceof HTMLElement) {
      if (shareControls.parentElement !== mobileToolbar) {
        mobileToolbar.appendChild(shareControls);
      }
      mobileToolbar.style.flexWrap = "wrap";
      selectedFileLabel.style.flex = "1 1 10rem";
      shareControls.style.marginTop = "0";
      shareControls.style.marginLeft = "auto";
      shareControls.style.maxWidth = "100%";
      return;
    }

    if (browserHeader instanceof HTMLElement && shareControls.parentElement !== browserHeader) {
      browserHeader.appendChild(shareControls);
    }
    shareControls.style.marginTop = ".6rem";
    shareControls.style.marginLeft = "0";
    shareControls.style.maxWidth = "100%";
  }

  function initializeSharing() {
    if (
      !(managedFrame instanceof HTMLIFrameElement) ||
      !(browserHeader instanceof HTMLElement) ||
      !(mobileToolbar instanceof HTMLElement) ||
      typeof document.createElement !== "function"
    ) {
      return;
    }

    shareControls = document.createElement("div");
    shareControls.setAttribute("data-repository-share", "");
    shareControls.setAttribute("aria-label", "Share selected file");
    shareControls.style.display = "flex";
    shareControls.style.flexWrap = "wrap";
    shareControls.style.alignItems = "center";
    shareControls.style.gap = ".35rem";

    const definitions = [
      ["path", "Copy path", "path"],
      ["viewer", "Copy viewer link", "viewer link"],
      ["source", "Copy immutable source link", "immutable source link"],
    ];
    shareButtons = definitions.map(([kind, label, statusName]) => {
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.copyRepository = kind;
      button.textContent = label;
      button.disabled = true;
      button.style.minHeight = "2.3rem";
      button.style.border = "1px solid color-mix(in srgb, CanvasText 24%, transparent)";
      button.style.borderRadius = ".45rem";
      button.style.padding = ".35rem .55rem";
      button.style.color = "inherit";
      button.style.background = "color-mix(in srgb, CanvasText 6%, Canvas)";
      button.style.font = "inherit";
      button.style.cursor = "pointer";
      button.addEventListener("click", async () => {
        const value = copyValueFor(kind);
        if (!value) {
          return;
        }
        button.disabled = true;
        try {
          await copyText(value);
          if (shareStatus instanceof HTMLElement) {
            shareStatus.textContent = `Copied ${statusName}`;
          }
        } catch (error) {
          console.warn(`Unable to copy repository ${statusName}`, error);
          if (shareStatus instanceof HTMLElement) {
            shareStatus.textContent = `Copy failed: ${statusName}`;
          }
        } finally {
          button.disabled = !(selectedLink instanceof HTMLAnchorElement);
        }
      });
      shareControls.appendChild(button);
      return button;
    });

    shareStatus = document.createElement("span");
    shareStatus.setAttribute("data-repository-share-status", "");
    shareStatus.setAttribute("aria-live", "polite");
    shareStatus.style.fontSize = ".74rem";
    shareStatus.style.minWidth = "8rem";
    shareControls.appendChild(shareStatus);
    syncShareAvailability();
    syncShareLayout();
  }

  document.documentElement.classList.add("repository-browser-enhanced");
  setMobileMode("files");
  initializeSharing();
  syncFromLocation();

  browser.addEventListener("click", (event) => {
    if (
      event.defaultPrevented ||
      event.button !== 0 ||
      event.metaKey ||
      event.ctrlKey ||
      event.shiftKey ||
      event.altKey
    ) {
      return;
    }

    const target = event.target;
    if (!(target instanceof Element)) {
      return;
    }

    const link = target.closest("a[data-repository-file]");
    if (!(link instanceof HTMLAnchorElement) || !browser.contains(link)) {
      return;
    }

    const path = link.dataset.filePath;
    if (!path || !managedFrame) {
      return;
    }

    event.preventDefault();
    selectLink(link, { navigateFrame: true, focusBackButton: true });
    pushFileLocation(path);
  });

  filesButton.addEventListener("click", () => {
    const focusTarget =
      selectedLink instanceof HTMLAnchorElement
        ? selectedLink
        : tree.querySelector("a[data-repository-file], summary, a, button");
    setMobileMode("files");
    if (mobileViewport.matches && focusTarget instanceof HTMLElement) {
      window.requestAnimationFrame(() => {
        focusTarget.focus({ preventScroll: true });
      });
    }
  });

  window.addEventListener("popstate", syncFromLocation);
  window.addEventListener("hashchange", syncFromLocation);

  const handleViewportChange = () => {
    syncInteractivity();
    syncShareLayout();
  };
  if (typeof mobileViewport.addEventListener === "function") {
    mobileViewport.addEventListener("change", handleViewportChange);
  } else if (typeof mobileViewport.addListener === "function") {
    mobileViewport.addListener(handleViewportChange);
  }
})();
