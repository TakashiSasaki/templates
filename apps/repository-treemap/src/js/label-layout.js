export function cellLabelPresentation(width, height) {
  const normalizedWidth = Number.isFinite(width) ? Math.max(0, width) : 0;
  const normalizedHeight = Number.isFinite(height) ? Math.max(0, height) : 0;
  const area = normalizedWidth * normalizedHeight;

  const density = normalizedWidth >= 90 && normalizedHeight >= 48 && area >= 4200
    ? "full"
    : normalizedWidth >= 26 && normalizedHeight >= 16
      ? "compact"
      : "tiny";

  const widthFactor = normalizedWidth < 48 ? normalizedWidth * 0.28 : normalizedWidth * 0.16;
  const heightFactor = normalizedHeight * 0.28;
  const fontSize = Math.round(Math.max(6, Math.min(16, widthFactor, heightFactor)));

  return {
    density,
    showMeta: density === "full",
    fontSize
  };
}
