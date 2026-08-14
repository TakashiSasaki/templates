# Use as a PWA

This documentation site can be installed as a Progressive Web App (PWA) from supported browsers. After installation, it can be launched in a standalone window from the operating system's application list, home screen, Start menu, or equivalent launcher.

## Installation

### Android and Chromium-based browsers

Use the browser menu and choose **Install app** or **Add to Home screen**. When the browser considers the site installable, an install action may also appear in the address bar.

### Desktop Chrome and Edge

Use the install icon in the address bar or the browser menu action to install `agent-policy`.

### iPhone and iPad

In Safari, use the Share menu and choose **Add to Home Screen**. Available PWA features vary by browser and operating-system version.

## Orientation

When launched as an installed PWA on a mobile device, the application requests portrait-primary orientation. The Web App Manifest sets `orientation` to `portrait-primary`, and standalone display also attempts to lock orientation through the Screen Orientation API.

In a normal browser tab, in browsers without the API, or when the operating system rejects orientation locking, the device's own rotation setting takes precedence.

## Offline behavior

The Service Worker caches the application's basic assets and same-origin pages that have previously been viewed. When the network is unavailable, the application displays a cached page when available or the offline guidance page otherwise.

Documentation changes over time, so while online the application prefers the current network version.

## Updates

When a new Service Worker is delivered, it is activated automatically. If displayed content appears stale, reload the page or close and restart the installed application.
