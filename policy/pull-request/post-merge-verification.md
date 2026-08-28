---
id: pull-request.verify-merge-result
severity: mandatory
overridable: true
order: 982
---
# Verify the merge result after execution

After executing a pull-request merge, verify from current repository state that the pull request is actually merged, record the resulting merge identity, and confirm that the target branch contains the intended merged result or a later intentional successor.

Do not report merge completion solely because the merge operation returned without a transport error. If the observed repository state does not establish that the intended result was merged, report the merge outcome as unresolved or failed and investigate before claiming completion.

Treat any release, publication, deployment, or other post-merge readiness requirement as a separate acceptance boundary; successful merge verification does not by itself establish those later states.
