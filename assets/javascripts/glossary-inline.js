(() => {
  "use strict";

  const SELECTOR = "a.glossary-term[data-glossary-id]";
  const GLOSSARY_URL = "/glossary/index.json";
  let glossaryPromise;
  let dialog;
  let activeLink;
  let pendingLink;

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
        });
    }
    return glossaryPromise;
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

    dialog.querySelector(".glossary-inline-dialog__close").addEventListener("click", () => {
      dialog.close();
    });
    dialog.addEventListener("close", () => {
      const restore = activeLink;
      activeLink = null;
      pendingLink = null;
      if (restore instanceof HTMLElement && document.contains(restore)) {
        restore.focus({ preventScroll: true });
      }
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
    const preferredTop = belowTop + panelHeight <= window.innerHeight - viewportPadding
      ? belowTop
      : Math.max(viewportPadding, aboveTop);

    panel.style.setProperty("--glossary-inline-left", `${preferredLeft}px`);
    panel.style.setProperty("--glossary-inline-top", `${preferredTop}px`);
  }

  function repositionOpenDialog() {
    if (dialog && dialog.open && activeLink && document.contains(activeLink)) {
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

  function fillDialog(panel, term, link) {
    panel.querySelector("#glossary-inline-title").textContent = term.term;
    panel.querySelector(".glossary-inline-dialog__definition").textContent = explanation(term);
    const meta = panel.querySelector(".glossary-inline-dialog__meta");
    const owner = typeof term.provider === "string" ? term.provider : "Glossary";
    meta.textContent = term.origin === "external" ? `External term · curated by ${owner}` : `Templates-defined · ${owner}`;
    panel.querySelector(".glossary-inline-dialog__actions a").href = link.href;
  }

  async function openDefinition(link) {
    pendingLink = link;
    const termId = link.dataset.glossaryId;
    if (!termId) {
      pendingLink = null;
      window.location.assign(link.href);
      return;
    }

    let terms;
    try {
      terms = await loadGlossary();
    } catch (error) {
      if (pendingLink !== link) {
        return;
      }
      pendingLink = null;
      console.warn("Glossary definition loading failed", error);
      window.location.assign(link.href);
      return;
    }
    if (pendingLink !== link) {
      return;
    }
    const term = terms.get(termId);
    if (!term) {
      pendingLink = null;
      window.location.assign(link.href);
      return;
    }

    const panel = ensureDialog();
    pendingLink = null;
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
      pendingLink = null;
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
      pendingLink = null;
    }

    if (
      dialog &&
      dialog.open &&
      !dialog.contains(target) &&
      (!activeLink || !activeLink.contains(target))
    ) {
      dialog.close();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && dialog && dialog.open) {
      event.preventDefault();
      dialog.close();
    }
  });

  window.addEventListener("resize", repositionOpenDialog);
})();
