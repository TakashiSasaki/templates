# Webapp contracts

`foundation.web` owns the shared Web contract families: `browser_identity`, generalized `routes`, and `viewports`. They describe browser identity, canonical paths and accessibility/navigation expectations, and viewport/input expectations without selecting an artifact identity.

`artifact.webapp-core` owns `surfaces`, `application_routes`, and `ui_states`. An application-route record binds a shared route ID to an application surface, authentication and access-failure behavior, and action-oriented UI states. The validator rejects missing, unknown, or duplicate route behavior instead of allowing one declaration to overwrite another.

Webapp evidence remains application-specific: surfaces, application route behavior, and UI states are validated as product behavior. Shared browser proof infrastructure may observe foundation-owned browser identity, routes, and viewports, but it does not turn those concerns into Webapp-only authority.
