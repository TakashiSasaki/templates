---
id: interfaces.model-user-visible-states
severity: mandatory
overridable: true
order: 830
---
# Model user-visible states and recovery

For each relevant operation, define loading, empty, partial, success, error, unauthorized, unavailable, offline, stale, and retry behavior. Error handling must control repeated work, preserve recoverable progress, and expose a clear recovery path instead of only displaying a message.
