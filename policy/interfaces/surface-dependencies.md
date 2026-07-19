---
id: interfaces.isolate-surface-dependencies
severity: mandatory
overridable: true
order: 810
---
# Isolate surface dependencies and failures

A surface must initially depend only on the authentication, data, and services required to render that surface. Load optional or sensitive data on demand, and do not let unrelated initialization or failures block an otherwise independent public or user-facing surface.
