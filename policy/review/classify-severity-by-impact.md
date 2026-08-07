---
id: review.classify-severity-by-impact
severity: mandatory
overridable: true
order: 860
---
# Classify severity from reachable impact

Classify review severity from the realistic reachability, breadth, reversibility, and consequence of the failure rather than from the theoretical worst case. Reserve the highest severity for defects that can directly cause catastrophic data loss, broad production failure, major privilege compromise, remote code execution, or comparably immediate harm; use the next blocking tier for realistic major malfunction, security boundary failure, compatibility breakage, or operational failure that must be fixed before merge.
