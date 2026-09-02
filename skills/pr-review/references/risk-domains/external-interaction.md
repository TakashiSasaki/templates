<!--
agent-policy-generated: true
source-skill: pr-review
DO NOT EDIT DIRECTLY
-->
# External interaction

This is a **provider-neutral procedure-support reference** for `pr-review`. It supports candidate discovery and falsification; semantic policy remains authoritative.

## Trigger

Use this domain when the change sends requests, follows redirects, consumes callbacks/webhooks, reads remote resources, trusts externally controlled metadata, or otherwise crosses a process, service, network, organization, or trust boundary.

## State and authority model

Model the intended remote identity/authority, request construction, resolution/redirect chain, authentication and authorization context, response validation, retry/fallback behavior, and the local operation performed from the response.

## Candidate seeds

Generate candidates when:

- the checked destination can redirect or re-resolve to a different effective authority;
- externally supplied location/metadata can choose a privileged local or remote target;
- response authenticity/integrity is assumed from transport or naming alone;
- retries/fallbacks can duplicate externally visible effects or widen destination scope;
- callback identity is not bound to the initiating request/state;
- untrusted remote content influences persistence, execution, authorization, or generated artifacts without the required validation boundary.

A seed is not a finding.

## Falsification evidence

Trace effective destinations, identity binding, authentication/integrity guarantees, redirect/retry policy, replay protection, response/schema validation, capability restrictions, and realistic external control. Discard candidates that cannot cross the relevant boundary or cannot produce material reachable impact.

## Closure

Close this domain only after the reviewer can identify every material external authority involved and show that effective destinations, returned data, retries, and callbacks remain bound to the intended trust and operation scope.