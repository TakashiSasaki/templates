# Webapp contracts

`foundation.web` owns the shared Web contract families: `browser_identity`, generalized `routes`, and `viewports`. They describe browser identity, canonical paths and accessibility/navigation expectations, and viewport/input expectations without selecting an artifact identity.

`artifact.webapp-core` owns `surfaces`, `application_routes`, and `ui_states`. An application-route record binds a shared route ID to an application surface, authentication and access-failure behavior, and action-oriented UI states. The validator rejects missing, unknown, or duplicate route behavior instead of allowing one declaration to overwrite another.

Webapp evidence remains application-specific: surfaces, application route behavior, and UI states are validated as product behavior. Application-route behavior is browser-sensitive and therefore requires positive and negative browser-backed executable proof using an authoritative command whose execution capabilities include the `browser` execution capability. Planning mode applies the same proof-strength intent before coding: a planned application-route requirement must declare browser-level positive proof strength rather than weakening the requirement to an integration-only claim.

Shared browser proof infrastructure may also observe foundation-owned browser identity, routes, and viewports, but it does not turn those concerns into Webapp-only authority. PWA installability, application-icon, offline/freshness, and update evidence are owned separately by `capability.pwa`; selecting PWA does not transfer those proof families to either `foundation.web` or `artifact.webapp-core`.
