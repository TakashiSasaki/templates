const CACHE_NAME = "templates-portal-shell-v4";
const DOCUMENT_CACHE_NAME = "templates-portal-documents-v1";
const GLOSSARY_CACHE_NAME = "templates-portal-glossary-v1";
const GLOSSARY_MODEL_PATH = "/glossary/index.json";
const GLOSSARY_CACHED_ACCEPT_HEADER = "X-Templates-Glossary-Accepts-Cached";
const SITE_CHROME_LOCALES_PATH = "/site-chrome-locales.json";
const PWA_FRESHNESS_FIELDS = Object.freeze([
  "saved_copy",
  "checking",
  "unverified",
  "update_available",
  "published_changed",
  "reload",
  "offline_unavailable",
]);
const STATIC_ASSETS = [
  "/app.webmanifest",
  "/icon.svg",
  "/site-chrome-locales.json",
  "/stylesheets/extra.css",
  "/stylesheets/landing-cover.css",
  "/stylesheets/landing-shell.css",
  "/stylesheets/mobile-density.css",
  "/stylesheets/translation-reader.css",
  "/stylesheets/glossary-inline.css",
  "/stylesheets/freshness-status.css",
  "/javascripts/repository-tree-viewer.js",
  "/javascripts/repository-browser.js",
  "/javascripts/guided-copy.js",
  "/javascripts/pwa.js",
  "/javascripts/reader-navigation.js",
  "/javascripts/search-history.js",
  "/javascripts/glossary-inline.js",
  "/javascripts/composition-playground.js",
  "/javascripts/composition-playground-explain.js"
];
const FRESHNESS_STATES = Object.freeze([
  "verified-current",
  "checking",
  "cached-unverified",
  "update-available",
]);
const WORKER_INSTANCE_ID = self.crypto.randomUUID();
const DOCUMENT_SOFT_TIMEOUT_MS = 1500;
const FRESHNESS_UI_ACK_TIMEOUT_MS = 500;
const MAX_REMEMBERED_FRESHNESS_STATES = 64;

const documentCacheMutationQueues = new Map();
const documentCacheMutationGenerations = new Map();
const authoritativeDocumentDeletions = new Map();
const clientFreshnessStates = new Map();
const documentFreshnessStates = new Map();
let nextDocumentRequestGeneration = 0;

let nextGlossaryRequestGeneration = 0;
let glossaryCacheMutationGeneration = 0;
let glossaryCacheMutationQueue = Promise.resolve();
let authoritativeGlossaryDeletionGeneration = 0;

function parseSiteChromeLocales(value) {
  if (
    !value ||
    typeof value !== "object" ||
    Array.isArray(value) ||
    value.schema_version !== 1 ||
    value.canonical_language !== "en" ||
    !Array.isArray(value.locales) ||
    value.locales.length === 0
  ) {
    return undefined;
  }
  const locales = new Map();
  for (const locale of value.locales) {
    if (
      !locale ||
      typeof locale !== "object" ||
      Array.isArray(locale) ||
      typeof locale.language !== "string" ||
      !/^[a-z]{2,3}(?:-[a-z0-9]{2,8})*$/.test(locale.language) ||
      !locale.pwa_freshness ||
      typeof locale.pwa_freshness !== "object" ||
      Array.isArray(locale.pwa_freshness) ||
      Object.keys(locale.pwa_freshness).length !== PWA_FRESHNESS_FIELDS.length ||
      PWA_FRESHNESS_FIELDS.some(
        (field) =>
          typeof locale.pwa_freshness[field] !== "string" ||
          locale.pwa_freshness[field].trim().length === 0
      ) ||
      Object.keys(locale.pwa_freshness).some(
        (field) => !PWA_FRESHNESS_FIELDS.includes(field)
      ) ||
      locales.has(locale.language)
    ) {
      return undefined;
    }
    locales.set(locale.language, Object.freeze({ ...locale.pwa_freshness }));
  }
  if (!locales.has(value.canonical_language)) {
    return undefined;
  }
  return Object.freeze({
    canonicalLanguage: value.canonical_language,
    locales,
  });
}

async function loadSiteChromeLocales() {
  try {
    const cache = await caches.open(CACHE_NAME);
    const response = await cache.match(SITE_CHROME_LOCALES_PATH);
    if (!response || !response.ok) {
      return undefined;
    }
    return parseSiteChromeLocales(await response.json());
  } catch (error) {
    console.warn("PWA chrome locale cache read failed", error);
    return undefined;
  }
}

function pwaFreshnessStrings(model, language) {
  if (!model) {
    return undefined;
  }
  if (typeof language === "string") {
    const exact = model.locales.get(language);
    if (exact) {
      return exact;
    }
    const primary = language.split("-", 1)[0];
    const primaryLocale = model.locales.get(primary);
    if (primaryLocale) {
      return primaryLocale;
    }
  }
  return model.locales.get(model.canonicalLanguage);
}

function htmlLanguage(source) {
  const htmlTags = source.match(/<html\b[^>]*>/gi) || [];
  if (htmlTags.length !== 1) {
    return undefined;
  }
  const attributes = extractMetaAttributes(htmlTags[0]);
  const language = attributes.get("lang");
  return typeof language === "string" &&
    /^[a-z]{2,3}(?:-[a-z0-9]{2,8})*$/.test(language)
    ? language
    : undefined;
}

function requestLanguage(model, request) {
  if (!model) {
    return undefined;
  }
  try {
    const url = new URL(request.url);
    if (url.origin !== self.location.origin) {
      return model.canonicalLanguage;
    }
    const firstSegment = decodeURIComponent(url.pathname.split("/")[1] || "");
    if (/^[a-z]{2,3}(?:-[a-z0-9]{2,8})*$/.test(firstSegment)) {
      if (
        model.locales.has(firstSegment) ||
        model.locales.has(firstSegment.split("-", 1)[0])
      ) {
        return firstSegment;
      }
    }
  } catch (error) {
    console.warn("PWA offline request locale is invalid", error);
  }
  return model.canonicalLanguage;
}

function escapeHtmlText(value) {
  return value.replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[character]);
}

function freshnessInlineStyle() {
  return (
    '<style id="templates-freshness-status-inline-style">' +
    '#templates-freshness-status{position:fixed;inset-block-start:0;inset-inline:0;z-index:1000;' +
    'box-sizing:border-box;width:100%;margin:0;padding:.55rem .8rem;border-block:.125rem solid currentColor;' +
    'background:Canvas;color:CanvasText;font:normal .8rem/1.35 system-ui,sans-serif;text-align:center}' +
    '#templates-freshness-status strong{font-weight:700}' +
    '#templates-freshness-status .freshness-status__reload{margin-inline-start:.35rem;padding:.15rem .5rem;' +
    'border:.0625rem solid currentColor;border-radius:.25rem;background:transparent;color:inherit;font:inherit;cursor:pointer}' +
    '#templates-freshness-status .freshness-status__reload:focus-visible{outline:.125rem solid currentColor;outline-offset:.125rem}' +
    '@media(max-width:800px){#templates-freshness-status{padding-inline:.55rem;font-size:.75rem}}' +
    '</style>'
  );
}

function freshnessNoticeHtml(state, strings) {
  let className;
  let message;
  const savedCopy = escapeHtmlText(strings.saved_copy);
  if (state === "checking") {
    className = "freshness-status freshness-status--checking";
    message = `<strong>${savedCopy}</strong> ${escapeHtmlText(strings.checking)}`;
  } else if (state === "cached-unverified") {
    className = "freshness-status freshness-status--cached-unverified";
    message = `<strong>${savedCopy}</strong> ${escapeHtmlText(strings.unverified)}`;
  } else {
    return undefined;
  }
  return (
    freshnessInlineStyle() +
    '<aside id="templates-freshness-status" ' +
    `class="${className}" data-freshness-state="${state}" ` +
    'role="status" aria-live="polite">' +
    message +
    "</aside>"
  );
}

async function offlineResponse(request) {
  const model = await loadSiteChromeLocales();
  const language = requestLanguage(model, request);
  const strings = pwaFreshnessStrings(model, language);
  const message = strings?.offline_unavailable || "Offline.";
  return new Response(`${message}\n`, {
    status: 503,
    statusText: "Service Unavailable",
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
}

function isDocumentRequest(request, url) {
  if (url.pathname.startsWith("/repository-trees/previews/")) {
    return false;
  }
  if (request.mode === "navigate") {
    return true;
  }
  if (request.destination !== "") {
    return false;
  }
  const accept = request.headers.get("Accept") || "";
  if (accept.toLowerCase().includes("text/html")) {
    return true;
  }
  const pathname = url.pathname;
  if (pathname.endsWith("/") || pathname.endsWith(".html")) {
    return true;
  }
  const lastSegment = pathname.slice(pathname.lastIndexOf("/") + 1);
  return lastSegment.length > 0 && !lastSegment.includes(".");
}

function fetchFreshDocument(request) {
  return fetch(request, { cache: "no-cache" });
}

function isCacheableDocumentResponse(response) {
  if (response.status !== 200 || !response.url) {
    return false;
  }
  try {
    if (new URL(response.url).origin !== self.location.origin) {
      return false;
    }
  } catch (error) {
    console.warn("PWA document response URL is invalid", error);
    return false;
  }
  const contentType = response.headers.get("Content-Type") || "";
  return contentType.toLowerCase().includes("text/html");
}

function beginDocumentRequest() {
  nextDocumentRequestGeneration += 1;
  return nextDocumentRequestGeneration;
}

function documentStateKey(urlString) {
  try {
    const url = new URL(urlString);
    if (url.origin !== self.location.origin) {
      return undefined;
    }
    url.hash = "";
    return url.href;
  } catch (error) {
    return undefined;
  }
}

function rememberBounded(map, key, value) {
  if (!key) {
    return false;
  }
  const previous = map.get(key);
  if (
    previous &&
    Number.isSafeInteger(previous.generation) &&
    previous.generation > value.generation
  ) {
    return false;
  }
  map.delete(key);
  map.set(key, value);
  while (map.size > MAX_REMEMBERED_FRESHNESS_STATES) {
    map.delete(map.keys().next().value);
  }
  return true;
}

function freshnessClientId(event) {
  if (event.request.mode === "navigate") {
    return event.resultingClientId || event.clientId || "";
  }
  return event.clientId || "";
}

function rememberDocumentFreshnessState(event, state, generation) {
  const urlKey = documentStateKey(event.request.url);
  if (!urlKey) {
    return false;
  }
  return rememberBounded(documentFreshnessStates, urlKey, {
    state,
    generation,
    urlKey,
  });
}

function rememberFreshnessState(event, state, generation) {
  const urlKey = documentStateKey(event.request.url);
  if (!urlKey) {
    return false;
  }
  const value = { state, generation, urlKey };
  const documentRemembered = rememberBounded(
    documentFreshnessStates,
    urlKey,
    value
  );
  const clientId = freshnessClientId(event);
  const clientRemembered = clientId
    ? rememberBounded(clientFreshnessStates, clientId, value)
    : false;
  return documentRemembered || clientRemembered;
}

function forgetFreshnessStateThroughGeneration(map, key, urlKey, generation) {
  if (!key || !urlKey) {
    return;
  }
  const stored = map.get(key);
  if (!stored || stored.urlKey !== urlKey) {
    return;
  }
  if (
    !Number.isSafeInteger(stored.generation) ||
    stored.generation <= generation
  ) {
    map.delete(key);
  }
}

function forgetRequestFreshnessStateThroughGeneration(event, generation) {
  const stateKey = documentStateKey(event.request.url);
  forgetFreshnessStateThroughGeneration(
    clientFreshnessStates,
    freshnessClientId(event),
    stateKey,
    generation
  );
  forgetFreshnessStateThroughGeneration(
    documentFreshnessStates,
    stateKey,
    stateKey,
    generation
  );
}

function recordAuthoritativeDeletion(request, generation) {
  const key = request.url;
  const appliedGeneration = documentCacheMutationGenerations.get(key) || 0;
  if (generation < appliedGeneration) {
    return false;
  }
  documentCacheMutationGenerations.set(key, generation);
  authoritativeDocumentDeletions.set(key, generation);
  return true;
}

function enqueueDocumentCacheMutation(request, generation, operation) {
  const key = request.url;
  const previous = documentCacheMutationQueues.get(key) || Promise.resolve();
  const next = previous.catch(() => undefined).then(async () => {
    const appliedGeneration = documentCacheMutationGenerations.get(key) || 0;
    if (generation < appliedGeneration) {
      return false;
    }
    const result = await operation();
    documentCacheMutationGenerations.set(key, generation);
    return result;
  });
  documentCacheMutationQueues.set(key, next);
  return next.finally(() => {
    if (documentCacheMutationQueues.get(key) === next) {
      documentCacheMutationQueues.delete(key);
    }
  });
}

async function cacheVerifiedDocument(request, cachedResponse, generation) {
  try {
    const written = await enqueueDocumentCacheMutation(request, generation, async () => {
      const cache = await caches.open(DOCUMENT_CACHE_NAME);
      await cache.put(request, cachedResponse);
      return true;
    });
    if (written) {
      const deletionGeneration = authoritativeDocumentDeletions.get(request.url) || 0;
      if (generation >= deletionGeneration) {
        authoritativeDocumentDeletions.delete(request.url);
      }
    }
    return written;
  } catch (error) {
    console.warn("PWA document cache update failed", error);
    return false;
  }
}

async function deleteCachedDocument(request, generation) {
  return await enqueueDocumentCacheMutation(request, generation, async () => {
    const cache = await caches.open(DOCUMENT_CACHE_NAME);
    return await cache.delete(request);
  });
}

async function clearAuthoritativeCachedDocument(request, generation) {
  recordAuthoritativeDeletion(request, generation);
  try {
    await deleteCachedDocument(request, generation);
  } catch (error) {
    console.warn("PWA authoritative document cache deletion failed", error);
    try {
      await caches.delete(DOCUMENT_CACHE_NAME);
    } catch (cleanupError) {
      console.warn("PWA document cache namespace cleanup failed", cleanupError);
    }
  }
}

async function lookupCachedDocument(request) {
  try {
    if (authoritativeDocumentDeletions.has(request.url)) {
      return undefined;
    }
    const cache = await caches.open(DOCUMENT_CACHE_NAME);
    return await cache.match(request);
  } catch (error) {
    console.warn("PWA document cache lookup failed", error);
    return undefined;
  }
}

function injectCachedDocumentNotice(source, state, strings) {
  const notice = freshnessNoticeHtml(state, strings);
  if (!notice) {
    return undefined;
  }
  const htmlOpenings = [...source.matchAll(/<html\b[^>]*>/gi)];
  const bodyOpenings = [...source.matchAll(/<body\b[^>]*>/gi)];
  const bodyClosures = [...source.matchAll(/<\/body\s*>/gi)];
  if (
    htmlOpenings.length !== 1 ||
    bodyOpenings.length !== 1 ||
    bodyClosures.length !== 1
  ) {
    console.warn("PWA cached document body boundary is ambiguous");
    return undefined;
  }
  const htmlOpening = htmlOpenings[0];
  const bodyOpening = bodyOpenings[0];
  const bodyOpeningEnd = bodyOpening.index + bodyOpening[0].length;
  if (bodyOpeningEnd > bodyClosures[0].index || htmlOpening.index > bodyOpening.index) {
    console.warn("PWA cached document body boundary is invalid");
    return undefined;
  }
  const htmlOpeningEnd = htmlOpening.index + htmlOpening[0].length;
  const marker = ` data-templates-cached-fallback="true" data-templates-freshness-state="${state}"`;
  const withMarker =
    source.slice(0, htmlOpeningEnd - 1) + marker + ">" + source.slice(htmlOpeningEnd);
  const shiftedBodyOpeningEnd = bodyOpeningEnd + marker.length;
  return (
    withMarker.slice(0, shiftedBodyOpeningEnd) +
    notice +
    withMarker.slice(shiftedBodyOpeningEnd)
  );
}

async function decorateCachedDocument(response, request, state) {
  const contentType = response.headers.get("Content-Type") || "";
  if (!contentType.toLowerCase().includes("text/html")) {
    return undefined;
  }
  if (response.url && response.url !== request.url) {
    console.warn("PWA cached redirect fallback rejected", response.url, request.url);
    return undefined;
  }
  if (state !== "checking" && state !== "cached-unverified") {
    return undefined;
  }
  let source;
  try {
    source = await response.text();
  } catch (error) {
    console.warn("PWA cached document read failed", error);
    return undefined;
  }
  const model = await loadSiteChromeLocales();
  const language = htmlLanguage(source);
  const strings = pwaFreshnessStrings(model, language);
  if (!strings) {
    return undefined;
  }
  const decorated = injectCachedDocumentNotice(source, state, strings);
  if (decorated === undefined) {
    return undefined;
  }
  const headers = new Headers(response.headers);
  for (const name of ["Content-Encoding", "Content-Length", "ETag", "Last-Modified"]) {
    headers.delete(name);
  }
  headers.set("Cache-Control", "no-store");
  headers.set("X-Templates-Freshness", state);
  return new Response(decorated, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

async function cachedDocumentFallback(request, state) {
  const response = await lookupCachedDocument(request);
  if (!response) {
    return undefined;
  }
  return await decorateCachedDocument(response, request, state);
}

function freshnessMessage(event, state, generation, awaitingCommit) {
  return {
    type: "templates:freshness-state",
    state,
    url: event.request.url,
    requestGeneration: generation,
    workerInstanceId: WORKER_INSTANCE_ID,
    awaitingCommit,
  };
}

async function postFreshnessState(event, state, generation, requireAcknowledgement) {
  const message = freshnessMessage(
    event,
    state,
    generation,
    requireAcknowledgement
  );
  const targetKey = documentStateKey(event.request.url);
  const clientId = freshnessClientId(event);
  let client;
  if (clientId) {
    try {
      client = await self.clients.get(clientId);
    } catch (error) {
      console.warn("PWA freshness client lookup failed", error);
    }
  }
  if (
    !requireAcknowledgement &&
    client &&
    documentStateKey(client.url) !== targetKey
  ) {
    client = undefined;
  }
  if (!client || typeof client.postMessage !== "function") {
    return !requireAcknowledgement;
  }
  if (!requireAcknowledgement) {
    client.postMessage(message);
    return true;
  }
  return await new Promise((resolve) => {
    const channel = new MessageChannel();
    let settled = false;
    const finish = (acknowledged) => {
      if (settled) {
        return;
      }
      settled = true;
      clearTimeout(timer);
      channel.port1.close();
      resolve(acknowledged);
    };
    const timer = setTimeout(() => finish(false), FRESHNESS_UI_ACK_TIMEOUT_MS);
    channel.port1.onmessage = (messageEvent) => {
      const data = messageEvent.data;
      finish(
        data?.type === "templates:freshness-state-applied" &&
          data.state === state &&
          data.requestGeneration === generation &&
          data.workerInstanceId === WORKER_INSTANCE_ID
      );
    };
    try {
      client.postMessage(message, [channel.port2]);
    } catch (error) {
      console.warn("PWA freshness state notification failed", error);
      finish(false);
    }
  });
}

async function publishFreshnessState(
  event,
  state,
  generation,
  requireAcknowledgement = false
) {
  if (!rememberFreshnessState(event, state, generation)) {
    return !requireAcknowledgement;
  }
  if (event.request.mode === "navigate" && requireAcknowledgement) {
    return true;
  }
  return await postFreshnessState(
    event,
    state,
    generation,
    requireAcknowledgement
  );
}

async function notifyInstantNavigationCommit(event, representation, generation) {
  if (event.request.mode === "navigate" || !event.clientId) {
    return;
  }
  try {
    const client = await self.clients.get(event.clientId);
    if (!client || typeof client.postMessage !== "function") {
      return;
    }
    client.postMessage({
      type: "templates:document-commit",
      representation,
      url: event.request.url,
      requestGeneration: generation,
      workerInstanceId: WORKER_INSTANCE_ID,
    });
  } catch (error) {
    console.warn("PWA document commit notification failed", error);
  }
}

function extractMetaAttributes(tag) {
  const attributes = new Map();
  const pattern = /([^\s=/>]+)\s*=\s*(?:(["'])(.*?)\2|([^\s/>]+))/g;
  let match;
  while ((match = pattern.exec(tag)) !== null) {
    const name = match[1].toLowerCase();
    const value = match[3] ?? match[4];
    if (!attributes.has(name)) {
      attributes.set(name, value);
    } else {
      attributes.set(name, undefined);
    }
  }
  return attributes;
}

async function readSiteRevision(response) {
  try {
    let source = await response.text();
    source = source.replace(
      /<(script|style)\b[^>]*>[\s\S]*?<\/\1\s*>/gi,
      ""
    );
    source = source.replace(/<!--[\s\S]*?-->/g, "");
    const headMatch = source.match(/<head\b[^>]*>([\s\S]*?)<\/head>/i);
    source = headMatch ? headMatch[1] : source;
    const revisions = [];
    const tags = source.match(/<meta\b[^>]*>/gi) || [];
    for (const tag of tags) {
      const attributes = extractMetaAttributes(tag);
      if (attributes.get("name")?.toLowerCase() !== "templates-site-revision") {
        continue;
      }
      const content = attributes.get("content");
      if (typeof content !== "string" || !/^[0-9a-f]{40}$/i.test(content)) {
        return undefined;
      }
      revisions.push(content.toLowerCase());
    }
    return revisions.length === 1 ? revisions[0] : undefined;
  } catch (error) {
    console.warn("PWA document revision read failed", error);
    return undefined;
  }
}

function startDocumentNetworkRequest(request) {
  return fetchFreshDocument(request).then(
    (response) => ({ kind: "response", response }),
    (error) => ({ kind: "error", error })
  );
}

function softTimeoutSignal() {
  return new Promise((resolve) => {
    setTimeout(() => resolve({ kind: "soft-timeout" }), DOCUMENT_SOFT_TIMEOUT_MS);
  });
}

async function fallbackForCompletedFailure(event, generation, response) {
  const cached = await cachedDocumentFallback(
    event.request,
    "cached-unverified"
  );
  if (!cached) {
    return response || (await offlineResponse(event.request));
  }
  if (event.request.mode === "navigate") {
    rememberFreshnessState(event, "cached-unverified", generation);
    return cached;
  }
  const acknowledged = await publishFreshnessState(
    event,
    "cached-unverified",
    generation,
    true
  );
  if (!acknowledged) {
    return response || (await offlineResponse(event.request));
  }
  return cached;
}

async function handleCompletedDocumentNetwork(
  event,
  outcome,
  generation,
  registerBackgroundTask
) {
  const request = event.request;
  if (outcome.kind === "error") {
    return await fallbackForCompletedFailure(
      event,
      generation,
      undefined
    );
  }

  const response = outcome.response;
  if (response.status === 404 || response.status === 410) {
    await clearAuthoritativeCachedDocument(request, generation);
    forgetRequestFreshnessStateThroughGeneration(event, generation);
    await notifyInstantNavigationCommit(event, "network", generation);
    return response;
  }
  if (response.status >= 500) {
    return await fallbackForCompletedFailure(
      event,
      generation,
      response
    );
  }
  if (response.status >= 400) {
    forgetRequestFreshnessStateThroughGeneration(event, generation);
    await notifyInstantNavigationCommit(event, "network", generation);
    return response;
  }
  if (isCacheableDocumentResponse(response)) {
    registerBackgroundTask(
      cacheVerifiedDocument(request, response.clone(), generation)
    );
    rememberFreshnessState(event, "verified-current", generation);
  }
  await notifyInstantNavigationCommit(event, "network", generation);
  return response;
}

async function convergeAfterChecking(
  event,
  networkOutcomePromise,
  previousCachedResponse,
  generation
) {
  const request = event.request;
  const outcome = await networkOutcomePromise;
  if (outcome.kind === "error") {
    await publishFreshnessState(
      event,
      "cached-unverified",
      generation,
      false
    );
    return;
  }

  const response = outcome.response;
  if (response.status === 404 || response.status === 410) {
    await clearAuthoritativeCachedDocument(request, generation);
    await publishFreshnessState(
      event,
      "update-available",
      generation,
      false
    );
    return;
  }
  if (response.status >= 400) {
    await publishFreshnessState(
      event,
      "cached-unverified",
      generation,
      false
    );
    return;
  }
  if (!isCacheableDocumentResponse(response)) {
    await publishFreshnessState(
      event,
      "update-available",
      generation,
      false
    );
    return;
  }

  const previousRevisionPromise = readSiteRevision(
    previousCachedResponse.clone()
  );
  const nextRevisionPromise = readSiteRevision(response.clone());
  const cacheTask = cacheVerifiedDocument(request, response.clone(), generation);
  const [previousRevision, nextRevision] = await Promise.all([
    previousRevisionPromise,
    nextRevisionPromise,
    cacheTask,
  ]);
  const state =
    previousRevision &&
    nextRevision &&
    previousRevision === nextRevision
      ? "verified-current"
      : "update-available";
  await publishFreshnessState(event, state, generation, false);
}

async function fetchDocumentNetworkFirst(event, registerBackgroundTask) {
  const generation = beginDocumentRequest();
  const networkOutcomePromise = startDocumentNetworkRequest(event.request);
  const first = await Promise.race([
    networkOutcomePromise,
    softTimeoutSignal(),
  ]);
  if (first.kind !== "soft-timeout") {
    return await handleCompletedDocumentNetwork(
      event,
      first,
      generation,
      registerBackgroundTask
    );
  }

  const cachedLookupPromise = lookupCachedDocument(event.request).then(
    (response) => ({ kind: "cached", response })
  );
  const afterTimeout = await Promise.race([
    networkOutcomePromise,
    cachedLookupPromise,
  ]);
  if (afterTimeout.kind !== "cached") {
    return await handleCompletedDocumentNetwork(
      event,
      afterTimeout,
      generation,
      registerBackgroundTask
    );
  }
  if (!afterTimeout.response) {
    return await handleCompletedDocumentNetwork(
      event,
      await networkOutcomePromise,
      generation,
      registerBackgroundTask
    );
  }

  const checkingResponse = await decorateCachedDocument(
    afterTimeout.response.clone(),
    event.request,
    "checking"
  );
  if (!checkingResponse) {
    return await handleCompletedDocumentNetwork(
      event,
      await networkOutcomePromise,
      generation,
      registerBackgroundTask
    );
  }

  if (event.request.mode === "navigate") {
    rememberFreshnessState(event, "checking", generation);
  } else {
    const checkingAcknowledgement = publishFreshnessState(
      event,
      "checking",
      generation,
      true
    );
    const gate = await Promise.race([
      networkOutcomePromise.then((outcome) => ({
        kind: "network",
        outcome,
      })),
      checkingAcknowledgement.then((acknowledged) => ({
        kind: "acknowledgement",
        acknowledged,
      })),
    ]);
    if (gate.kind === "network") {
      return await handleCompletedDocumentNetwork(
        event,
        gate.outcome,
        generation,
        registerBackgroundTask
      );
    }
    if (!gate.acknowledged) {
      return await handleCompletedDocumentNetwork(
        event,
        await networkOutcomePromise,
        generation,
        registerBackgroundTask
      );
    }
  }

  registerBackgroundTask(
    convergeAfterChecking(
      event,
      networkOutcomePromise,
      afterTimeout.response.clone(),
      generation
    )
  );
  return checkingResponse;
}

function respondWithDocumentNetworkFirst(event) {
  let backgroundTask = Promise.resolve();
  const registerBackgroundTask = (task) => {
    backgroundTask = Promise.all([backgroundTask, Promise.resolve(task)]);
  };
  const responsePromise = fetchDocumentNetworkFirst(
    event,
    registerBackgroundTask
  );
  const lifetimePromise = responsePromise
    .then(
      () => backgroundTask,
      () => backgroundTask
    )
    .catch((error) => {
      console.warn("PWA document lifetime task failed", error);
    });
  event.waitUntil(lifetimePromise);
  event.respondWith(responsePromise);
}

function beginGlossaryRequest() {
  nextGlossaryRequestGeneration += 1;
  return nextGlossaryRequestGeneration;
}

function isCacheableGlossaryResponse(response) {
  if (response.status !== 200 || !response.url) {
    return false;
  }
  try {
    if (new URL(response.url).origin !== self.location.origin) {
      return false;
    }
  } catch (error) {
    console.warn("PWA Glossary response URL is invalid", error);
    return false;
  }
  const contentType = (response.headers.get("Content-Type") || "").toLowerCase();
  return contentType.includes("application/json") || contentType.includes("+json");
}

function recordAuthoritativeGlossaryDeletion(generation) {
  if (generation < glossaryCacheMutationGeneration) {
    return false;
  }
  authoritativeGlossaryDeletionGeneration = Math.max(
    authoritativeGlossaryDeletionGeneration,
    generation
  );
  return true;
}

function enqueueGlossaryCacheMutation(generation, operation) {
  const next = glossaryCacheMutationQueue.catch(() => undefined).then(async () => {
    if (generation < glossaryCacheMutationGeneration) {
      return false;
    }
    const result = await operation();
    glossaryCacheMutationGeneration = generation;
    return result;
  });
  glossaryCacheMutationQueue = next;
  return next;
}

async function cacheVerifiedGlossaryModel(request, response, generation) {
  try {
    const written = await enqueueGlossaryCacheMutation(generation, async () => {
      const cache = await caches.open(GLOSSARY_CACHE_NAME);
      await cache.put(request, response);
      return true;
    });
    if (written && generation >= authoritativeGlossaryDeletionGeneration) {
      authoritativeGlossaryDeletionGeneration = 0;
    }
  } catch (error) {
    console.warn("PWA Glossary cache update failed", error);
  }
}

async function deleteCachedGlossaryModel(request, generation) {
  return await enqueueGlossaryCacheMutation(generation, async () => {
    const cache = await caches.open(GLOSSARY_CACHE_NAME);
    return await cache.delete(request);
  });
}

async function decorateCachedGlossaryModel(response, request) {
  if (response.status !== 200) {
    return undefined;
  }
  const contentType = (response.headers.get("Content-Type") || "").toLowerCase();
  if (!contentType.includes("application/json") && !contentType.includes("+json")) {
    return undefined;
  }
  if (response.url && response.url !== request.url) {
    console.warn("PWA cached Glossary redirect fallback rejected", response.url, request.url);
    return undefined;
  }
  let body;
  try {
    body = await response.arrayBuffer();
  } catch (error) {
    console.warn("PWA cached Glossary read failed", error);
    return undefined;
  }
  const headers = new Headers(response.headers);
  for (const name of ["Content-Encoding", "Content-Length", "ETag", "Last-Modified"]) {
    headers.delete(name);
  }
  headers.set("Cache-Control", "no-store");
  headers.set("X-Templates-Freshness", "cached-unverified");
  return new Response(body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

async function cachedGlossaryFallback(request) {
  try {
    if (request.headers.get(GLOSSARY_CACHED_ACCEPT_HEADER) !== "1") {
      return undefined;
    }
    if (authoritativeGlossaryDeletionGeneration > 0) {
      return undefined;
    }
    const cache = await caches.open(GLOSSARY_CACHE_NAME);
    const response = await cache.match(request);
    if (!response) {
      return undefined;
    }
    return await decorateCachedGlossaryModel(response, request);
  } catch (error) {
    console.warn("PWA Glossary cache lookup failed", error);
    return undefined;
  }
}

async function fetchGlossaryNetworkFirst(request, registerBackgroundTask) {
  const generation = beginGlossaryRequest();
  try {
    const response = await fetch(request, { cache: "no-cache" });
    if (response.status === 404 || response.status === 410) {
      if (recordAuthoritativeGlossaryDeletion(generation)) {
        registerBackgroundTask(
          deleteCachedGlossaryModel(request, generation).catch(async (error) => {
            console.warn("PWA authoritative Glossary cache deletion failed", error);
            try {
              await caches.delete(GLOSSARY_CACHE_NAME);
            } catch (cleanupError) {
              console.warn("PWA Glossary cache namespace cleanup failed", cleanupError);
            }
          })
        );
      }
      return response;
    }
    if (response.status >= 500) {
      return (await cachedGlossaryFallback(request)) || response;
    }
    if (isCacheableGlossaryResponse(response)) {
      registerBackgroundTask(
        cacheVerifiedGlossaryModel(request, response.clone(), generation)
      );
    }
    return response;
  } catch (error) {
    const cached = await cachedGlossaryFallback(request);
    if (cached) {
      return cached;
    }
    throw error;
  }
}

function respondWithGlossaryNetworkFirst(event) {
  let backgroundTask = Promise.resolve();
  const registerBackgroundTask = (task) => {
    backgroundTask = Promise.all([backgroundTask, Promise.resolve(task)]);
  };
  const responsePromise = fetchGlossaryNetworkFirst(event.request, registerBackgroundTask);
  const lifetimePromise = responsePromise
    .then(
      () => backgroundTask,
      () => backgroundTask
    )
    .catch((error) => {
      console.warn("PWA Glossary lifetime task failed", error);
    });
  event.waitUntil(lifetimePromise);
  event.respondWith(responsePromise);
}

async function refreshStaticAsset(request) {
  const response = await fetch(request, { cache: "no-cache" });
  if (response.ok) {
    try {
      const cache = await caches.open(CACHE_NAME);
      await cache.put(request, response.clone());
    } catch (error) {
      console.warn("PWA static asset cache refresh failed", error);
    }
  }
  return response;
}

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter(
              (key) =>
                (key.startsWith("templates-portal-shell-") && key !== CACHE_NAME) ||
                (key.startsWith("templates-portal-glossary-") &&
                  key !== GLOSSARY_CACHE_NAME)
            )
            .map((key) => caches.delete(key))
        )
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener("message", (event) => {
  if (!event.source || typeof event.source.postMessage !== "function") {
    return;
  }
  if (event.data?.type === "templates:get-freshness-capabilities") {
    event.source.postMessage({
      type: "templates:freshness-capabilities",
      states: FRESHNESS_STATES,
      siteVersionUrl: "/site-version.json",
      documentCacheName: DOCUMENT_CACHE_NAME,
      glossaryCacheName: GLOSSARY_CACHE_NAME,
      glossaryModelUrl: GLOSSARY_MODEL_PATH,
      softTimeoutMs: DOCUMENT_SOFT_TIMEOUT_MS,
      workerInstanceId: WORKER_INSTANCE_ID,
    });
    return;
  }
  if (event.data?.type === "templates:get-current-freshness-state") {
    const sourceId = event.source.id || "";
    const stateKey = documentStateKey(event.data.url || "");
    const clientState = clientFreshnessStates.get(sourceId);
    let state =
      clientState && clientState.urlKey === stateKey
        ? clientState
        : stateKey
          ? documentFreshnessStates.get(stateKey)
          : undefined;
    if (!state && stateKey && event.data.currentState === "checking") {
      const recoveryGeneration = Math.max(nextDocumentRequestGeneration, 1);
      nextDocumentRequestGeneration = recoveryGeneration;
      state = {
        state: "cached-unverified",
        generation: recoveryGeneration,
        urlKey: stateKey,
      };
      rememberBounded(documentFreshnessStates, stateKey, state);
      if (sourceId) {
        rememberBounded(clientFreshnessStates, sourceId, state);
      }
    }
    if (state) {
      event.source.postMessage({
        type: "templates:freshness-state",
        state: state.state,
        url: event.data.url || "",
        requestGeneration: state.generation,
        workerInstanceId: WORKER_INSTANCE_ID,
        awaitingCommit: false,
      });
    }
  }
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") {
    return;
  }

  let url;
  try {
    url = new URL(event.request.url);
  } catch (error) {
    console.warn("PWA fetch request URL is invalid", error);
    return;
  }
  if (url.origin !== self.location.origin) {
    return;
  }

  if (url.pathname === GLOSSARY_MODEL_PATH) {
    respondWithGlossaryNetworkFirst(event);
    return;
  }

  if (isDocumentRequest(event.request, url)) {
    respondWithDocumentNetworkFirst(event);
    return;
  }

  if (STATIC_ASSETS.includes(url.pathname)) {
    const refresh = refreshStaticAsset(event.request);
    const cached = caches
      .open(CACHE_NAME)
      .then((cache) => cache.match(event.request))
      .catch(() => undefined);
    event.waitUntil(refresh.catch(() => undefined));
    event.respondWith(
      cached
        .then((response) => response || refresh)
        .catch(() => offlineResponse(event.request))
    );
  }
});