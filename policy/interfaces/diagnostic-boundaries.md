---
id: interfaces.separate-diagnostics
severity: mandatory
overridable: true
order: 850
---
# Separate operational diagnostics from user interfaces

Keep debug output, internal identifiers, implementation details, and sensitive diagnostics out of ordinary end-user surfaces. Expose required diagnostics only through intentional status, developer, or administrative surfaces with appropriate access control and redaction; keep machine-readable error codes distinct from human-facing messages.
