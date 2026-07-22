---
id: safety.limit-rollback-to-owned-changes
severity: mandatory
overridable: false
order: 475
---
# Limit rollback to changes owned by the operation

For a multi-step mutation, complete preflight before the first write, revalidate the live state at the commit boundary, and track which paths the current operation created or changed. On failure, roll back only those owned changes; never delete or overwrite pre-existing or concurrently created state as cleanup unless explicitly authorized.
