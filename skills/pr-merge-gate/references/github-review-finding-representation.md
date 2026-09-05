# GitHub review finding representation

This reference is **non-normative GitHub integration guidance** for review acquisition and remediation. It does not define semantic review findings, change their severity, create merge authorization, or prescribe a repository-owned review-result schema. The canonical semantic rules remain under `policy/review/` and `policy/pull-request/`; the current GitHub API or connected-tool contract remains authoritative for request capabilities and fields.

## Preserve independent remediation units

When GitHub supports resolvable inline review threads and an independently actionable finding has an honest causal changed-line anchor, prefer representing that finding as its own resolvable inline thread.

Use one thread per independently actionable finding. Anchor it at the smallest changed location that introduces the root cause. Do not bundle unrelated defects into one thread merely because they belong to one review submission or share a broad topic.

This is a capability-aware representation preference, not a rule that every finding must be inline. Provider formatting must preserve the conceptual finding rather than redefine it.

## Do not manufacture inline anchors

Cross-cutting, architectural, multi-file, multi-PR, or otherwise unanchorable findings remain valid when semantic review policy establishes them. Do not attach such a finding to an unrelated changed line solely to obtain a resolvable thread.

Keep each such finding separately identifiable in the top-level review body or another provider-supported surface. Short descriptive labels are useful when several cross-cutting findings share one surface, but stable numeric finding identifiers are not required and no label convention is a review-result schema.

## Use the review body for review-wide material

The top-level review body is appropriate for review-wide material such as:

- the overall verdict or conclusion;
- reviewed scope and exact reviewed identity;
- material limitations;
- cross-cutting findings that lack an honest single changed-line anchor.

Do not collapse line-anchorable, independently actionable findings into the top-level body when GitHub can preserve them as independent resolvable threads without fabricating anchors.

## Review-acquisition preference

When asking a reviewer to produce GitHub-facing output and the acquisition mechanism permits output guidance, communicate the following preference in substance:

- use a separate resolvable inline review thread for each independently actionable finding that has a concrete causal changed-line anchor and for which the provider supports such a thread;
- do not combine unrelated defects into one thread;
- do not manufacture an inline anchor for a cross-cutting finding;
- keep unanchorable findings separately identifiable in the top-level review summary or another provider-supported surface.

The request may adapt wording to the reviewer or integration. It must not require a provider-specific review-result object, mandatory numeric finding IDs, or a GitHub event shape as semantic review authority.

## Remediation and closure

After a finding has been repaired or given an evidence-backed explicit disposition, validate that outcome against the current proposed head. Only then, when GitHub exposes a corresponding resolvable thread and current provider mechanics permit it, mark that thread resolved.

A resolved thread is bookkeeping evidence that disposition occurred; it is not semantic proof that the remediation is correct. Conversely, a finding present only in a top-level review body still requires finding-level disposition and validation even though no resolvable thread exists. Absence of a thread does not establish absence or resolution of a finding.

When a material finding is present only in a top-level review body or another non-resolvable GitHub surface, prefer recording its validated disposition as a reply or follow-up directly associated with the source review when current provider mechanics expose such an association. Preserve the source-review identity and a stable finding-level locator in that closure record so multiple body-only findings remain independently auditable.

If GitHub or the connected execution surface cannot attach a reply or follow-up to the source review, record the validated disposition on another durable pull-request surface and explicitly reference the source review plus the stable finding locator. Do not invent an inline thread or fabricate a changed-line anchor merely to obtain resolvable UI state. This is a traceability preference; semantic closure still comes from the validated disposition rather than the transport location.

The canonical review-reacquisition policy determines when recorded closure evidence is required before intentionally requesting another merge-acceptance review. This GitHub guidance only selects a traceable provider surface for that evidence and does not create the prerequisite itself.
