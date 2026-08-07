---
id: review.evaluate-regression-guard-changes
severity: mandatory
overridable: true
order: 900
---
# Review changes that weaken existing regression guards

Treat removal, disabling, bypass, or material weakening of an existing required test, security check, compatibility check, or CI success condition as a blocking finding when it allows a significant regression to pass undetected. The absence of a new test for new logic is not by itself a blocking defect.
