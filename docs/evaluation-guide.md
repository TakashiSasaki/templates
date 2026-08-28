# Evaluating Composition

This is the canonical entry point for an independent clean-room evaluation of Composition. It is intended for evaluators and Composition authority maintainers, not for ordinary consumer installation or product implementation. The normal consumer bootstrap and lifecycle contracts remain authoritative for consumer work.

## Canonical evaluation sequence

1. Read the [small-model clean-room protocol](../examples/evaluations/small-model-clean-room-protocol.txt) before starting the run. Establish the fresh-conversation, external-workspace, environment-fingerprint, transcript, and intervention boundaries it requires.
2. Execute the clean-room run and preserve chronological observations. In particular, record the first product-code mutation and first release-readiness evaluation instead of inferring ordering from final repository state.
3. Complete the [evaluation scorecard guide](../examples/evaluations/evaluation-scorecard.txt), using its fixed dimensions, attribution vocabulary, chronology rules, and fail-closed treatment of missing evidence.
4. Produce `evaluation-scorecard.json` and validate it against the [evaluation scorecard schema](../examples/evaluations/evaluation-scorecard.schema.json). Do not convert `BLOCKED` or `NOT TESTED` into `PASS`, and do not repair an observed ordering violation from later final state.

The output is the validated scorecard JSON plus the transcript/tool evidence needed to support its claims. Repository defects, documentation/discoverability defects, machine-contract defects, evaluation-methodology defects, evaluator mistakes, environment limitations, and evidence-capture limitations remain distinct attributions.

## Authority boundary

The protocol, scorecard guide, and scorecard schema are Composition-owned evaluation authorities. Site publishes this guide and those exact supporting assets for discovery, but does not reinterpret their evaluation semantics. They are not materialized into ordinary consumer repositories and do not add an evaluator mode to the Site `agent.json` consumer bootstrap.
