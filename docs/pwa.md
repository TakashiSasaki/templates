# Use as a PWA

This guide describes the **provider-local Policy documentation build** named
`agent-policy`, configured by `mkdocs.yml` and `docs/manifest.webmanifest`.
It is reader operation help for anyone consulting Policy documentation, including
consumers and provider maintainers. Installing this PWA opens documentation; it
does not install the `agent-policy` skill or CLI, adopt Policy in a repository,
or provide an offline toolchain runtime. For those operations, see
[Getting started](getting-started.md) and [Managed repository operation](managed-operation.md).

The integrated repository documentation at
[templates.moukaeritai.work](https://templates.moukaeritai.work/) runs the
Site-owned PWA. Its product identity, service worker, cache scope, update and
freshness behavior are defined by Site's canonical
[PWA contract](https://github.com/TakashiSasaki/templates/blob/site/PWA.md).
The provider-local behavior below must not be read as that integrated runtime's
contract merely because Site publishes this page.

Policy's [documentation workflow](documentation-publication.md) is build-only;
it does not deploy this local build. The instructions below apply when that
build is served as its own site in a browser context supporting installation
and service workers. The root-scoped local assets are not instructions for
embedding another PWA inside the integrated Site.

## Provider-local reader operation

The provider-local documentation site can be installed as a Progressive Web App (PWA) from supported browsers. After installation, it can be launched in a standalone window from the operating system's application list, home screen, Start menu, or equivalent launcher.

### Installation

#### Android and Chromium-based browsers

Use the browser menu and choose **Install app** or **Add to Home screen**. When the browser considers the site installable, an install action may also appear in the address bar.

#### Desktop Chrome and Edge

Use the install icon in the address bar or the browser menu action to install `agent-policy`.

#### iPhone and iPad

In Safari, use the Share menu and choose **Add to Home Screen**. Available PWA features vary by browser and operating-system version.

### Orientation

When launched as an installed PWA on a mobile device, the application requests portrait-primary orientation. The Web App Manifest sets `orientation` to `portrait-primary`, and standalone display also attempts to lock orientation through the Screen Orientation API.

In a normal browser tab, in browsers without the API, or when the operating system rejects orientation locking, the device's own rotation setting takes precedence.

### Offline behavior

The Service Worker caches the application's basic assets and same-origin pages that have previously been viewed. When the network is unavailable, the application displays a cached page when available or the offline guidance page otherwise.

Documentation changes over time, so while online the application prefers the current network version.

### Updates

When a new Service Worker is delivered, it is activated automatically. If displayed content appears stale, reload the page or close and restart the installed application.

## Provider maintenance boundary

For changes to this local behavior, inspect `docs/manifest.webmanifest`,
`docs/assets/javascripts/pwa.js`, and `docs/service-worker.js`, and validate the
[local documentation build](documentation-publication.md#local-build-reproduction).
Deployment and the integrated PWA remain Site responsibilities. Publishing this
guide neither selects Site runtime assets nor changes Site installation behavior.
