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
message contract together with `/site-version.json` and the reserved document
cache namespace.

The vocabulary is a compatibility contract, not permission to claim a state
without evidence. In particular, matching build revision metadata does not by
itself establish `verified-current`.

## Current PR1 cache behavior

The freshness-identity foundation does not change document caching behavior.
Browser navigations and same-origin document-like instant-navigation requests
continue to use `fetch(request, { cache: "no-cache" })`, so the browser HTTP
cache is revalidated. If that network request fails, the Service Worker returns
the existing explicit HTTP 503 offline response.

`templates-portal-documents-v1` is reserved for the follow-up runtime document
cache implementation but is not opened or populated by this foundation. Service
Worker activation deletes only incompatible `templates-portal-shell-*` caches;
it does not delete the reserved document namespace.

The existing shell cache continues to contain `/app.webmanifest` and `/icon.svg`
and uses stale-while-revalidate behavior for those exact assets.

## Evolution rule

A later offline-capable implementation may populate the document cache only when
it also preserves the following invariant in the same change: a document whose
current network freshness cannot be verified must be visibly identified as
unverified before it is presented as ordinary readable content.

A future slow-network implementation may use `checking` and
`update-available`, but a timeout used to reveal a cached document must not be
treated as proof that the network request failed or as proof that the cached
copy is current.

Changes to `/site-version.json` schema semantics, the HTML revision-meta name,
the runtime freshness-state vocabulary, or cache namespace compatibility are
public Site contract changes and require review with the PWA freshness tests.
