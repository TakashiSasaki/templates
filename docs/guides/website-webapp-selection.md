# Choose Website or Web application

Use this guide when the product is browser-facing and you need to choose between the `website` and `webapp` Composition recipes.

The decision is about **product identity and caller-visible behavior**, not implementation technology. Do not classify the product from whether it is static or dynamic, client-rendered or server-rendered, hosted on a CDN or application server, or implemented with a particular framework.

## Short rule

Choose **Website** when the primary product model is **documents/content that people discover, navigate, read, and share**.

Choose **Web application** when the primary product model is **interactive tasks performed through application state, actions, transitions, and recoverable UI states**.

If both are present, classify the primary browser product from the behavior that defines its identity. Add capabilities for additional externally supported behavior rather than changing artifact identity to match deployment topology.

## Decision table

| Product intent | Choose | Why |
| --- | --- | --- |
| Documentation, reference material, a blog, news, marketing, institutional information, or a content catalog | `website` | Page/document structure, metadata, discovery, canonical identity, and navigation are the product baseline |
| A corporate or documentation site generated as static files | `website` | Static generation is a deployment/rendering choice, not application identity |
| A server-rendered news or publishing site | `website` | Server rendering does not turn document-oriented content into an application |
| A browser inventory manager, task tracker, dashboard, editor, workflow UI, or stateful tool | `webapp` | Application surfaces, actions, route behavior, visible states, and recovery behavior define the product |
| A single-page application served entirely from a CDN | `webapp` | Static hosting does not turn task/application-state semantics into Website semantics |
| A local-storage-only browser tool with no backend | `webapp` | A runtime or server is not required for Web application identity |
| A documentation site that can be installed and read offline | `website` + `capability.pwa` | PWA behavior is an optional cross-cutting capability; installability does not change artifact identity |
| An installable stateful browser application | `webapp` + `capability.pwa` | The product remains a Web application while gaining PWA behavior |
| A Website rendered by a maintained server runtime | `website` + `capability.runtime` | Runtime/deployment is orthogonal to Website identity |
| A Web application backed by a maintained runtime | `webapp` + `capability.runtime` | Runtime/deployment is orthogonal to Web application identity |

## What the recipes share

Both browser artifacts require `foundation.web` transitively. Consumers do not select the foundation directly.

The shared foundation owns product-neutral browser semantics:

- browser identity;
- generalized route identity, canonical paths, aliases, deep-link expectations, and route accessibility;
- viewport and input-capability expectations.

Those common contracts do not decide whether the product is a Website or Web application.

## Website identity

The `website` recipe selects `artifact.website-core`. Its artifact-owned contracts describe document/content-oriented browser products:

- `site_structure` — page identity, page hierarchy, home page, primary navigation, and bindings to shared routes;
- `document_metadata` — page titles, descriptions, indexability, canonical-path policy, and social-preview intent;
- `site_discovery` — canonical origin, robots policy, sitemap coverage, and discovery feeds.

A Website does **not** receive Webapp-private `application_routes`, `surfaces`, or `ui_states` merely because it uses JavaScript, a runtime, authentication elsewhere in the system, or client-side navigation.

## Web application identity

The `webapp` recipe selects `artifact.webapp-core`. It adds application-specific semantics on top of the same shared Web foundation:

- application surfaces;
- application-route bindings, authentication/access-failure behavior, history behavior, and route-visible state applicability;
- reusable visible UI states and recovery/announcement/focus semantics.

Use these contracts when application behavior itself is part of the supported browser product contract.

## PWA does not choose the artifact

`capability.pwa` is intentionally artifact-neutral. Select it because the browser product has externally supported installability, offline/freshness, platform application identity, and update behavior.

Do not infer `webapp` merely because a product:

- has a Web App Manifest;
- installs to a home screen;
- uses a service worker;
- works offline;
- has application icons; or
- has an update lifecycle.

A content-oriented documentation Website can be a PWA. A stateful browser application can also be a PWA. The artifact answers **what the browser product is**; PWA answers **what additional browser capability it supports**.

## Runtime and deployment do not choose the artifact

Likewise, do not infer artifact identity from where code runs.

These are all valid combinations:

```text
static Website
server-rendered Website
PWA Website
runtime-backed Website
CDN-hosted Web application
local-only Web application
PWA Web application
runtime-backed Web application
```

Select `capability.runtime`, `capability.web-interface`, service interfaces, or release lifecycle components only when their own caller-visible or lifecycle contracts apply.

## Mixed products

Some products intentionally contain both substantial document/content publishing and substantial application behavior. Do not collapse both semantic models into one oversized artifact contract merely because they share a hostname.

First identify the supported product boundary:

1. If one experience is primary and the other is incidental, choose the primary artifact and add only capabilities that actually match the additional behavior.
2. If the Website and application are independently supported product surfaces with distinct lifecycle/contract needs, model them as separate product artifacts/repositories or another explicit composition boundary rather than forcing Website semantics into Webapp contracts or vice versa.
3. Shared origin, framework, process, deployment, or navigation chrome is not by itself evidence that the two product contracts are one artifact.

## Quick examples

**Use `website`:** project documentation, a university department site, a company site, a blog, a news publication, an API reference site, a static knowledge base, a server-rendered article archive.

**Use `webapp`:** an inventory manager, issue tracker, form workflow, administrative dashboard, visual editor, scheduling tool, authenticated task application, browser IDE.

**Use either with PWA when appropriate:** installable offline documentation remains a Website; an installable offline inventory manager remains a Web application.

## Verify the choice before apply

The recipe descriptor is machine authority. Use `plan` before `apply` and inspect the resolved closure.

For a minimal Website, the closure should include `artifact.website-core` and transitive `foundation.web`, but not `artifact.webapp-core`.

For a minimal Web application, the closure should include `artifact.webapp-core` and transitive `foundation.web`, but not `artifact.website-core`.

Adding `capability.pwa` or `capability.runtime` must not switch one artifact identity into the other.

For exact recipe/component availability, continue to the [production catalog guide](../../catalog/README.md). For the repository-specific component-role mental model, see [Composition concepts](composition-concepts.md).
