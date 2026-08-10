export function textStats(text) {
  if (typeof text !== "string") {
    throw new TypeError("text must be a string");
  }

  const bytes = Buffer.byteLength(text, "utf8");
  const newlineCount = (text.match(/\n/g) ?? []).length;
  const lines = text.length === 0 ? 0 : newlineCount + (text.endsWith("\n") ? 0 : 1);
  const trimmed = text.trim();
  const words = trimmed === "" ? 0 : trimmed.split(/\s+/u).length;

  return { bytes, lines, words };
}
