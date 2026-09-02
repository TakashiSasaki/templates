<!--
agent-policy-generated: true
source-skill: pr-review
DO NOT EDIT DIRECTLY
-->
# Identity and authority

This is a **provider-neutral procedure-support reference** for `pr-review`. It generates and falsifies defect candidates; it does not define defects, severity, review completion, or merge authorization. The retained semantic review policy remains authoritative.

## Trigger

Use this domain when an identity selects authority, ownership, scope, trust, privilege, tenancy, repository/resource boundaries, or the subject of a safety decision.

## State and authority model

Model the chain from presented identity to canonical/effective identity, the authority attached to that identity, and the operation performed under that authority. Separate display names, aliases, mutable labels, caller assertions, cached identities, and stable provider/resource identities.

## Candidate seeds

Generate candidates when:

- authorization or containment is checked against an identity different from the one ultimately used;
- an alias, rename, redirect, rebinding, fallback, or canonicalization step can change the effective subject;
- an identity from one trust domain can be confused with another domain's identity;
- cached identity/authority evidence can survive a state change that invalidates it;
- a default, fallback, or inferred identity can silently widen scope or privilege.

A seed is not a finding.

## Falsification evidence

Try to disprove each candidate using the actual identity-resolution chain, immutable/stable identifiers, authority checks at the effective-use boundary, scope restrictions, change causality, exact-head tests, and realistic controlling actors. Discard the candidate if existing guards make the identity confusion unreachable or harmless.

## Closure

Close this domain only after the reviewer can explain which effective identity receives authority at use time, how that identity is bound to the checked authority/scope, and how material identity substitutions are prevented or safely rejected.