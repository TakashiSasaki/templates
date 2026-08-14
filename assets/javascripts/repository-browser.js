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

  const mobileViewport = window.matchMedia("(max-width: 800px)");
  let selectedLink = null;

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

  document.documentElement.classList.add("repository-browser-enhanced");
  setMobileMode("files");

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

    if (selectedLink instanceof HTMLAnchorElement && selectedLink !== link) {
      selectedLink.removeAttribute("aria-current");
    }
    selectedLink = link;
    selectedLink.setAttribute("aria-current", "true");
    selectedFileLabel.textContent =
      link.dataset.filePath || link.textContent?.trim() || "Selected file";

    setMobileMode("content");
    if (mobileViewport.matches) {
      window.requestAnimationFrame(() => {
        filesButton.focus({ preventScroll: true });
      });
    }
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

  const handleViewportChange = () => syncInteractivity();
  if (typeof mobileViewport.addEventListener === "function") {
    mobileViewport.addEventListener("change", handleViewportChange);
  } else if (typeof mobileViewport.addListener === "function") {
    mobileViewport.addListener(handleViewportChange);
  }
})();
