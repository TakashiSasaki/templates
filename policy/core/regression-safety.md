---
id: regression.no-weaken-tests
severity: mandatory
overridable: false
order: 200
---
# Do not weaken existing tests

Do not delete, skip, narrow, or relax an existing test merely to make a change pass. For a bug fix, add a regression test that fails before the fix and passes afterward whenever the failure can be reproduced deterministically.
