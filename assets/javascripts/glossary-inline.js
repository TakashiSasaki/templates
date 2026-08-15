(() => {
  "use strict";

  const FALLBACK_SELECTOR = "a.glossary-term[data-glossary-id]";
  const TRIGGER_SELECTOR = "button.glossary-term[data-glossary-id]";
  const CONTROL_SELECTOR = ".glossary-term[data-glossary-id]";
  const DIALOG_ID = "glossary-inline-dialog";
  const GLOSSARY_URL = "/glossary/index.json";
  const PROVIDER_LABELS = {
    site: "Site",
    skill: "Skill",
    policy: "Policy",
    webapp: "Webapp",
  };
  let glossaryPromise;
  let dialog;
  let activeTrigger;
  let pendingTrigger;
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

  function fallbackHref(trigger) {
    const href = trigger.dataset.glossaryHref;
    if (href) {
      return href;
    }
    const termId = trigger.dataset.glossaryId;
    return termId ? `/glossary/#${encodeURIComponent(termId)}` : "/glossary/";
  }

  function enhanceLink(link) {
    if (!(link instanceof HTMLAnchorElement) || !link.matches(FALLBACK_SELECTOR)) {
      return link;
    }
    const termId = link.dataset.glossaryId;
    if (!termId) {
      return link;
    }

    const trigger = document.createElement("button");
    trigger.type = "button";
    trigger.className = link.className;
    while (link.firstChild) {
      trigger.appendChild(link.firstChild);
    }
    trigger.dataset.glossaryId = termId;
    trigger.dataset.glossaryHref = link.getAttribute("href") || `/glossary/#${encodeURIComponent(termId)}`;
    trigger.setAttribute("aria-haspopup", "dialog");
    trigger.setAttribute("aria-controls", DIALOG_ID);
    trigger.setAttribute("aria-expanded", "false");
    link.replaceWith(trigger);
    return trigger;
  }

  function enhanceGlossaryLinks(root) {
    if (root instanceof HTMLAnchorElement && root.matches(FALLBACK_SELECTOR)) {
      enhanceLink(root);
      return;
    }
    if (!(root instanceof Document || root instanceof Element || root instanceof DocumentFragment)) {
      return;
    }
    for (const link of root.querySelectorAll(FALLBACK_SELECTOR)) {
      enhanceLink(link);
    }
  }

  function setPendingTrigger(trigger) {
    if (pendingTrigger && pendingTrigger !== trigger) {
      pendingTrigger.removeAttribute("aria-busy");
    }
    pendingTrigger = trigger;
    trigger.setAttribute("aria-busy", "true");
  }

  function clearPendingTrigger(trigger) {
    if (!pendingTrigger || (trigger && pendingTrigger !== trigger)) {
      return;
    }
    const current = pendingTrigger;
    pendingTrigger = null;
    current.removeAttribute("aria-busy");
  }

  function closeDetachedDialog() {
    if (dialog && dialog.open && activeTrigger && !activeTrigger.isConnected) {
      pointerDismissal = true;
      dialog.close();
    }
  }

  function observeNavigationBody() {
    if (!document.body) {
      return;
    }
    if (!navigationObserver) {
      navigationObserver = new MutationObserver((records) => {
        closeDetachedDialog();
        for (const record of records) {
          for (const node of record.addedNodes) {
            if (node instanceof Element || node instanceof DocumentFragment) {
              enhanceGlossaryLinks(node);
            }
          }
        }
      });
    } else {
      navigationObserver.disconnect();
    }
    navigationObserver.observe(document.body, {
      childList: true,
      subtree: true,
    });
  }

  function ensureDialog() {
    if (dialog) {
      if (!dialog.isConnected) {
        document.body.appendChild(dialog);
        observeNavigationBody();
      }
      return dialog;
    }

    dialog = document.createElement("dialog");
    dialog.id = DIALOG_ID;
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
    observeNavigationBody();

    dialog.querySelector(".glossary-inline-dialog__close").addEventListener("click", () => {
      pointerDismissal = false;
      dialog.close();
    });
    dialog.addEventListener("close", () => {
      const restore = activeTrigger;
      if (restore instanceof HTMLElement) {
        restore.setAttribute("aria-expanded", "false");
      }
      activeTrigger = null;
      clearPendingTrigger();
      if (
        !pointerDismissal &&
        restore instanceof HTMLElement &&
        restore.isConnected
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
    if (dialog && dialog.open && activeTrigger && activeTrigger.isConnected) {
      positionDialog(activeTrigger, dialog);
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

  function fillDialog(panel, term, trigger) {
    panel.querySelector("#glossary-inline-title").textContent = term.term;
    panel.querySelector(".glossary-inline-dialog__definition").textContent = explanation(term);
    const meta = panel.querySelector(".glossary-inline-dialog__meta");
    const owner = providerLabel(term.provider);
    meta.textContent = term.origin === "external" ? `External term · curated by ${owner}` : `Templates-defined · ${owner}`;
    panel.querySelector(".glossary-inline-dialog__actions a").href = fallbackHref(trigger);
  }

  function fillErrorDialog(panel, trigger, message) {
    const label = (trigger.textContent || "").trim();
    panel.querySelector("#glossary-inline-title").textContent = label || "Glossary";
    panel.querySelector(".glossary-inline-dialog__definition").textContent = message;
    panel.querySelector(".glossary-inline-dialog__meta").textContent = "Glossary data unavailable.";
    panel.querySelector(".glossary-inline-dialog__actions a").href = fallbackHref(trigger);
  }

  function presentDialog(trigger, panel) {
    if (activeTrigger && activeTrigger !== trigger) {
      activeTrigger.setAttribute("aria-expanded", "false");
    }
    pointerDismissal = false;
    activeTrigger = trigger;
    trigger.setAttribute("aria-expanded", "true");
    if (!panel.open) {
      panel.show();
    }
    positionDialog(trigger, panel);
    panel.querySelector(".glossary-inline-dialog__close").focus({ preventScroll: true });
  }

  async function openDefinition(trigger) {
    const termId = trigger.dataset.glossaryId;
    if (!termId) {
      clearPendingTrigger();
      return;
    }
    setPendingTrigger(trigger);

    let terms;
    try {
      terms = await loadGlossary();
    } catch (error) {
      const canPresent = pendingTrigger === trigger && trigger.isConnected;
      clearPendingTrigger(trigger);
      if (!canPresent) {
        return;
      }
      console.warn("Glossary definition loading failed", error);
      const panel = ensureDialog();
      fillErrorDialog(panel, trigger, "Definition could not be loaded.");
      presentDialog(trigger, panel);
      return;
    }
    if (pendingTrigger !== trigger || !trigger.isConnected) {
      clearPendingTrigger(trigger);
      return;
    }
    const term = terms.get(termId);
    if (!term) {
      clearPendingTrigger(trigger);
      const panel = ensureDialog();
      fillErrorDialog(panel, trigger, "Definition could not be found.");
      presentDialog(trigger, panel);
      return;
    }

    const panel = ensureDialog();
    clearPendingTrigger(trigger);
    fillDialog(panel, term, trigger);
    presentDialog(trigger, panel);
  }

  document.addEventListener("click", (event) => {
    if (event.defaultPrevented || event.button !== 0) {
      return;
    }
    const target = event.target;
    if (!(target instanceof Element)) {
      return;
    }
    const control = target.closest(CONTROL_SELECTOR);
    if (!control) {
      clearPendingTrigger();
      return;
    }

    if (control instanceof HTMLAnchorElement) {
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
        return;
      }
      event.preventDefault();
      const trigger = enhanceLink(control);
      if (trigger instanceof HTMLButtonElement && trigger.matches(TRIGGER_SELECTOR)) {
        void openDefinition(trigger);
      }
      return;
    }

    if (!(control instanceof HTMLButtonElement) || !control.matches(TRIGGER_SELECTOR)) {
      return;
    }
    event.preventDefault();
    void openDefinition(control);
  });

  document.addEventListener("pointerdown", (event) => {
    const target = event.target;
    if (!(target instanceof Node)) {
      return;
    }

    if (
      pendingTrigger &&
      !pendingTrigger.contains(target) &&
      (!dialog || !dialog.contains(target))
    ) {
      clearPendingTrigger();
    }

    if (
      dialog &&
      dialog.open &&
      !dialog.contains(target) &&
      (!activeTrigger || !activeTrigger.contains(target))
    ) {
      pointerDismissal = true;
      dialog.close();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") {
      return;
    }
    clearPendingTrigger();
    pointerDismissal = false;
    if (dialog && dialog.open) {
      event.preventDefault();
      dialog.close();
    }
  });

  enhanceGlossaryLinks(document);
  observeNavigationBody();
  window.addEventListener("resize", repositionOpenDialog);
  document.addEventListener("scroll", repositionOpenDialog, {
    capture: true,
    passive: true,
  });
})();
