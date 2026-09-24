export const CLOSE_FALLBACK_DELAY_MS = 120;

export function closeFallbackAction(historyLength) {
  return Number.isFinite(historyLength) && historyLength > 1 ? "back" : "blank";
}

export function closeApplication(windowRef, delayMs = CLOSE_FALLBACK_DELAY_MS) {
  windowRef.close();

  windowRef.setTimeout(() => {
    if (windowRef.closed) return;

    if (closeFallbackAction(windowRef.history?.length) === "back") {
      windowRef.history.back();
      return;
    }

    windowRef.location.replace("about:blank");
  }, delayMs);
}
