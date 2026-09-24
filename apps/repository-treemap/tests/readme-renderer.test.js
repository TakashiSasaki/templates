import test from "node:test";
import assert from "node:assert/strict";
import { DOMPURIFY_CDN_URL, MARKED_CDN_URL, README_ASSET_URL } from "../src/js/readme-renderer.js";

test("README renderer uses exact-version CDN dependencies", () => {
  assert.equal(MARKED_CDN_URL, "https://cdn.jsdelivr.net/npm/marked@18.0.13/lib/marked.esm.js");
  assert.equal(DOMPURIFY_CDN_URL, "https://cdn.jsdelivr.net/npm/dompurify@3.4.15/dist/purify.es.mjs");
});

test("README renderer reads the build-copied app-root README", () => {
  assert.equal(README_ASSET_URL, "./README.md");
});
