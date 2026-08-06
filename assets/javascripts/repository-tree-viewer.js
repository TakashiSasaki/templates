(() => {
  "use strict";

  document.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof Element)) {
      return;
    }

    const link = target.closest("a.repository-file-preview-link");
    if (!(link instanceof HTMLAnchorElement)) {
      return;
    }

    const frameName = link.getAttribute("target");
    if (!frameName) {
      return;
    }

    const viewer = document.querySelector(
      `[data-repository-file-viewer][data-preview-target="${CSS.escape(frameName)}"]`,
    );
    if (!(viewer instanceof HTMLElement)) {
      return;
    }

    const label = viewer.querySelector("[data-preview-label]");
    const source = viewer.querySelector("a[data-preview-source]");
    const frame = viewer.querySelector(`iframe[name="${CSS.escape(frameName)}"]`);
    const path = link.dataset.previewPath || "selected file";
    const sourceUrl = link.dataset.previewSource;

    if (label instanceof HTMLElement) {
      label.textContent = `Inline preview: ${path}`;
    }
    if (source instanceof HTMLAnchorElement && sourceUrl) {
      source.href = sourceUrl;
    }
    if (frame instanceof HTMLIFrameElement) {
      frame.title = `Inline preview: ${path}`;
    }

    const reducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;
    window.requestAnimationFrame(() => {
      viewer.scrollIntoView({
        behavior: reducedMotion ? "auto" : "smooth",
        block: "start",
      });
    });
  });
})();
