# Integration maintenance

Provider discovery, semantic assembly and self-contained publication artifacts.

## Boundaries

- Work in this authority's worktree. Keep `policy`, `composition`, `modeling`,
  `integration` and `site` histories independent: no cross-authority merge or rebase.
- Synchronize the target base before branching. Preserve other worktrees and local edits.
- Source flows from providers to Integration artifacts to Site to Pages. A downstream
  failure does not invalidate upstream source work or require a coordinated release.
- There is no backward-compatibility or migration requirement for this repository.
- The repository owner may change these instructions together with implementation.

## Work and validation

Read the source and tests for the affected behavior. Use focused checks while editing,
then the relevant local checks before handing off. Do not wait for another authority's
CI, a pin update, a review-scope planner, or a generated Work ledger to implement a change.

```sh
python -m unittest discover -s tests -v
```

Keep authored source separate from generated output. Regenerate outputs with their local
tool. Treat exact SHAs and hashes as build provenance; do not require a source commit just
to adopt a new downstream publication. An unchanged artifact remains usable after its
source branch advances. Report what actually ran and any remaining failures.

Use `.agents/skills/land-templates-stack/SKILL.md` only for PR preparation/landing.
The optional progressive-discovery utility and reusable Policy/Composition products do
not govern repository maintenance by implicit self-adoption. Release/runtime pins that
identify executable consumer distributions are separate from publication selection.
