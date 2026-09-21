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
schema, policy-significant rule metadata (`title`, `severity`, `overridable`,
and `order`), source identities, generated-output lock, and current
configuration and repository-policy input bindings before printing details. It
uses the installed `agent_policy` package for strict YAML lock parsing and
canonical rule loading; an old bundle plus an old lock is not current guidance
after inputs change. It is a presentation adapter. It does not select policy,
reinterpret severity, decide applicability, or authorize a mutation.

Run it before the dependent operation:

```bash
python .agents/skills/policy-guidance/scripts/policy_guidance.py \
  --bundle={{ policy_delivery_bundle_path_shell }} --operation <operation>
```

The script locates the nearest repository ancestor containing
`.agent-policy.yml` from its installed path, so this command also works from a
nested repository directory. Use `--root <repository>` when an explicit root
is required.

Use `--rule-id <id>` for one exact rule or `--all` when the operation route is
missing or ambiguous. A validation error is a blocking condition for the
dependent operation. Missing, contradictory, incomplete, or stale bindings
must be repaired or regenerated before retrying. `--all` is a safe fallback
only for a valid bundle whose operation route is explicitly absent; it does not
bypass bundle or input validation. The generated command shell-quotes the bundle
path, so configured paths containing whitespace, shell metacharacters, or a
leading hyphen remain one argument.
