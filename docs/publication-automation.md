# Contract-gated publication automation

The publication controller distinguishes technical processability from
authorization. A compatible candidate remains pending until the exact producer,
consumer, policy, workflow, run attempt, and artifact evidence are qualified.

The release mode is `shadow` by default. Shadow classification and read-only
qualification may produce reports, but they never update an authority lock,
merge a pull request, or deploy Pages. Adoption-only and auto-publish require a
separate activation of trusted external configuration.

The only normal mutations are the exact provider revision fields in Integration's
`publication-sources.json` and the exact selected Bundle identity fields in
Site's `integration-source.json`. The controller never updates active Policy
pins, `AGENTS.md`, workflows, validators, capabilities, or generated trees.

Candidate qualification output is evidence, not authority: a controller must
bind the exact run/attempt/artifact and independently validate the Bundle with
trusted code before applying a positive adoption gate. A candidate report
cannot grant its own authorization or change the active Policy/controller pin.

The kill switch stops new adoption and deployment while preserving the last
successful publication. Recovery selects a previously qualified fixed input or
artifact; retry must not resurrect a superseded selection.
