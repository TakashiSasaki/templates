import { access, readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const required = [
  "README.md",
  "src/index.html", "src/css/app.css", "src/sw.js", "src/js/main.js", "src/js/github-api.js",
  "src/js/github-api-urls.js", "src/js/cache-policy.js", "src/js/service-worker-client.js",
  "src/js/repository-tree.js", "src/js/metrics.js", "src/js/visible-tree.js", "src/js/label-layout.js",
  "src/js/layout-weights.js", "src/js/touch-long-press.js", "src/js/dialog-dismiss.js",
  "src/js/fullscreen.js", "src/js/preferences.js", "src/js/selection-guard.js", "src/js/readme-renderer.js", "src/js/app-close.js", "src/js/treemap-view.js", "src/config/defaults.json"
];
await Promise.all(required.map((relativePath) => access(path.join(root, relativePath))));
const index = await readFile(path.join(root, "src/index.html"), "utf8");
if (!index.includes('type="module" src="./js/main.js"')) throw new Error("index.html must load main.js as an ES module");
if (!index.includes('id="node-details-dialog"')) throw new Error("index.html must define the long-press details dialog");
if (!index.includes('id="branch-select"') || !index.includes('aria-label="Repository branch"')) throw new Error("index.html must define an accessible branch dropdown");
if (index.includes('id="branch-tabs"')) throw new Error("legacy branch tabs must not remain");
if (!index.includes('id="view-tab-about"') || !index.includes('id="view-panel-about"')) throw new Error("index.html must move explanatory content into an About tab");
if (!index.includes('id="view-tab-readme"') || !index.includes('id="view-panel-readme"')) throw new Error("index.html must define the README tab and panel");
if (!index.includes('id="fullscreen-button"') || !index.includes('fullscreen-icon--enter') || !index.includes('fullscreen-icon--exit')) throw new Error("index.html must define fullscreen pictogram states");
if (!index.includes('class="controls floating-controls"')) throw new Error("treemap controls must support the mobile floating toolbar");
if (!index.includes('aria-label="Up one directory"') || !index.includes('aria-label="Repository root"')) throw new Error("pictogram navigation controls must retain accessible names");
if (!index.includes('aria-label="Area by files"') || !index.includes('aria-label="Area by bytes"')) throw new Error("metric pictograms must retain accessible names");
if (!index.includes('id="app-close-button"') || !index.includes('aria-label="Close application"')) throw new Error("index.html must define an accessible close-app pictogram button");
const main = await readFile(path.join(root, "src/js/main.js"), "utf8");
if (!main.includes("https://cdn.jsdelivr.net/npm/d3@7.9.0/+esm")) throw new Error("D3 dependency must remain exact-version pinned");
if (!main.includes("registerRepositoryTreemapServiceWorker")) throw new Error("main.js must register the service worker");
if (!main.includes("loadPreferences") || !main.includes("withBranchRelativeDepth")) throw new Error("main.js must persist branch/depth preferences");
if (!main.includes("createLatestSelectionGuard")) throw new Error("main.js must reject stale branch-load completions");
if (!main.includes("renderReadmeMarkdown") || !main.includes("ensureReadmeLoaded")) throw new Error("main.js must lazily render the app README");
if (!main.includes("initializeBranchSelect")) throw new Error("main.js must initialize the branch dropdown");
if (!main.includes("breadcrumb.hidden = breadcrumbItems.length === 0")) throw new Error("root breadcrumb must be hidden");
if (main.includes('breadcrumb.textContent = [state.branch')) throw new Error("breadcrumb must not repeat the selected branch");
if (!main.includes("toggleFullscreen")) throw new Error("main.js must implement fullscreen toggle");
if (!main.includes("closeApplication")) throw new Error("main.js must wire the close-app control");
if (!main.includes("isPointOutsideRect")) throw new Error("main.js must close details on backdrop clicks");
const cachePolicy = await readFile(path.join(root, "src/js/cache-policy.js"), "utf8");
if (!cachePolicy.includes("30 * 60 * 1000")) throw new Error("GitHub cache TTL must remain 30 minutes");
const preferences = await readFile(path.join(root, "src/js/preferences.js"), "utf8");
if (!preferences.includes("repository-treemap.preferences.v1")) throw new Error("localStorage preference key must remain versioned");
const readmeRenderer = await readFile(path.join(root, "src/js/readme-renderer.js"), "utf8");
if (!readmeRenderer.includes("marked@18.0.13") || !readmeRenderer.includes("dompurify@3.4.15")) throw new Error("README renderer CDN dependencies must remain exact-version pinned");
const build = await readFile(path.join(root, "scripts/build.mjs"), "utf8");
if (!build.includes('copyFile(path.join(root, "README.md"), path.join(output, "README.md"))')) throw new Error("build must publish the app-root README.md");
const touchLongPress = await readFile(path.join(root, "src/js/touch-long-press.js"), "utf8");
if (!touchLongPress.includes("LONG_PRESS_DELAY_MS = 500")) throw new Error("touch long press must remain 500 ms");
const layoutWeights = await readFile(path.join(root, "src/js/layout-weights.js"), "utf8");
if (!layoutWeights.includes("READABLE_WEIGHT_EXPONENT = 0.8")) throw new Error("readable layout exponent must remain explicit");
if (!layoutWeights.includes("TREEMAP_SQUARIFY_RATIO = 1.2")) throw new Error("squarify ratio must remain explicit");
const readme = await readFile(path.join(root, "README.md"), "utf8");
if (!readme.includes("## User interface") || !readme.includes("## Render deployment")) throw new Error("app README must document UI and deployment");
const defaults = JSON.parse(await readFile(path.join(root, "src/config/defaults.json"), "utf8"));
if (!Array.isArray(defaults.branches) || defaults.branches.length === 0) throw new Error("defaults.branches must be a non-empty array");
if (!Number.isInteger(defaults.defaultRelativeDepth) || defaults.defaultRelativeDepth < 1) throw new Error("defaults.defaultRelativeDepth must be a positive integer");
console.log("Validation passed");
