<!--
agent-policy-generated: true
source-skill: pr-review
DO NOT EDIT DIRECTLY
-->
# Namespace and indirection

This is a **provider-neutral procedure-support reference** for `pr-review`. It supports candidate discovery and falsification only; semantic review policy defines whether a surviving condition is a defect.

## Trigger

Use this domain when a logical name, path, locator, key, parent, reference, route, link, alias, redirect, mount, mapping, or other indirection determines the effective target of an operation.

## State and authority model

Model the transition from logical identifier to normalized/resolved name, through every applicable indirection step, to the effective resource used by the operation. Record where containment, ownership, authorization, existence, or collision decisions are made relative to that resolution chain.

## Candidate seeds

Generate candidates when:

- validation applies to the logical name while the operation follows later indirection;
- parent/ancestor substitution changes the effective target without changing the checked leaf name;
- normalization or decoding produces a materially different namespace location;
- alias/redirect resolution crosses an authority or containment boundary;
- a create/replace operation assumes a name is unoccupied although another actor can bind it first;
- different components interpret equivalent-looking names differently.

A seed is not a finding.

## Falsification evidence

Trace the concrete resolution semantics and actor capabilities. Look for stable handles/identities, protected resolution boundaries, no-follow/no-rebind guarantees, atomic namespace operations, collision handling, containment revalidation, and earlier rejection layers. Discard candidates that cannot alter the effective resource or violate an applicable invariant.

## Closure

Close this domain only after the effective resource is known and the reviewer can show that relevant containment, authority, collision, and identity conditions apply to that effective resource rather than only to its pre-resolution name.