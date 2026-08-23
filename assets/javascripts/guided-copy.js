(() => {
  const statusTimeouts = new WeakMap();

  const copyWithFallback = (value) => {
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
  };

  const copyText = async (value) => {
    if (
      window.isSecureContext &&
      navigator.clipboard &&
      typeof navigator.clipboard.writeText === "function"
    ) {
      await navigator.clipboard.writeText(value);
      return;
    }
    copyWithFallback(value);
  };

  document.addEventListener("click", async (event) => {
    const target = event.target;
    if (!(target instanceof Element)) {
      return;
    }
    const button = target.closest("button[data-copy-url]");
    if (!(button instanceof HTMLButtonElement)) {
      return;
    }

    const value = button.dataset.copyUrl;
    const successMessage = button.dataset.copySuccess;
    const failureMessage = button.dataset.copyFailure;
    if (!value || !successMessage || !failureMessage) {
      return;
    }

    const name = button.dataset.copyName || "URL";
    const container = button.closest(".page-path");
    const status = container ? container.querySelector(".copy-status") : null;

    button.disabled = true;
    try {
      await copyText(value);
      if (status) {
        status.textContent = successMessage;
      }
    } catch (error) {
      console.warn(`Unable to copy ${name}`, error);
      if (status) {
        status.textContent = failureMessage;
      }
    } finally {
      button.disabled = false;
      if (status) {
        const existingTimeout = statusTimeouts.get(status);
        if (existingTimeout !== undefined) {
          window.clearTimeout(existingTimeout);
        }
        const timeoutId = window.setTimeout(() => {
          status.textContent = "";
          statusTimeouts.delete(status);
        }, 1800);
        statusTimeouts.set(status, timeoutId);
      }
    }
  });
})();
