# Policy authoring

Each shared policy file contains YAML front matter with a stable rule ID, severity, override permission, and deterministic order. Mandatory non-overridable rules cannot be replaced by project-local policy. Long rationale and examples may follow the normative paragraph, but generated agent instructions should remain concise and executable.

## One independently applicable rule per module

A policy module owns one independently applicable normative rule and one stable rule ID. Rationale, examples, failure cases, and implementation notes may accompany that rule when they do not introduce additional independent obligations.

Split a document when two requirements can differ in any of these ways:

- one can apply while the other does not;
- one can change without changing the semantic meaning of the other;
- one can be overridden while the other remains mandatory;
- one belongs to a different operational context; or
- one needs a different stable identity for reference, migration, review, or diagnostics.

Do not duplicate an existing rule merely because another context such as pull-request review needs to check the same obligation. The context-specific rule should reference or rely on the existing canonical rule where possible.

## Shared-policy ownership test

A normative rule belongs in the shared `policy` corpus only when its meaning remains substantially unchanged when both the artifact category and the reasoning or execution engine are substituted.

Artifact-independent rules may be context-specific. For example, a generic rule for evaluating a pull request may live under a review policy family even though it is not selected for ordinary implementation work.

Use these ownership classes when extracting or moving rules:

- **shared policy**: artifact- and engine-independent operating behavior that is generally applicable;
- **context policy**: artifact- and engine-independent behavior selected only for an operational context such as review or external-artifact intake;
- **repository-local policy**: maintenance behavior that depends on repository identities, paths, schemas, profiles, publication boundaries, or other local invariants;
- **artifact contract**: requirements that define what a Skill, Web application, CLI, library, service, or other produced artifact must contain or do;
- **adapter/renderer requirement**: behavior whose meaning depends on a particular agent, platform, protocol, command surface, or output format;
- **explanatory material**: rationale, examples, history, proposals, and other non-normative text.

Shared semantic rules are authored only in the `policy` branch. Consumer repositories may keep generated projections with source provenance, but a handwritten copy must not become an independent competing authority.

## Repository-local extension and override

A managed repository selects shared policy and may add repository-local policy through `.agent-policy.yml`. Repository-local policy should state only local facts, invariants, justified extensions, or explicit permitted overrides; it should not restate shared rules for convenience.

An override is valid only when the canonical shared rule is declared overridable and the local policy makes the replacement explicit and attributable. A mandatory non-overridable rule remains authoritative.

Generated instructions should preserve the origin of every rule so a reviewer can distinguish toolchain-owned shared policy from repository-owned policy.

See ADR-0005 and `policy-authority-inventory.md` for the consolidation model and frozen cross-branch audit baseline.
