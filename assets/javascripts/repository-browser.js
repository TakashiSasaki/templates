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

  function clearSelection({ resetFrame = true } = {}) {
    if (selectedLink instanceof HTMLAnchorElement) {
      selectedLink.removeAttribute("aria-current");
    }
    selectedLink = null;
    selectedFileLabel.textContent = "Selected file";
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

  document.documentElement.classList.add("repository-browser-enhanced");
  setMobileMode("files");
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

  const handleViewportChange = () => syncInteractivity();
  if (typeof mobileViewport.addEventListener === "function") {
    mobileViewport.addEventListener("change", handleViewportChange);
  } else if (typeof mobileViewport.addListener === "function") {
    mobileViewport.addListener(handleViewportChange);
  }
})();
