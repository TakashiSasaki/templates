export function textStats(text) {
  if (typeof text !== "string") {
    throw new TypeError("text must be a string");
  }

  const bytes = Buffer.byteLength(text, "utf8");
  const lines = text.length === 0 ? 0 : text.split(/\n/).length;
  const trimmed = text.trim();
  const words = trimmed === "" ? 0 : trimmed.split(/\s+/u).length;

  return { bytes, lines, words };
}
