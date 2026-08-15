(() => {
  "use strict";

  const SELECTOR = "a.glossary-term[data-glossary-id]";
  const GLOSSARY_URL = "/glossary/index.json";
  const PROVIDER_LABELS = {
    site: "Site",
    skill: "Skill",
    policy: "Policy",
    webapp: "Webapp",
  };
  let glossaryPromise;
  let dialog;
  let activeLink;
  let pendingLink;
  let navigationObserver;
  let pointerDismissal = false;

  function loadGlossary() {
    if (!glossaryPromise) {
      glossaryPromise = fetch(GLOSSARY_URL, {
        credentials: "same-origin",
        cache: "no-cache",
      })
        .then((response) => {
          if (!response.ok) {
            throw new Error(`Glossary request failed: ${response.status}`);
          }
          return response.json();
        })
        .then((model) => {
          if (!model || !Array.isArray(model.terms)) {
            throw new Error("Glossary response is invalid");
          }
          const terms = new Map();
          for (const term of model.terms) {
            if (!term || typeof term.id !== "string" || typeof term.term !== "string") {
              continue;
            }
            terms.set(term.id, term);
          }
          return terms;
        })
        .catch((error) => {
          glossaryPromise = undefined;
          throw error;
        });
    }
    return glossaryPromise;
  }

  function setPendingLink(link) {
    if (pendingLink && pendingLink !== link) {
      pendingLink.removeAttribute("aria-busy");
    }
    pendingLink = link;
    link.setAttribute("aria-busy", "true");
  }

  function clearPendingLink(link) {
    if (!pendingLink || (link && pendingLink !== link)) {
      return;
    }
    const current = pendingLink;
    pendingLink = null;
    current.removeAttribute("aria-busy");
  }

  function closeDetachedDialog() {
    if (dialog && dialog.open && activeLink && !activeLink.isConnected) {
      pointerDismissal = true;
      dialog.close();
    }
  }

  function ensureDialog() {
    if (dialog) {
      return dialog;
    }

    dialog = document.createElement("dialog");
    dialog.className = "glossary-inline-dialog";
    dialog.setAttribute("aria-labelledby", "glossary-inline-title");
    dialog.setAttribute("aria-describedby", "glossary-inline-definition");
    dialog.innerHTML = `
      <div class="glossary-inline-dialog__header">
        <div>
          <p class="glossary-inline-dialog__eyebrow">Glossary</p>
          <h2 id="glossary-inline-title"></h2>
        </div>
        <button class="glossary-inline-dialog__close" type="button" aria-label="Close definition">×</button>
      </div>
      <p class="glossary-inline-dialog__definition" id="glossary-inline-definition"></p>
      <p class="glossary-inline-dialog__meta"></p>
      <p class="glossary-inline-dialog__actions"><a href="/glossary/">Open in Glossary</a></p>
    `;
    document.body.appendChild(dialog);

    navigationObserver = new MutationObserver(closeDetachedDialog);
    navigationObserver.observe(document.body, {
      childList: true,
      subtree: true,
    });

    dialog.querySelector(".glossary-inline-dialog__close").addEventListener("click", () => {
      pointerDismissal = false;
      dialog.close();
    });
    dialog.addEventListener("close", () => {
      const restore = activeLink;
      activeLink = null;
      clearPendingLink();
      if (
        !pointerDismissal &&
        restore instanceof HTMLElement &&
        document.contains(restore)
      ) {
        restore.focus({ preventScroll: true });
      }
      pointerDismissal = false;
    });
    return dialog;
  }

  function positionDialog(target, panel) {
    const rect = target.getBoundingClientRect();
    const viewportPadding = 12;
    const gap = 8;
    const panelRect = panel.getBoundingClientRect();
    const panelWidth = Math.min(panelRect.width || 400, window.innerWidth - viewportPadding * 2);
    const panelHeight = Math.min(panelRect.height || 280, window.innerHeight - viewportPadding * 2);
    const preferredLeft = Math.min(
      Math.max(rect.left, viewportPadding),
      Math.max(viewportPadding, window.innerWidth - panelWidth - viewportPadding),
    );
    const belowTop = rect.bottom + gap;
    const aboveTop = rect.top - panelHeight - gap;
    const preferredTop = Math.max(
      viewportPadding,
      belowTop + panelHeight <= window.innerHeight - viewportPadding
        ? belowTop
        : aboveTop,
    );

    panel.style.setProperty("--glossary-inline-left", `${preferredLeft}px`);
    panel.style.setProperty("--glossary-inline-top", `${preferredTop}px`);
  }

  function repositionOpenDialog() {
    closeDetachedDialog();
    if (dialog && dialog.open && activeLink && activeLink.isConnected) {
      positionDialog(activeLink, dialog);
    }
  }

  function explanation(term) {
    if (term.origin === "repository" && typeof term.definition === "string") {
      return term.definition;
    }
    if (typeof term.summary === "string") {
      return term.summary;
    }
    return "Definition unavailable.";
  }

  function providerLabel(provider) {
    if (typeof provider !== "string") {
      return "Glossary";
    }
    return PROVIDER_LABELS[provider] || provider;
  }

  function fillDialog(panel, term, link) {
    panel.querySelector("#glossary-inline-title").textContent = term.term;
    panel.querySelector(".glossary-inline-dialog__definition").textContent = explanation(term);
    const meta = panel.querySelector(".glossary-inline-dialog__meta");
    const owner = providerLabel(term.provider);
    meta.textContent = term.origin === "external" ? `External term · curated by ${owner}` : `Templates-defined · ${owner}`;
    panel.querySelector(".glossary-inline-dialog__actions a").href = link.href;
  }

  async function openDefinition(link) {
    const termId = link.dataset.glossaryId;
    if (!termId) {
      clearPendingLink();
      window.location.assign(link.href);
      return;
    }
    setPendingLink(link);

    let terms;
    try {
      terms = await loadGlossary();
    } catch (error) {
      if (pendingLink !== link || !link.isConnected) {
        return;
      }
      clearPendingLink(link);
      console.warn("Glossary definition loading failed", error);
      window.location.assign(link.href);
      return;
    }
    if (pendingLink !== link || !link.isConnected) {
      clearPendingLink(link);
      return;
    }
    const term = terms.get(termId);
    if (!term) {
      clearPendingLink(link);
      window.location.assign(link.href);
      return;
    }

    const panel = ensureDialog();
    clearPendingLink(link);
    pointerDismissal = false;
    activeLink = link;
    fillDialog(panel, term, link);
    if (!panel.open) {
      panel.show();
    }
    positionDialog(link, panel);
    panel.querySelector(".glossary-inline-dialog__close").focus({ preventScroll: true });
  }

  document.addEventListener("click", (event) => {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
      return;
    }
    const target = event.target;
    if (!(target instanceof Element)) {
      return;
    }
    const link = target.closest(SELECTOR);
    if (!(link instanceof HTMLAnchorElement)) {
      clearPendingLink();
      return;
    }
    event.preventDefault();
    void openDefinition(link);
  });

  document.addEventListener("pointerdown", (event) => {
    const target = event.target;
    if (!(target instanceof Node)) {
      return;
    }

    if (
      pendingLink &&
      !pendingLink.contains(target) &&
      (!dialog || !dialog.contains(target))
    ) {
      clearPendingLink();
    }

    if (
      dialog &&
      dialog.open &&
      !dialog.contains(target) &&
      (!activeLink || !activeLink.contains(target))
    ) {
      pointerDismissal = true;
      dialog.close();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") {
      return;
    }
    clearPendingLink();
    pointerDismissal = false;
    if (dialog && dialog.open) {
      event.preventDefault();
      dialog.close();
    }
  });

  window.addEventListener("resize", repositionOpenDialog);
  document.addEventListener("scroll", repositionOpenDialog, {
    capture: true,
    passive: true,
  });
})();
