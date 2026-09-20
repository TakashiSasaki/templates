---
name: policy-guidance
description: Retrieve exact selected Policy rule details from a lock-bound staged delivery bundle before a dependent operation.
---
<!--
agent-policy-generated: true
source-skill: policy-guidance
DO NOT EDIT DIRECTLY
-->

# Policy guidance

Use this Skill when the repository has an `agents-md-staged` output.

The generated script reads the complete selected-rule bundle and validates its
schema, source identities, and generated-output lock before printing details.
It is a presentation adapter. It does not select policy, reinterpret severity,
decide applicability, or authorize a mutation.

Run it before the dependent operation:

```bash
python .agents/skills/policy-guidance/scripts/policy_guidance.py \
  --bundle {{ policy_delivery_bundle_path }} --operation <operation>
```

Use `--rule-id <id>` for one exact rule or `--all` when the operation route is
missing or ambiguous. A validation error is a blocking condition for the
dependent operation. Repair or regenerate the managed outputs before retrying.
