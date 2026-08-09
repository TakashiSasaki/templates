export function textStats(text) {
  if (typeof text !== "string") {
    throw new TypeError("text must be a string");
  }

  const newlineCount = (text.match(/\n/g) ?? []).length;
  const lines = text.length === 0 ? 0 : newlineCount + (text.endsWith("\n") ? 0 : 1);

  return {
    bytes: Buffer.byteLength(text, "utf8"),
    lines,
    words: text.trim() === "" ? 0 : text.trim().split(/\s+/u).length,
  };
}
