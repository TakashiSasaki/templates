(() => {
  "use strict";

  const FALLBACK_SELECTOR = "a.glossary-term[data-glossary-id]";
  const TRIGGER_SELECTOR = "button.glossary-term[data-glossary-id]";
  const CONTROL_SELECTOR = ".glossary-term[data-glossary-id]";
  const DIALOG_ID = "glossary-inline-dialog";
  const GLOSSARY_URL = "/glossary/index.json";
  const SITE_CHROME_LOCALES_URL = "/site-chrome-locales.json";
  const CACHED_FRESHNESS = "cached-unverified";
  const CACHED_ACCEPT_HEADER = "X-Templates-Glossary-Accepts-Cached";
  const GLOSSARY_INLINE_FIELDS = Object.freeze([
    "eyebrow",
    "close_definition",
    "open_in_glossary",
    "definition_unavailable",
    "cached_unverified",
    "external_term_prefix",
    "repository_term_prefix",
    "data_unavailable",
    "definition_load_failed",
    "definition_not_found",
  ]);
  const PROVIDER_LABELS = {
    site: "Site",
    composition: "Composition",
    policy: "Policy",
  };
  let glossaryPromise;
  let chromePromise;
  let glossaryFreshness = "verified-current";
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
        headers: { [CACHED_ACCEPT_HEADER]: "1" },
      })
        .then(async (response) => {
          if (!response.ok) {
            throw new Error(`Glossary request failed: ${response.status}`);
          }
          const freshness =
            response.headers.get("X-Templates-Freshness") === CACHED_FRESHNESS
              ? CACHED_FRESHNESS
              : "verified-current";
          return {
            model: await response.json(),
            freshness,
          };
        })
        .then(({ model, freshness }) => {
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
          glossaryFreshness = freshness;
          if (freshness === CACHED_FRESHNESS) {
            glossaryPromise = undefined;
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

  function parseGlossaryChrome(value) {
    if (
      !value ||
      typeof value !== "object" ||
      Array.isArray(value) ||
      value.schema_version !== 1 ||
      value.canonical_language !== "en" ||
      !Array.isArray(value.locales) ||
      value.locales.length === 0
    ) {
      throw new Error("Glossary chrome locale root is invalid");
    }
    const locales = new Map();
    for (const locale of value.locales) {
      if (
        !locale ||
        typeof locale !== "object" ||
        Array.isArray(locale) ||
        typeof locale.language !== "string" ||
        !/^[a-z]{2,3}(?:-[a-z0-9]{2,8})*$/.test(locale.language) ||
        !locale.glossary_inline ||
        typeof locale.glossary_inline !== "object" ||
        Array.isArray(locale.glossary_inline) ||
        Object.keys(locale.glossary_inline).length !== GLOSSARY_INLINE_FIELDS.length ||
        GLOSSARY_INLINE_FIELDS.some(
          (field) =>
            typeof locale.glossary_inline[field] !== "string" ||
            locale.glossary_inline[field].trim().length === 0,
        ) ||
        Object.keys(locale.glossary_inline).some(
          (field) => !GLOSSARY_INLINE_FIELDS.includes(field),
        ) ||
        locales.has(locale.language)
      ) {
        throw new Error("Glossary chrome locale entry is invalid");
      }
      locales.set(locale.language, Object.freeze({ ...locale.glossary_inline }));
    }
    if (!locales.has(value.canonical_language)) {
      throw new Error("Glossary chrome canonical locale is missing");
    }
    return Object.freeze({
      canonicalLanguage: value.canonical_language,
      locales,
    });
  }

  function loadGlossaryChrome() {
    if (!chromePromise) {
      chromePromise = fetch(SITE_CHROME_LOCALES_URL, {
        credentials: "same-origin",
        cache: "no-cache",
      })
        .then(async (response) => {
          if (!response.ok) {
            throw new Error(`Glossary chrome request failed: ${response.status}`);
          }
          return parseGlossaryChrome(await response.json());
        })
        .catch((error) => {
          chromePromise = undefined;
          throw error;
        });
    }
    return chromePromise;
  }

  function glossaryStrings(model, language) {
    if (!model || typeof language !== "string") {
      return null;
    }
    const exact = model.locales.get(language);
    if (exact) {
      return exact;
    }
    const primary = language.split("-", 1)[0];
    return model.locales.get(primary) || model.locales.get(model.canonicalLanguage) || null;
  }

  async function currentGlossaryStrings() {
    const model = await loadGlossaryChrome();
    const strings = glossaryStrings(model, document.documentElement?.lang || "");
    if (!strings) {
      throw new Error("Glossary chrome strings are unavailable");
    }
    return strings;
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

  function restoreFallbackLink(trigger) {
    if (!(trigger instanceof HTMLButtonElement) || !trigger.isConnected) {
      return null;
    }
    const link = document.createElement("a");
    link.className = trigger.className;
    while (trigger.firstChild) {
      link.appendChild(trigger.firstChild);
    }
    const termId = trigger.dataset.glossaryId;
    if (termId) {
      link.dataset.glossaryId = termId;
    }
    link.setAttribute("href", fallbackHref(trigger));
    trigger.replaceWith(link);
    return link;
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

  function applyDialogChrome(panel, strings) {
    panel.querySelector(".glossary-inline-dialog__eyebrow").textContent = strings.eyebrow;
    panel.querySelector(".glossary-inline-dialog__close").setAttribute(
      "aria-label",
      strings.close_definition,
    );
    panel.querySelector(".glossary-inline-dialog__actions a").textContent = strings.open_in_glossary;
  }

  function ensureDialog(strings) {
    if (dialog) {
      if (!dialog.isConnected) {
        document.body.appendChild(dialog);
        observeNavigationBody();
      }
      applyDialogChrome(dialog, strings);
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
          <p class="glossary-inline-dialog__eyebrow"></p>
          <h2 id="glossary-inline-title"></h2>
        </div>
        <button class="glossary-inline-dialog__close" type="button">×</button>
      </div>
      <p class="glossary-inline-dialog__definition" id="glossary-inline-definition"></p>
      <p class="glossary-inline-dialog__meta"></p>
      <p class="glossary-inline-dialog__freshness" role="status" hidden></p>
      <p class="glossary-inline-dialog__actions"><a href="/glossary/"></a></p>
    `;
    applyDialogChrome(dialog, strings);
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

  function explanation(term, strings) {
    if (term.origin === "repository" && typeof term.definition === "string") {
      return term.definition;
    }
    if (typeof term.summary === "string") {
      return term.summary;
    }
    return strings.definition_unavailable;
  }

  function providerLabel(provider) {
    if (typeof provider !== "string") {
      return "Glossary";
    }
    return PROVIDER_LABELS[provider] || provider;
  }

  function setFreshness(panel, freshness, strings) {
    const status = panel.querySelector(".glossary-inline-dialog__freshness");
    if (freshness === CACHED_FRESHNESS) {
      status.hidden = false;
      status.textContent = strings.cached_unverified;
      return;
    }
    status.hidden = true;
    status.textContent = "";
  }

  function fillDialog(panel, term, trigger, freshness, strings) {
    panel.querySelector("#glossary-inline-title").textContent = term.term;
    panel.querySelector(".glossary-inline-dialog__definition").textContent = explanation(term, strings);
    const meta = panel.querySelector(".glossary-inline-dialog__meta");
    const owner = providerLabel(term.provider);
    meta.textContent =
      term.origin === "external"
        ? `${strings.external_term_prefix}${owner}`
        : `${strings.repository_term_prefix}${owner}`;
    setFreshness(panel, freshness, strings);
    panel.querySelector(".glossary-inline-dialog__actions a").href = fallbackHref(trigger);
  }

  function fillErrorDialog(panel, trigger, message, strings) {
    const label = (trigger.textContent || "").trim();
    panel.querySelector("#glossary-inline-title").textContent = label || strings.eyebrow;
    panel.querySelector(".glossary-inline-dialog__definition").textContent = message;
    panel.querySelector(".glossary-inline-dialog__meta").textContent = strings.data_unavailable;
    setFreshness(panel, "unavailable", strings);
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

    const glossaryResultPromise = loadGlossary().then(
      (value) => ({ ok: true, value }),
      (error) => ({ ok: false, error }),
    );
    const chromeResultPromise = currentGlossaryStrings().then(
      (value) => ({ ok: true, value }),
      (error) => ({ ok: false, error }),
    );
    const [glossaryResult, chromeResult] = await Promise.all([
      glossaryResultPromise,
      chromeResultPromise,
    ]);

    if (pendingTrigger !== trigger || !trigger.isConnected) {
      clearPendingTrigger(trigger);
      return;
    }
    if (!chromeResult.ok) {
      console.warn("Glossary chrome loading failed", chromeResult.error);
      clearPendingTrigger(trigger);
      restoreFallbackLink(trigger);
      return;
    }
    const strings = chromeResult.value;
    if (!glossaryResult.ok) {
      console.warn("Glossary definition loading failed", glossaryResult.error);
      clearPendingTrigger(trigger);
      const panel = ensureDialog(strings);
      fillErrorDialog(panel, trigger, strings.definition_load_failed, strings);
      presentDialog(trigger, panel);
      return;
    }

    const terms = glossaryResult.value;
    const term = terms.get(termId);
    if (!term) {
      clearPendingTrigger(trigger);
      const panel = ensureDialog(strings);
      fillErrorDialog(panel, trigger, strings.definition_not_found, strings);
      presentDialog(trigger, panel);
      return;
    }

    const panel = ensureDialog(strings);
    clearPendingTrigger(trigger);
    fillDialog(panel, term, trigger, glossaryFreshness, strings);
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
