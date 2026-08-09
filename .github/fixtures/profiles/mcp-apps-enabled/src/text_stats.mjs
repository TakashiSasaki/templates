export function textStats(text) {
  if (typeof text !== "string") {
    throw new TypeError("text must be a string");
  }

  return {
    bytes: Buffer.byteLength(text, "utf8"),
    lines: text.length === 0 ? 0 : text.split(/\n/).length,
    words: text.trim() === "" ? 0 : text.trim().split(/\s+/u).length,
  };
}
