# Freshness identity and cache contract

This document is the normative Site-side contract for identifying the exact
published documentation revision and for communicating document freshness to
browser clients. It complements `PUBLISHING.md` for publication provenance and
`MAINTENANCE.md` for PWA operation.

## Objective

The documentation portal must distinguish three different facts:

1. which reviewed Git revisions produced a Pages artifact;
2. which Site revision produced a particular generated HTML document; and
3. whether a browser has verified that a document response is current.

A cached or offline document must never be represented as network-verified merely
because its build revision is known. Build identity is evidence about the content
that was generated; runtime freshness is evidence about whether the current
published response was successfully revalidated.

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

The Site reserves the following runtime state vocabulary:

- `verified-current`: the current document request was successfully obtained or
  revalidated from the network;
- `checking`: a stored document is visible while network freshness verification
  is still pending;
- `cached-unverified`: a stored document is visible because current network
  freshness could not be verified;
- `update-available`: a newer verified response has been obtained while an older
  stored document remains visible.

The Service Worker exposes this vocabulary through the
`templates:get-freshness-capabilities` / `templates:freshness-capabilities`
message contract together with `/site-version.json` and the document cache
namespace. Matching build identity alone never establishes `verified-current`.

## Runtime document-cache behavior

Normal browser navigations and same-origin document-like instant-navigation
requests remain network-first. Every online document request uses
`fetch(request, { cache: "no-cache" })`, preserving HTTP-cache revalidation.

A successful same-origin HTTP 200 response is cacheable only when its
`Content-Type` contains `text/html`. The response is cloned before asynchronous
cache work begins, so returning the network response does not race with Cache
Storage consumption of the same body stream.

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
  fails attempt to delete the entire document-cache namespace rather than
  knowingly preserve an authoritative stale copy;
- ordinary non-transient 4xx such as 403: return the network response and do not
  fall back to stale documentation;
- HTTP 5xx: return cached documentation only when stale indication can be proven;
  otherwise return the original 5xx;
- network/DNS/TLS/connection failure: return cached documentation only when stale
  indication can be proven; otherwise return the explicit HTTP 503 fallback.

### Full-navigation stale indication

For a full browser navigation, the cached HTML response itself carries the
freshness indication. The Service Worker inserts an element with
`id="templates-freshness-status"` and
`data-freshness-state="cached-unverified"` immediately before the document's
single unambiguous closing `</body>` tag. If that boundary cannot be established,
the cached representation fails closed and is not exposed.

The decorated representation also includes a minimal inline fallback style for
the status element. This makes the warning fixed at the top of standalone pages
whose CSP permits their existing inline styles but which do not load the shared
`freshness-status.css`; ordinary Site pages continue to receive the equivalent
shared stylesheet. The inline fallback contains only fixed Site-owned CSS and no
content-derived values.

A full-navigation page may emit Zensical's `document$` event during initial page
setup. `pwa.js` therefore recognizes an already embedded `cached-unverified`
status as belonging to the initial cached representation and preserves it across
that initial commit rather than interpreting the event as proof of fresh content.

### Instant-navigation stale indication, acknowledgement, and commit boundary

A document-like fetch used by instant navigation cannot assume that an indication
embedded in fetched HTML will survive partial-DOM replacement. Before returning
a cached response for such a request, the Service Worker sends the requesting
client a `templates:freshness-state` message carrying `cached-unverified`, the
exact request URL, the request generation, and a `MessageChannel`
acknowledgement port.

Current `pwa.js` applies that state to persistent DOM by creating the same fixed
status element and records a pending commit whose representation is `cached`.
It then replies through the port with `templates:freshness-state-applied`,
echoing the state and request generation. The Service Worker waits for that exact
acknowledgement, with a bounded timeout, before returning cached HTML.

This acknowledgement is a safety condition, not an optimization. If an older
open page is controlled by the updated worker but still runs a client script that
does not implement the freshness UI, no acknowledgement arrives. The worker then
refuses to expose cached HTML: a network failure returns the explicit 503 and a
transient HTTP 5xx returns the original 5xx.

Network response completion and document replacement are separate events under
Zensical instant navigation. The worker therefore sends a separate
`templates:document-commit` intent for non-cached network representations. That
message carries the exact URL, representation kind, and request generation, but
does not clear an existing warning. `pwa.js` retains only the newest observed
commit generation and waits for Zensical's `document$` event before acting on the
pending representation.

At the document-commit boundary, a committed `cached` representation keeps the
warning and consumes its pending marker. A committed `network` representation
clears the warning. This representation-aware correlation prevents two opposite
failures: a successful fetch that is prefetched or cancelled cannot clear a stale
warning before it is rendered, and a later fresh retry to the same URL cannot be
mistaken for an earlier cancelled cached fallback merely because the URLs match.

This fail-safe ordering deliberately permits an old warning to remain longer than
necessary if a non-Zensical surface cannot expose a document-commit signal. It
never permits stale content to become unindicated merely because a network fetch
finished before the caller replaced the visible DOM.

### Synthetic cached response

Cached fallback responses carry
`X-Templates-Freshness: cached-unverified` and `Cache-Control: no-store`.
Because the cached HTML body is modified, `Content-Encoding`, `Content-Length`,
`ETag`, and `Last-Modified` are removed. A cached response that is not HTML,
cannot be read, has a redirected final URL different from the exact request URL,
or lacks one unambiguous closing body boundary is not used as fallback. Redirects
fail closed because constructing a synthetic decorated `Response` cannot preserve
the original response URL needed for canonical relative-URL resolution.

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
- an uncached offline request retains explicit 503;
- ordinary 4xx responses never fall back to stale documentation;
- transient 5xx may fall back only with acknowledged stale indication;
- authoritative 404 removes the cached document so later offline access cannot
  resurrect it, including when an older delayed 200 completes afterward;
- Service Worker update propagation, manifest convergence, and the live
  freshness-capability message contract remain valid.

## Evolution rule

`checking` and `update-available` remain reserved for the later slow-network
convergence phase. A future soft timeout may reveal cached content while a network
request remains pending, but it must not cancel the request or be treated as proof
that the cached copy is current.

Any future change must preserve the central invariant: a document whose current
network freshness has not been verified is visibly identified as unverified
before it is presented as ordinary readable content.
