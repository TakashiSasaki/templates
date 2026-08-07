---
id: review.require-error-path-evidence
severity: mandatory
overridable: true
order: 880
---
# Require evidence for error-path findings

For an error-handling or boundary-condition finding, identify the triggering input, state, or external failure, explain why that condition is realistic, determine whether the changed path fails closed, fails open, retries, partially commits, or otherwise changes state, and connect that behavior to a material consequence. Missing defensive code alone is not a blocking finding.
