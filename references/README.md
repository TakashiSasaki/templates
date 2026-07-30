# Operational references

This directory is optional. Place documents here only when an agent may need them while performing the skill.

Useful reference types include:

- authoritative policies or procedures;
- domain terminology and glossaries;
- input, output, schema, and format contracts;
- compatibility or version rules;
- lookup tables and bounded decision guides;
- error-code references;
- troubleshooting procedures;
- worked examples that materially reduce ambiguity;
- environment-specific operational notes.

Every retained reference must have an exact `Reference: references/...` declaration in `SKILL.md`. That declaration must state when the file should be read and what question or workflow step it supports. Supplemental details may remain in the reference itself, but no other document replaces the declaration and trigger in `SKILL.md`.

For every retained reference, also record as applicable:

- whether it is authoritative, advisory, or illustrative;
- applicable product, schema, protocol, or policy versions;
- provenance or source when correctness depends on it;
- freshness or re-verification requirements when the information may become stale.

Prefer focused references over broad documentation dumps. Avoid deep chains where one reference points to another reference that points to a third. The agent should be able to determine the needed file directly from `SKILL.md`.

Do not duplicate short instructions that belong in `SKILL.md`. Move detail here when it is conditional, lengthy, tabular, version-specific, or needed only for a subset of tasks.

Maintainer-only architecture, development, release, and migration material belongs under `docs/`, not here.

Delete this directory when the concrete skill needs no additional operational knowledge.
