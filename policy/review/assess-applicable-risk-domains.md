---
id: review.assess-applicable-risk-domains
severity: mandatory
overridable: true
order: 815
---
# Assess the risk domains applicable to the change

Before concluding that a reviewed change has no blocking defect, assess the material risk domains that the change can affect, including contract or specification consistency, correctness and preserved invariants, data integrity, tests and CI integrity, security and trust boundaries, compatibility or migration, generated or derived artifacts, failure and recovery paths, and performance or resource behavior when those domains are relevant. This is a coverage obligation, not a checklist-based approval rule: irrelevant domains need no finding, and a completed enumeration does not substitute for establishing change causality, realistic reachability, concrete impact, and the other evidence required for a valid finding.
