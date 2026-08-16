# Freshness identity and cache contract

This document is the normative Site-side contract for identifying the exact
published documentation revision and for communicating document and integrated
Glossary-model freshness to browser clients. It complements `PUBLISHING.md` for
publication provenance and `MAINTENANCE.md` for PWA operation.

## Objective

The documentation portal must distinguish four different facts:

1. which reviewed Git revisions produced a Pages artifact;
2. which Site revision produced a particular generated HTML document;
3. whether a browser has verified that a document response is current; and
4. whether an inline Glossary definition came from the currently verified
   integrated read model or from an explicitly unverified saved copy.

A cached or offline document or Glossary model must never be represented as
network-verified merely because its build revision is known. Build identity is
evidence about the content that was generated; runtime freshness is evidence
about whether the current published response was successfully revalidated.

## Build-time freshness identity

After every human-readable and generated Site surface has been finalized, the
build-provenance step writes `build-provenance.json` and projects the same exact
checked-out revisions into the client-facing `/site-version.json` read model.
The Site and provider revisions are full lowercase 40-character Git commit SHAs
from the actual build checkouts, not mutable branch names, tags, or abbreviated
revisions.

`/site-version.json` uses schema version 1 and records `site_revision`, the
existing deployment timestamp (or null for preview builds), and exact `skill`,
`policy`, and `webapp` revisions. The generator rejects symbolic-link or
non-regular outputs and generated HTML paths.

## Per-document build identity

Every generated HTML page that participates in the normal Site runtime receives
exactly one element in its `<head>`:

```html
<meta name="templates-site-revision" content="<full Site commit SHA>">
```

The value must equal `/site-version.json`'s `site_revision`. Existing conflicting
or duplicate metadata fails the build. Generated HTML with malformed or ambiguous
`<head>` boundaries also fails rather than being heuristically rewritten.
Sandboxed repository-tree previews under `/repository-trees/previews/` are
excluded from both build-time freshness annotation and PWA document handling.

After writing the projection, the build re-reads `/site-version.json` and every
eligible generated HTML page. It verifies the complete canonical JSON payload and
exactly one matching revision meta element before artifact upload can proceed.

## Runtime freshness states

The Site uses the following runtime state vocabulary:

- `verified-current`: the current document or supported read-model request was
  successfully obtained or revalidated from the network;
- `checking`: a stored document is visible while network freshness verification
  is still pending;
- `cached-unverified`: a stored document or explicitly supported read model is
  being used because current network freshness could not be verified;
- `update-available`: a newer or materially different verified response has been
  obtained while an older stored document remains visible.

The Service Worker exposes this vocabulary through the
`templates:get-freshness-capabilities` / `templates:freshness-capabilities`
message contract together with `/site-version.json`, the document-cache
namespace, the Glossary-cache namespace, the integrated Glossary model URL, and
`softTimeoutMs: 1500`. The capability response also identifies the current
Service Worker instance so request-generation ordering cannot be confused across
a normal worker restart. Matching build identity alone never establishes
`verified-current`.

## Runtime document-cache behavior

Normal browser navigations and same-origin document-like instant-navigation
requests remain network-first. Every online document request uses
`fetch(request, { cache: "no-cache" })`, preserving HTTP-cache revalidation.

A successful same-origin HTTP 200 response is cacheable only when its
`Content-Type` contains `text/html`. The response is cloned before asynchronous
cache work begins, so returning the network response does not race with Cache
Storage consumption of the same body stream.

The fetch event registers its document-lifetime promise synchronously inside the
Service Worker event callback, before asynchronous network completion. The
response promise later binds any cache-write or slow-network convergence task
into that already-registered lifetime. Code must not make its first `waitUntil()`
call only after awaiting the network response or the soft timeout; background
cache and convergence work must remain covered by the original trusted event
lifetime.

The runtime document cache is `templates-portal-documents-v1`, independent of the
versioned shell cache. Service Worker activation removes incompatible shell
namespaces but preserves the compatible document namespace.

Cache mutations for one exact request URL are both serialized and ordered by a
request generation allocated before that request begins network I/O. A mutation
from an older generation is discarded after a newer generation has already been
applied. An authoritative 404/410 records its generation before deletion begins,
so a slower HTTP 200 request that started earlier cannot later resurrect the
deleted document. The worker also retains an in-memory authoritative-deletion
tombstone until a newer successful cache write supersedes it; if physical cache
deletion fails, the stale entry therefore remains ineligible for fallback.

Network outcomes have distinct semantics:

- cacheable HTTP 200: return the network response and update the exact document
  cache entry when its request generation is not stale;
- HTTP 404 or 410: mark the request generation authoritative, remove the exact
  cached document before returning the network response, and if entry deletion
  throws attempt to delete the entire document-cache namespace rather than
  knowingly preserve an authoritative stale copy;
- ordinary non-transient 4xx such as 403: return the network response and do not
  fall back to stale documentation when it completes before cached content has
  been exposed;
- HTTP 5xx: return cached documentation only when stale indication can be proven;
  otherwise return the original 5xx;
- network/DNS/TLS/connection failure: return cached documentation only when stale
  indication can be proven; otherwise return the explicit HTTP 503 fallback.

### Slow-network convergence

A document request has a 1500 ms soft timeout. The timeout does not abort, cancel,
or replace the original network request. If the network completes before the
soft timeout, ordinary network-first behavior applies. If no safe stored document
exists when the timeout expires, the browser continues waiting for the original
network result rather than synthesizing an early failure.

If a safe stored document does exist after the timeout, the Site may expose that
stored representation with the explicit `checking` state while the original
network request continues. Full navigation carries `checking` in the decorated
HTML itself. Instant navigation must first apply and acknowledge the persistent
`checking` UI through the same generation-bound `MessageChannel` safety gate used
for `cached-unverified` fallback.

Background completion never replaces the visible document automatically. It
converges the freshness state instead:

- matching cached and network `templates-site-revision` values become
  `verified-current`;
- a different revision, a cache-ineligible successful response, an unextractable
  or ambiguous revision, or authoritative 404/410 becomes `update-available`;
- a network failure or other completed result that cannot verify the visible
  saved representation becomes `cached-unverified`.

`update-available` exposes an explicit Reload action. The user remains in control
of the representation change. The Service Worker reads revision metadata without
assuming HTML attribute order, accepts ordinary quoted or unquoted attribute
values, ignores commented-out metadata, requires one unambiguous valid full SHA,
and fails conservatively to `update-available` when identity cannot be established.

The worker retains a bounded amount of per-document and per-client freshness state
so a page that starts listening after an earlier message can request the current
state with `templates:get-current-freshness-state`. Each state is ordered by the
request generation and scoped to a randomly generated Service Worker instance ID.
A worker restart therefore establishes a new ordering epoch rather than causing a
new low generation to be rejected by an already-open page. Client code also checks
the exact document URL before applying a non-commit freshness update, and a newer
committed network representation retires older convergence for that visible
document. These rules prevent late slow requests from adding or clearing warnings
on a different or newer page.

### Full-navigation stale indication

For a full browser navigation, the cached HTML response itself carries the
freshness indication. The Service Worker requires one unambiguous `<html>` start
tag, one `<body>` start tag, and one closing `</body>` tag. It marks the cached
representation with `data-templates-cached-fallback="true"` and its current
freshness state on `<html>`, and inserts the `templates-freshness-status` element
immediately after the opening `<body>` tag, before later page scripts can execute.
If those boundaries cannot be established consistently, the cached representation
fails closed and is not exposed.

The decorated representation also includes a minimal inline fallback style for
the status element and Reload action. This makes the warning fixed at the top of
standalone pages whose CSP permits their existing inline styles but which do not
load the shared `freshness-status.css`; ordinary Site pages continue to receive
the equivalent shared stylesheet. The inline fallback contains only fixed
Site-owned CSS and no content-derived values.

A full-navigation page may emit Zensical's `document$` event during initial page
setup. `pwa.js` therefore reads the explicit `<html>` cached-representation marker
(and accepts an already present `checking` or `cached-unverified` status as a
defensive fallback), preserves the warning across the initial commit, and consumes
the marker only when that cached commit boundary is observed. The initial event is
not interpreted as proof of fresh content.

### Instant-navigation stale indication, acknowledgement, and commit boundary

A document-like fetch used by instant navigation cannot assume that an indication
embedded in fetched HTML will survive partial-DOM replacement. Before returning
a cached response for such a request, the Service Worker sends the requesting
client a `templates:freshness-state` message carrying `checking` or
`cached-unverified`, the exact request URL, the request generation, the current
worker-instance ID, and a `MessageChannel` acknowledgement port.

Current `pwa.js` applies that state to persistent DOM by creating the same fixed
status element and records a pending commit whose representation is `cached`.
It then replies through the port with `templates:freshness-state-applied`,
echoing the state, request generation, and worker-instance ID. The Service Worker
waits for that exact acknowledgement, with a bounded timeout, before returning
cached HTML.

This acknowledgement is a safety condition, not an optimization. If an older
open page is controlled by the updated worker but still runs a client script that
does not implement the freshness UI, no acknowledgement arrives. The worker then
refuses to expose cached HTML: a network failure returns the explicit 503 and a
transient HTTP 5xx returns the original 5xx. A slow request whose `checking`
acknowledgement cannot be established keeps waiting for the original network
result instead of exposing an unindicated stored document.

Network response completion and document replacement are separate events under
Zensical instant navigation. The worker therefore sends a separate
`templates:document-commit` intent for non-cached network representations. That
message carries the exact URL, representation kind, request generation, and
worker-instance ID, but does not clear an existing warning. `pwa.js` retains only
the newest observed commit generation and waits for Zensical's `document$` event
before acting on the pending representation.

At the document-commit boundary, a committed `cached` representation keeps the
warning and consumes its pending marker. A committed `network` representation
clears the warning. This representation-aware correlation prevents two opposite
failures: a successful fetch that is prefetched or cancelled cannot clear a stale
warning before it is rendered, and a later fresh retry to the same URL cannot be
mistaken for an earlier cancelled cached fallback merely because the URLs match.
An uncorrelated `document$` event alone is never authority to clear the freshness
warning.

This fail-safe ordering deliberately permits an old warning to remain longer than
necessary if a non-Zensical surface cannot expose a document-commit signal. It
never permits stale content to become unindicated merely because a network fetch
finished before the caller replaced the visible DOM.

### Synthetic cached document response

Cached document fallback responses carry `X-Templates-Freshness` with either
`checking` or `cached-unverified`, as appropriate, and `Cache-Control: no-store`.
Because the cached HTML body is modified, `Content-Encoding`, `Content-Length`,
`ETag`, and `Last-Modified` are removed. A cached response that is not HTML,
cannot be read, has a redirected final URL different from the exact request URL,
or lacks the single unambiguous `<html>`/`<body>` structure required for safe
marking and insertion is not used as fallback. Redirects fail closed because
constructing a synthetic decorated `Response` cannot preserve the original
response URL needed for canonical relative-URL resolution.

## Runtime Glossary-model cache behavior

The integrated `/glossary/index.json` read model has a separate runtime cache,
`templates-portal-glossary-v1`. It is deliberately not part of `STATIC_ASSETS`:
online Glossary activation remains network-first and uses `cache: "no-cache"`,
so a previously saved definition is never preferred merely because the shell is
available. The document soft timeout does not implicitly apply to this independent
Glossary route.

A Glossary response is cacheable only when it is same-origin HTTP 200 and its
`Content-Type` is JSON (`application/json` or a `+json` media type). Successful
responses are cloned for asynchronous cache writes while the original network
response is returned immediately. The fetch event binds any resulting cache
mutation to an already-registered lifetime promise, matching the document-cache
lifetime rule.

Because the integrated model has one stable URL, its mutations use one serialized
request-generation sequence. An older cache mutation cannot overwrite a newer
one. HTTP 404/410 is authoritative: its deletion is recorded only if its request
generation is not older than the newest applied cache mutation, and physical
entry deletion is generation-ordered. This prevents both a delayed old 200 from
resurrecting a deleted model and a delayed old 404 from invalidating a newer
verified model. If authoritative deletion cannot remove the entry, the worker
attempts to remove the entire Glossary cache namespace and retains an in-memory
tombstone until a newer successful write supersedes it.

Network outcomes are intentionally analogous to documents but narrower:

- cacheable HTTP 200: return the network model and update the Glossary cache;
- HTTP 404 or 410: treat the absence as authoritative and remove the saved model;
- ordinary non-transient 4xx: return the network response without stale fallback;
- HTTP 5xx: use a saved model only for a freshness-aware Glossary runtime;
  otherwise return the original 5xx;
- network/DNS/TLS/connection failure: use a saved model only for a
  freshness-aware Glossary runtime; otherwise let the request fail so the
  runtime presents its ordinary unavailable-definition state.

A saved Glossary response keeps the exact cached JSON bytes rather than rewriting
the model. The synthetic response carries
`X-Templates-Freshness: cached-unverified` and `Cache-Control: no-store`, and
removes `Content-Encoding`, `Content-Length`, `ETag`, and `Last-Modified` because
a new `Response` object is constructed around those bytes. The inline Glossary
runtime reads the freshness header before displaying a definition and exposes
`Saved glossary data · latest version not verified.` in the same dialog.

Cached Glossary fallback is fail-closed across Service Worker/client-version
boundaries. The current runtime opts in on its same-origin model request with
`X-Templates-Glossary-Accepts-Cached: 1`. The Service Worker refuses cached
Glossary fallback when that request header is absent. Consequently an older open
page that is claimed by the new worker but still runs a runtime that cannot show
the cached-unverified warning receives no saved model. This is the Glossary
counterpart of the document cache's stale-UI acknowledgement requirement, but it
does not require a `MessageChannel`: the Glossary dialog is constructed and its
freshness text is populated before that definition is presented.

## Shell cache behavior

The shell cache is versioned independently and precaches the Site-owned common
assets needed to render previously viewed documentation, including the manifest,
icon, common stylesheets, freshness-status stylesheet, and common local
JavaScript. Exact shell assets continue to use background `cache: "no-cache"`
revalidation when requested.

The Chromium capability checker derives its install-asset preflight directly from
the Service Worker's `STATIC_ASSETS` declaration. A newly added precache asset
therefore cannot be omitted silently from the preflight and leave the browser
waiting on a Service Worker installation that has already failed.

The Glossary cache is versioned independently of both shell and document caches.
Activation may delete older `templates-portal-glossary-*` namespaces when the
Glossary storage/representation contract changes, while preserving the compatible
`templates-portal-documents-v1` document cache. Adding Glossary caching does not
by itself change the shell namespace because the shell cache strategy and stored
shell representation are unchanged.

## Browser regression contract

The Chromium freshness lifecycle verifies at least:

- online v1 -> v2 document revalidation and runtime cache update;
- document-cache survival across a Service Worker shell update;
- an old/unaware controlled client without stale-UI acknowledgement receives 503
  rather than cached HTML during offline instant navigation;
- a current client receives cached v2 only after the persistent stale warning is
  applied and acknowledged;
- committing that cached fallback retains its persistent stale warning;
- an uncommitted ordinary 4xx response does not clear the warning;
- a later verified HTTP 200 response does not clear the warning before the
  corresponding document commit, while the subsequent committed navigation does;
- a cancelled cached navigation followed by a fresh retry to the same URL is
  correlated to the fresh representation rather than the stale URL alone;
- offline full navigation returns cached v2 with exactly one visible stale
  indication and preserves it across the initial document commit;
- the standalone/full-navigation warning remains fixed in the viewport using its
  CSP-compatible inline fallback style even without the shared warning stylesheet;
- an uncached offline request retains explicit 503;
- ordinary 4xx responses never fall back to stale documentation;
- transient 5xx may fall back only with acknowledged stale indication;
- authoritative 404 removes the cached document so later offline access cannot
  resurrect it, including when an older delayed 200 completes afterward;
- a slow cache miss continues waiting for the original network response after the
  1500 ms soft timeout;
- a slow cache hit can expose `checking` without aborting the original network
  request, and background completion converges without replacing visible DOM;
- matching and reversed-order revision metadata converge to `verified-current`,
  while missing/ambiguous revision metadata or a non-HTML success converges to
  `update-available`;
- slow network failure or transient failure after `checking` converges to
  `cached-unverified`;
- direct full navigation can expose its self-marked stored representation without
  requiring a pre-existing client acknowledgement;
- Service Worker restart, previous-document completion, and newer same-URL network
  commit races cannot apply an older freshness conclusion to the visible page;
- Service Worker update propagation, manifest convergence, and the live
  freshness-capability message contract, including `softTimeoutMs`, remain valid.

Glossary-specific regression coverage additionally preserves the dedicated
network-first cache route, generation-ordered authoritative deletion, exact-byte
cached response decoration, freshness-aware client opt-in, and visible
`cached-unverified` dialog state. A future browser-level Glossary cache lifecycle
checker may extend this list without changing the freshness semantics above.

## Evolution rule

Slow-network convergence is part of the active runtime contract. Future tuning may
change timeout values or extend supported read models only if the capability
contract and browser regression evidence are updated together. Such changes must
not turn a soft timeout into cancellation, must not infer freshness from build
identity alone, and must not replace visible document content automatically after
background verification.

Any future change must preserve the central invariant: a document or reader-visible
semantic read model whose current network freshness has not been verified is
visibly identified as unverified before it is presented as ordinary readable
content.
