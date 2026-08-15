const CACHE_NAME = "templates-portal-shell-v4";
const DOCUMENT_CACHE_NAME = "templates-portal-documents-v1";
const GLOSSARY_CACHE_NAME = "templates-portal-glossary-v1";
const GLOSSARY_MODEL_PATH = "/glossary/index.json";
const GLOSSARY_CACHED_ACCEPT_HEADER = "X-Templates-Glossary-Accepts-Cached";
const STATIC_ASSETS = [
  "/app.webmanifest",
  "/icon.svg",
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
  "/javascripts/glossary-inline.js"
];
const FRESHNESS_STATES = Object.freeze([
  "verified-current",
  "checking",
  "cached-unverified",
  "update-available",
]);
const CACHED_DOCUMENT_NOTICE =
  '<style id="templates-freshness-status-inline-style">' +
  '#templates-freshness-status{position:fixed;inset-block-start:0;inset-inline:0;z-index:1000;' +
  'box-sizing:border-box;width:100%;margin:0;padding:.55rem .8rem;border-block:.125rem solid currentColor;' +
  'background:Canvas;color:CanvasText;font:normal .8rem/1.35 system-ui,sans-serif;text-align:center}' +
  '#templates-freshness-status strong{font-weight:700}' +
  '@media(max-width:800px){#templates-freshness-status{padding-inline:.55rem;font-size:.75rem}}' +
  '</style>' +
  '<aside id="templates-freshness-status" ' +
  'class="freshness-status freshness-status--cached" ' +
  'data-freshness-state="cached-unverified" role="status" aria-live="polite">' +
  '<strong>Saved copy.</strong> The latest version could not be verified.' +
  "</aside>";
const FRESHNESS_UI_ACK_TIMEOUT_MS = 500;
const documentCacheMutationQueues = new Map();
const documentCacheMutationGenerations = new Map();
const authoritativeDocumentDeletions = new Map();
let nextDocumentRequestGeneration = 0;
let nextGlossaryRequestGeneration = 0;
let glossaryCacheMutationGeneration = 0;
let glossaryCacheMutationQueue = Promise.resolve();
let authoritativeGlossaryDeletionGeneration = 0;

function offlineResponse() {
  return new Response("This page is unavailable while offline.\n", {
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
  if (response.status !== 200) {
    return false;
  }
  if (!response.url) {
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
  } catch (error) {
    console.warn("PWA document cache update failed", error);
  }
}

async function deleteCachedDocument(request, generation) {
  return await enqueueDocumentCacheMutation(request, generation, async () => {
    const cache = await caches.open(DOCUMENT_CACHE_NAME);
    return await cache.delete(request);
  });
}

function injectCachedDocumentNotice(source) {
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
  const withMarker =
    source.slice(0, htmlOpeningEnd - 1) +
    ' data-templates-cached-fallback="true">' +
    source.slice(htmlOpeningEnd);
  const shiftedBodyOpeningEnd =
    bodyOpeningEnd + ' data-templates-cached-fallback="true"'.length;
  return (
    withMarker.slice(0, shiftedBodyOpeningEnd) +
    CACHED_DOCUMENT_NOTICE +
    withMarker.slice(shiftedBodyOpeningEnd)
  );
}

async function decorateCachedDocument(response, request) {
  const contentType = response.headers.get("Content-Type") || "";
  if (!contentType.toLowerCase().includes("text/html")) {
    return undefined;
  }

  if (response.url && response.url !== request.url) {
    console.warn("PWA cached redirect fallback rejected", response.url, request.url);
    return undefined;
  }

  let source;
  try {
    source = await response.text();
  } catch (error) {
    console.warn("PWA cached document read failed", error);
    return undefined;
  }

  const decorated = injectCachedDocumentNotice(source);
  if (decorated === undefined) {
    return undefined;
  }
  const headers = new Headers(response.headers);
  for (const name of ["Content-Encoding", "Content-Length", "ETag", "Last-Modified"]) {
    headers.delete(name);
  }
  headers.set("Cache-Control", "no-store");
  headers.set("X-Templates-Freshness", "cached-unverified");
  return new Response(decorated, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

async function cachedDocumentFallback(request) {
  try {
    if (authoritativeDocumentDeletions.has(request.url)) {
      return undefined;
    }
    const cache = await caches.open(DOCUMENT_CACHE_NAME);
    const response = await cache.match(request);
    if (!response) {
      return undefined;
    }
    return await decorateCachedDocument(response, request);
  } catch (error) {
    console.warn("PWA document cache lookup failed", error);
    return undefined;
  }
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
    });
  } catch (error) {
    console.warn("PWA document commit notification failed", error);
  }
}

async function notifyInstantNavigationState(
  event,
  state,
  requireAcknowledgement = false,
  generation = 0
) {
  if (event.request.mode === "navigate") {
    return true;
  }
  if (!event.clientId) {
    return !requireAcknowledgement;
  }

  let client;
  try {
    client = await self.clients.get(event.clientId);
  } catch (error) {
    console.warn("PWA freshness client lookup failed", error);
    return !requireAcknowledgement;
  }
  if (!client || typeof client.postMessage !== "function") {
    return !requireAcknowledgement;
  }

  const message = {
    type: "templates:freshness-state",
    state,
    url: event.request.url,
    requestGeneration: generation,
  };
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
          data.requestGeneration === generation
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

async function fetchDocumentNetworkFirst(event, registerBackgroundTask) {
  const request = event.request;
  const generation = beginDocumentRequest();
  try {
    const response = await fetchFreshDocument(request);
    if (response.status === 404 || response.status === 410) {
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
      await notifyInstantNavigationCommit(event, "network", generation);
      return response;
    }
    if (response.status >= 500) {
      const cached = await cachedDocumentFallback(request);
      if (!cached) {
        await notifyInstantNavigationCommit(event, "network", generation);
        return response;
      }
      if (
        !(await notifyInstantNavigationState(
          event,
          "cached-unverified",
          true,
          generation
        ))
      ) {
        await notifyInstantNavigationCommit(event, "network", generation);
        return response;
      }
      return cached;
    }
    if (isCacheableDocumentResponse(response)) {
      const cachedResponse = response.clone();
      registerBackgroundTask(cacheVerifiedDocument(request, cachedResponse, generation));
    }
    await notifyInstantNavigationCommit(event, "network", generation);
    return response;
  } catch (error) {
    const cached = await cachedDocumentFallback(request);
    if (!cached) {
      await notifyInstantNavigationCommit(event, "network", generation);
      return offlineResponse();
    }
    if (
      !(await notifyInstantNavigationState(
        event,
        "cached-unverified",
        true,
        generation
      ))
    ) {
      await notifyInstantNavigationCommit(event, "network", generation);
      return offlineResponse();
    }
    return cached;
  }
}

function respondWithDocumentNetworkFirst(event) {
  let backgroundTask = Promise.resolve();
  const registerBackgroundTask = (task) => {
    backgroundTask = Promise.resolve(task);
  };
  const responsePromise = fetchDocumentNetworkFirst(event, registerBackgroundTask);
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
  if (!isCacheableGlossaryResponse(response)) {
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
    backgroundTask = Promise.resolve(task);
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
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS)));
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
  if (
    event.data?.type !== "templates:get-freshness-capabilities" ||
    !event.source ||
    typeof event.source.postMessage !== "function"
  ) {
    return;
  }
  event.source.postMessage({
    type: "templates:freshness-capabilities",
    states: FRESHNESS_STATES,
    siteVersionUrl: "/site-version.json",
    documentCacheName: DOCUMENT_CACHE_NAME,
    glossaryCacheName: GLOSSARY_CACHE_NAME,
    glossaryModelUrl: GLOSSARY_MODEL_PATH,
  });
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
        .catch(() => offlineResponse())
    );
  }
});