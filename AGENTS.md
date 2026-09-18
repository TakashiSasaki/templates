# Integration authority

This worktree owns reviewed provider selection and cross-authority publication
integration. Composition and Policy retain their canonical semantics, translations,
glossaries and synchronization metadata. Never merge, rebase or cherry-pick foreign
authority histories. Materialized bootstrap files must retain source provenance.

Use the existing Policy construction/qualification frontier and evidence-applicability
principles. Focused tests belong to construction; exact-head deterministic qualification
belongs to a stabilized candidate. This authority adds no mandatory Work-ledger schema.
Never infer acceptance from stale-head evidence. Guard any later release merge by the
reviewed head, applicable CI and dispositioned review findings.

No Site runtime, HTML renderer, CSS, browser, PWA, Pages packaging or deployment belongs
here. Qualification must run with this checkout plus exact provider checkouts only.
Do not advance publication-sources.json without explicit provider adoption intent.
Do not edit provider translation content or synchronization metadata.

For Integration maintenance, read [README.md](README.md), [AUTHORITY.md](AUTHORITY.md),
[RELEASE.md](RELEASE.md), and `.agents/skills/integration-publication-maintenance/SKILL.md`.
Use that thin routing skill for provider-selection, Bundle, and publication-chain
diagnostics; Site adoption still requires the Site-owned instruction and gate.

Run `python -m unittest discover -s tests -v` after dependency installation. Producer
qualification must generate twice from identical exact inputs. Review artifact transport
binding separately from deterministic content identity. Build outputs live outside all
source checkouts. Caller-owned workspaces must be exclusive during qualification.

Integration release promotion requires explicit task authorization and guarded
exact-head acceptance. Request one cumulative review per logical stack; after
remediation, reacquire only targeted evidence whose bindings changed. The historical
P5 bootstrap handoff does not authorize Site adoption, cutover or deployment.

## Templates maintainer landing route

For maintenance of the `integration` authority itself, load
`.agents/skills/land-templates-stack/SKILL.md` for a single PR or
same-authority stack, then use `.agents/skills/pr-merge-gate/SKILL.md` for the
shared acceptance gate. The landing source is pinned to
`TakashiSasaki/templates@5af977020fca701bcf6b7fb7ce12ca077b2d7220`,
`repository-skills/land-templates-stack/SKILL.md`, blob
`902b6e543d467b47b2b91819bfab5574a85456c7`; verify its adjacent
`source.json` and resolve the rule from that same snapshot. Never use a mutable
branch or local fallback. Integration provider/Bundle evidence, CI, review,
publication, Site adoption, deployment, and human merge authorization remain
separate; this task does not merge or enable auto-merge.
