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
The Site and provider revisions are the full lowercase 40-character Git commit
SHAs from the actual build checkouts, not mutable branch names, tags, or abbreviated
revisions.

`/site-version.json` uses schema version 1:

```json
{
  "schema_version": 1,
  "site_revision": "<full Site commit SHA>",
  "deployed_at": "YYYY-MM-DD HH:MM:SS JST",
  "publications": {
    "skill": "<full Skill commit SHA>",
    "policy": "<full Policy commit SHA>",
    "webapp": "<full Webapp commit SHA>"
  }
}
```

`publications` contains exactly `skill`, `policy`, and `webapp`; missing or
unexpected provider keys fail the build. All revisions must be lowercase full
40-character Git SHAs.

`deployed_at` is the exact JST deployment timestamp already rendered by the Site
metadata pipeline. A non-deploying preview build records JSON `null`. The
freshness projection must not introduce a second clock or independently generate
a deployment timestamp.

The generator rejects a symbolic-link `/site-version.json` output and any
non-regular output path. It also rejects symbolic-link or non-regular generated
HTML paths rather than following them.

## Per-document build identity

Every generated HTML page that participates in the normal Site runtime receives
exactly one element in its `<head>`:

```html
<meta name="templates-site-revision" content="<full Site commit SHA>">
```

The value must equal `/site-version.json`'s `site_revision`. Existing conflicting
or duplicate metadata fails the build. Generated HTML with a malformed or
ambiguous closing `</head>` also fails rather than being heuristically rewritten.

Sandboxed repository-tree preview documents under
`/repository-trees/previews/` are excluded. They are bounded source previews,
not normal PWA document surfaces.

After writing the projection, the build re-reads `/site-version.json` and every
eligible generated HTML page. It verifies the complete JSON payload and exactly
one matching revision meta element before the Pages artifact can continue toward
link validation and upload.

## Provenance relationship

`build-provenance.json` remains the build-oriented source-input record.
`site-version.json` is a browser-readable projection of the same exact revisions.
Neither file is a digital signature, software bill of materials, or artifact
attestation.

The two files must not be populated from separate revision-resolution paths. The
existing provenance step receives the actual checked-out Site, Skill, Policy, and
Webapp revisions and supplies those same values to the freshness projection.

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
namespace.

The vocabulary is a compatibility contract, not permission to claim a state
without evidence. In particular, matching build revision metadata does not by
itself establish `verified-current`.

## Runtime document-cache behavior

Normal browser navigations and same-origin document-like instant-navigation
requests remain network-first. Every online document request uses
`fetch(request, { cache: "no-cache" })`, preserving HTTP-cache revalidation rather
than treating a stored document as authoritative.

A successful same-origin HTTP 200 response is eligible for the runtime document
cache only when its response `Content-Type` contains `text/html`. The response is
cloned before asynchronous cache work begins, so returning the network response
does not race with Cache Storage consumption of the same body stream.

The document cache uses the independent namespace
`templates-portal-documents-v1`. Service Worker activation removes incompatible
`templates-portal-shell-*` caches but does not delete the document namespace.
This allows verified documents that were previously viewed to remain available
through a shell-worker update.

Network and HTTP outcomes have distinct semantics:

- successful cacheable HTTP 200: return the network response and update the exact
  document cache entry;
- HTTP 404 or 410: treat the response as authoritative deletion, remove the exact
  cached document, and return the network response;
- ordinary non-transient 4xx such as 403: return the network response and do not
  resurrect a cached document;
- HTTP 5xx: return a cached document when one exists, otherwise return the server
  error response;
- network/DNS/TLS/connection failure: return a cached document when one exists,
  otherwise return the explicit HTTP 503 offline fallback.

A cache fallback is never returned as if it were current. Before a cached HTML
response is exposed, the Service Worker injects a visible status element directly
inside the document body with `data-freshness-state="cached-unverified"` and text
stating that the saved copy is being shown because the latest version could not
be verified. The synthetic response also carries
`X-Templates-Freshness: cached-unverified` and `Cache-Control: no-store`.

Because cached HTML is modified before return, representation-specific headers
that are no longer valid after decoration (`Content-Encoding`, `Content-Length`,
`ETag`, and `Last-Modified`) are removed from the synthetic response. If a cached
response is not HTML, cannot be read, or has no usable `<body>` insertion point,
it is not used as a fallback; the request instead follows the applicable network
or explicit offline response path. This fail-closed rule prevents stale content
from appearing without the required indication.

## Shell cache behavior

The shell cache is versioned independently from the document cache. It precaches
the Site-owned common assets needed to render previously viewed documentation,
including the manifest, icon, global stylesheets, the freshness-status stylesheet,
and common local JavaScript files. Those exact static resources continue to use
background `cache: "no-cache"` revalidation when requested.

The shell and document cache lifetimes must remain independent: a shell cache
version transition may remove older `templates-portal-shell-*` namespaces, while
the compatible runtime document namespace is preserved.

## Browser regression contract

The Chromium freshness lifecycle exercises both freshness and availability. It
verifies at least the following state transitions and invariants:

- document v1 is fetched online, then a server-side v2 replaces it and the next
  online request obtains v2 rather than an HTTP-cache-stale v1;
- the verified v2 response reaches the runtime document cache;
- a Service Worker version update does not remove the compatible document cache;
- offline fetch and full navigation of the previously viewed document return v2
  with the visible `cached-unverified` indication;
- an offline request for a never-cached document retains the explicit HTTP 503
  fallback;
- ordinary 4xx responses do not fall back to stale documentation;
- transient 5xx responses may fall back to the verified cached document;
- an authoritative 404 removes the cached document, after which offline access
  returns the explicit fallback rather than resurrecting deleted content.

The same browser fixture continues to verify Service Worker update propagation,
manifest convergence, and the live freshness-capability message contract.

## Evolution rule

`checking` and `update-available` remain reserved for the later slow-network
convergence phase. A future soft timeout may reveal a cached document while a
network request remains pending, but the timeout must not cancel that network
request or be treated as proof that the cached copy is current.

A later implementation of those states must preserve the central invariant: any
document whose current network freshness has not been verified is visibly marked
as unverified before it is presented as ordinary readable content.

Changes to `/site-version.json` schema semantics, the HTML revision-meta name,
the runtime freshness-state vocabulary, cache namespace compatibility, or the
fallback status policy are public Site contract changes and require review with
the PWA freshness tests.
