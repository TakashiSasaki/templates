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
    setMobileMode("files");
    if (mobileViewport.matches && selectedLink instanceof HTMLAnchorElement) {
      window.requestAnimationFrame(() => {
        selectedLink.focus({ preventScroll: true });
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
