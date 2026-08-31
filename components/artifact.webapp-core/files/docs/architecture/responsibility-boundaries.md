# Responsibility boundaries

`foundation.web` owns shared Web baseline semantics: browser identity/favicon declaration, generalized canonical navigation and accessibility expectations, plus viewports and input capabilities.

`artifact.webapp-core` owns application semantics: application surfaces, task/action-oriented UI states, authentication and access-failure behavior, and the binding of those behaviors to shared route IDs. Each Webapp `application-route` behavior target is browser-sensitive and therefore requires positive and negative browser-backed executable proof using an authoritative command whose execution capabilities include `browser`. Its validator is authoritative for Webapp-specific evidence targets; the shared foundation remains product-neutral.

`capability.pwa` owns its installability, application-icon, offline/freshness, and update proof families. Selecting PWA does not transfer those proof families to either `foundation.web` or `artifact.webapp-core`.
