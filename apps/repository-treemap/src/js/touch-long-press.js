export const LONG_PRESS_DELAY_MS = 500;
export const LONG_PRESS_MOVE_TOLERANCE_PX = 12;

export function isLongPressPointerType(pointerType) {
  return pointerType === "touch" || pointerType === "pen";
}

export function exceedsMoveTolerance(startX, startY, currentX, currentY, tolerance = LONG_PRESS_MOVE_TOLERANCE_PX) {
  const dx = currentX - startX;
  const dy = currentY - startY;
  return Math.hypot(dx, dy) > tolerance;
}

export function bindTouchLongPress(element, onLongPress, {
  delayMs = LONG_PRESS_DELAY_MS,
  moveTolerancePx = LONG_PRESS_MOVE_TOLERANCE_PX
} = {}) {
  let timer = null;
  let start = null;
  let suppressClickUntil = 0;

  const cancelPending = () => {
    if (timer !== null) clearTimeout(timer);
    timer = null;
    start = null;
  };

  element.addEventListener("pointerdown", (event) => {
    if (!event.isPrimary || !isLongPressPointerType(event.pointerType)) return;
    cancelPending();
    start = { pointerId: event.pointerId, x: event.clientX, y: event.clientY };
    timer = setTimeout(() => {
      timer = null;
      if (!start) return;
      suppressClickUntil = Date.now() + 900;
      onLongPress();
    }, delayMs);
  });

  element.addEventListener("pointermove", (event) => {
    if (!start || event.pointerId !== start.pointerId) return;
    if (exceedsMoveTolerance(start.x, start.y, event.clientX, event.clientY, moveTolerancePx)) cancelPending();
  });

  for (const eventName of ["pointerup", "pointercancel", "lostpointercapture"]) {
    element.addEventListener(eventName, cancelPending);
  }

  element.addEventListener("click", (event) => {
    if (Date.now() >= suppressClickUntil) return;
    event.preventDefault();
    event.stopImmediatePropagation();
  }, true);

  element.addEventListener("contextmenu", (event) => {
    if (Date.now() < suppressClickUntil) event.preventDefault();
  });
}
