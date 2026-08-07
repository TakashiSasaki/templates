---
id: skill-source.preserve-distribution-integrity
severity: mandatory
overridable: false
order: 1010
---
# Preserve the exact copyable distribution

`distribution-manifest.json` is authoritative for the copyable inventory.

Validator implementations projected from `.github/scripts/` into `template/.github/scripts/` must retain identical bytes and Git-significant modes. For a projected validator, change the source implementation and its distributed copy together, then run both source distribution validation and copied-Skill validation.

Keep `template/` closed and independently usable after copying. Reject undeclared copied files, missing declared files, projection byte or mode drift, prohibited symbolic links or Git links, path traversal or `.git` path components, maintainer-only leakage, automatic content transformation, and runtime or validation dependence on the source checkout.
