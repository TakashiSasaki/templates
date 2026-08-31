# Responsibility boundaries

`foundation.web` owns shared Web baseline semantics: browser identity/favicon declaration, generalized canonical navigation and accessibility expectations, plus viewports and input capabilities.

`artifact.webapp-core` owns application semantics: application surfaces, task/action-oriented UI states, authentication and access-failure behavior, and the binding of those behaviors to shared route IDs. Its validator is authoritative for Webapp-specific evidence targets; the shared foundation remains product-neutral.
