export const README_ASSET_URL = "./README.md";
export const MARKED_CDN_URL = "https://cdn.jsdelivr.net/npm/marked@18.0.13/lib/marked.esm.js";
export const DOMPURIFY_CDN_URL = "https://cdn.jsdelivr.net/npm/dompurify@3.4.15/dist/purify.es.mjs";

let rendererModulesPromise = null;

async function rendererModules() {
  if (!rendererModulesPromise) {
    rendererModulesPromise = Promise.all([
      import(MARKED_CDN_URL),
      import(DOMPURIFY_CDN_URL)
    ]).then(([markedModule, domPurifyModule]) => ({
      marked: markedModule.marked,
      DOMPurify: domPurifyModule.default
    }));
  }
  return rendererModulesPromise;
}

export async function renderReadmeMarkdown(markdown) {
  const { marked, DOMPurify } = await rendererModules();
  const rendered = marked.parse(markdown, { gfm: true, breaks: false });
  return DOMPurify.sanitize(rendered, { USE_PROFILES: { html: true } });
}
