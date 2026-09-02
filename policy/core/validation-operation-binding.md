---
id: safety.bind-validated-state-to-operation
severity: mandatory
overridable: false
order: 460
---
# Bind validated state to the effective operation

When correctness or safety depends on a validated or authorized target identity, scope, or other mutable precondition, ensure that the same effective target and required preconditions remain bound to the operation through use. Account for normalization, indirection, aliases, redirects, rebinding, and concurrent mutation; use stable identity or protected state, an atomic, transactional, or serialized mechanism, or revalidation at a protected commit or use boundary as appropriate. Fail closed if the operation can proceed against a different effective target or after the condition that authorized or validated it has become stale.
