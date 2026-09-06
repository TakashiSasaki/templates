# Routes v3 to v4 migration

Routes v4 is owned by `foundation.web` and is product-neutral: it retains canonical paths, aliases, deep-link expectations, and browser navigation/accessibility semantics.

This pre-production repository does not provide an in-place upgrade for pre-v4 consumer locks. Recompose from the current recipe revision. For a Webapp, move `surface`, `authentication`, `historyBehavior`, `authenticationReturn`, `accessFailures`, and `states` into matching `contracts/application-routes.json` entries. Website artifacts use the same shared routes contract and never declare Webapp application behavior.
