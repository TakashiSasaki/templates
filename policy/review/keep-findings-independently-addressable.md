---
id: review.keep-findings-independently-addressable
severity: mandatory
overridable: true
order: 945
---
# Keep independently actionable findings independently addressable

Preserve each independently actionable review finding as a distinct remediation unit whose repair, explicit disposition, validation, and closure can be tracked independently. Do not bundle unrelated defects into one finding merely because they were discovered in the same review or can be described in one output surface.

When the active review provider supports independently resolvable, location-bound review items, prefer a representation that can preserve independent remediation for a finding that has an honest causal changed-location anchor. This is a provider-capability preference, not a provider-specific semantic requirement and not a required review-result representation.

Do not manufacture a changed-line anchor to obtain a resolvable representation. Cross-cutting, architectural, multi-file, or multi-change findings that lack one honest causal changed location remain valid findings and must stay separately distinguishable and independently dispositionable through another available representation surface.

Do not require stable numeric identifiers, a repository-owned review-result schema, or any provider event or object shape solely to preserve independent addressability.