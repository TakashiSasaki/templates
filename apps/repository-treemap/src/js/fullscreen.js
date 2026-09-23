export function fullscreenButtonLabel(active) {
  return active ? "Exit fullscreen" : "Fullscreen";
}

export function currentFullscreenElement(documentRef) {
  return documentRef?.fullscreenElement ?? documentRef?.webkitFullscreenElement ?? null;
}

export function supportsNativeFullscreen(element, documentRef) {
  const canEnter = Boolean(element?.requestFullscreen || element?.webkitRequestFullscreen);
  const canExit = Boolean(documentRef?.exitFullscreen || documentRef?.webkitExitFullscreen);
  return canEnter && canExit;
}

export async function requestNativeFullscreen(element) {
  const request = element?.requestFullscreen?.bind(element)
    ?? element?.webkitRequestFullscreen?.bind(element);
  if (!request) return false;
  await request();
  return true;
}

export async function exitNativeFullscreen(documentRef) {
  const exit = documentRef?.exitFullscreen?.bind(documentRef)
    ?? documentRef?.webkitExitFullscreen?.bind(documentRef);
  if (!exit) return false;
  await exit();
  return true;
}
