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
  const treeScroller = tree.querySelector(".tree");
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

  const filterListItems = Array.from(tree.querySelectorAll(".tree li"));
  const filterListItemSet = new Set(filterListItems);
  const filterDetails = Array.from(tree.querySelectorAll(".tree details"));
  const filterDetailsSet = new Set(filterDetails);
  const filterEntries = fileLinks
    .map((link) => {
      const path = link.dataset.filePath;
      return path ? { link, path, key: path.toLocaleLowerCase() } : null;
    })
    .filter(Boolean);

  let selectedLink = null;
  let appliedHash = null;
  let shareControls = null;
  let shareStatus = null;
  let shareButtons = [];
  let filterControls = null;
  let filterInput = null;
  let filterStatus = null;
  let filterRestoreDetails = null;
  let treeReturnFocus = null;
  let treeReturnScrollTop = 0;

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

  function restoreFilterDetails() {
    if (!(filterRestoreDetails instanceof Map)) {
      return;
    }
    for (const [details, wasOpen] of filterRestoreDetails) {
      details.open = wasOpen;
    }
    filterRestoreDetails = null;
  }

  function applyFileFilter() {
    if (!(filterInput instanceof HTMLElement)) {
      return [];
    }
    const query = String(filterInput.value || "").trim().toLocaleLowerCase();
    if (!query) {
      for (const item of filterListItems) {
        item.hidden = false;
      }
      restoreFilterDetails();
      if (filterStatus instanceof HTMLElement) {
        filterStatus.textContent = `${filterEntries.length} files`;
      }
      return filterEntries.map((entry) => entry.link);
    }

    if (!(filterRestoreDetails instanceof Map)) {
      filterRestoreDetails = new Map(
        filterDetails.map((details) => [details, Boolean(details.open)])
      );
    }
    for (const item of filterListItems) {
      item.hidden = true;
    }

    const matches = [];
    for (const entry of filterEntries) {
      if (!entry.key.includes(query)) {
        continue;
      }
      matches.push(entry.link);
      let current = entry.link.parentElement;
      while (current && current !== tree) {
        if (filterListItemSet.has(current)) {
          current.hidden = false;
        }
        if (filterDetailsSet.has(current)) {
          current.open = true;
        }
        current = current.parentElement;
      }
    }

    if (filterStatus instanceof HTMLElement) {
      filterStatus.textContent =
        matches.length === 0
          ? "No matching files"
          : `${matches.length} of ${filterEntries.length} files`;
    }
    return matches;
  }

  function rememberTreeContext(fallback) {
    if (treeScroller instanceof HTMLElement) {
      treeReturnScrollTop = treeScroller.scrollTop;
    }
    const active = document.activeElement;
    const activeBelongsToTree =
      active instanceof HTMLElement &&
      (typeof tree.contains !== "function" || tree.contains(active));
    treeReturnFocus = activeBelongsToTree ? active : fallback;
  }

  function elementIsFilterVisible(element) {
    if (!(element instanceof HTMLElement)) {
      return false;
    }
    let current = element;
    while (current && current !== tree) {
      if (current.hidden) {
        return false;
      }
      current = current.parentElement;
    }
    return true;
  }

  function restoreTreeContext() {
    if (treeScroller instanceof HTMLElement) {
      treeScroller.scrollTop = treeReturnScrollTop;
    }
    const fallbackTreeControl = tree.querySelector(
      "a[data-repository-file], summary, a, button"
    );
    const candidates = [
      treeReturnFocus,
      selectedLink,
      filterInput,
      fallbackTreeControl,
    ];
    const focusTarget = candidates.find((candidate) => elementIsFilterVisible(candidate));
    if (focusTarget instanceof HTMLElement) {
      focusTarget.focus({ preventScroll: true });
    }
  }

  function quickOpenFirstMatch() {
    const matches = applyFileFilter();
    const link = matches[0];
    if (!(link instanceof HTMLAnchorElement) || !managedFrame) {
      return false;
    }
    const path = link.dataset.filePath;
    if (!path) {
      return false;
    }
    rememberTreeContext(filterInput);
    selectLink(link, { navigateFrame: true, focusBackButton: true });
    pushFileLocation(path);
    return true;
  }

  function initializeFiltering() {
    if (
      !(managedFrame instanceof HTMLIFrameElement) ||
      !(browserHeader instanceof HTMLElement) ||
      typeof document.createElement !== "function"
    ) {
      return;
    }

    filterControls = document.createElement("div");
    filterControls.setAttribute("data-repository-filter", "");
    filterControls.style.display = "flex";
    filterControls.style.flexWrap = "wrap";
    filterControls.style.alignItems = "center";
    filterControls.style.gap = ".35rem";
    filterControls.style.marginTop = ".6rem";

    filterInput = document.createElement("input");
    filterInput.type = "search";
    filterInput.value = "";
    filterInput.placeholder = "Filter files…";
    filterInput.setAttribute("aria-label", "Filter files");
    filterInput.setAttribute("autocomplete", "off");
    filterInput.setAttribute("spellcheck", "false");
    filterInput.style.flex = "1 1 11rem";
    filterInput.style.minWidth = "0";
    filterInput.style.minHeight = "2.3rem";
    filterInput.style.border = "1px solid color-mix(in srgb, CanvasText 24%, transparent)";
    filterInput.style.borderRadius = ".45rem";
    filterInput.style.padding = ".35rem .55rem";
    filterInput.style.color = "inherit";
    filterInput.style.background = "Canvas";
    filterInput.style.font = "inherit";
    filterInput.addEventListener("input", applyFileFilter);
    filterInput.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        if (filterInput.value) {
          event.preventDefault();
          filterInput.value = "";
          applyFileFilter();
        }
        return;
      }
      if (event.key === "Enter" && String(filterInput.value || "").trim()) {
        if (quickOpenFirstMatch()) {
          event.preventDefault();
        }
      }
    });

    filterStatus = document.createElement("span");
    filterStatus.setAttribute("data-repository-filter-status", "");
    filterStatus.setAttribute("aria-live", "polite");
    filterStatus.style.flex = "0 0 100%";
    filterStatus.style.fontSize = ".74rem";
    filterStatus.style.opacity = ".72";

    filterControls.appendChild(filterInput);
    filterControls.appendChild(filterStatus);
    browserHeader.appendChild(filterControls);
    applyFileFilter();
  }

  function targetIsEditable(target) {
    return (
      target instanceof Element &&
      typeof target.closest === "function" &&
      target.closest("input, textarea, select, [contenteditable='true']") !== null
    );
  }

  document.documentElement.classList.add("repository-browser-enhanced");
  setMobileMode("files");
  initializeFiltering();
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
    rememberTreeContext(link);
    selectLink(link, { navigateFrame: true, focusBackButton: true });
    pushFileLocation(path);
  });

  filesButton.addEventListener("click", () => {
    setMobileMode("files");
    if (mobileViewport.matches) {
      window.requestAnimationFrame(restoreTreeContext);
    }
  });

  if (typeof document.addEventListener === "function") {
    document.addEventListener("keydown", (event) => {
      if (
        event.defaultPrevented ||
        event.key !== "/" ||
        event.metaKey ||
        event.ctrlKey ||
        event.altKey ||
        targetIsEditable(event.target) ||
        !(filterInput instanceof HTMLElement)
      ) {
        return;
      }
      event.preventDefault();
      setMobileMode("files");
      window.requestAnimationFrame(() => {
        if (treeScroller instanceof HTMLElement) {
          treeScroller.scrollTop = treeReturnScrollTop;
        }
        filterInput.focus({ preventScroll: true });
      });
    });
  }

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
