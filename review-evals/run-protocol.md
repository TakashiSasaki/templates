# Empirical reviewer evaluation protocol

This protocol is **non-authoritative evaluation guidance**. It does not change semantic policy, the `pr-review` procedure, provider integration contracts, or merge authorization.

## Freeze the evaluated inputs

For a comparative run, record immutable identities for:

- the evaluation case bytes;
- the provider-neutral `pr-review` procedure bundle;
- the semantic review-policy projection;
- the repository/change fixture or historical exact head when the case provides one;
- the reviewer configuration being evaluated;
- the raw execution evidence used to score the trial;
- the evaluator or scoring implementation; and
- any external tooling configuration that can materially affect the run.

Do not compare runs that silently use different case, procedure, semantic-policy, fixture, reviewer-configuration, execution-evidence, evaluator, or material tooling identities as though they were repeated samples of the same condition.

## Run independently

Execute each case independently so findings or hints from one case do not become hidden context for another. For stochastic reviewers, use repeated runs when practical; a single success is evidence of capability, not evidence of reliable behavior.

The evaluator should preserve whether each run:

- performed substantive analysis rather than task substitution;
- dispositioned the applicable risk domains;
- generated and falsified material candidates;
- reached the case's expected review disposition;
- identified the required mechanism/root cause when a finding is expected;
- avoided the case's forbidden claims; and
- preserved incomplete status when required evidence or execution was unavailable.

## Record evaluation observations, not review-result contracts

`review-eval-observation.schema.json` defines a machine-readable record of what an **evaluator observed about one trial**. It is evaluation data only. It does not require the reviewed system to emit JSON, adopt these field names, expose internal reasoning, use a particular provider event, or implement a repository-owned review-result wire format.

Bind each observation to the exact case bytes with the case ID and SHA-256 digest. The observation also records immutable identities for the procedure bundle, semantic policy, fixture, evaluated reviewer configuration, raw execution evidence, evaluator, and material external tooling so repeated trials are comparable and scoring remains auditable.

Case-relative evidence is recorded by zero-based indices into the frozen case's `risk_domains`, `must_investigate`, `must_identify`, and `must_not_claim` arrays. The case digest makes those indices meaningful only for those exact bytes. `must_not_claim_indices_violated` records forbidden claims that were actually observed; an empty array on a completed evaluation means none were observed.

Use `scripts/validate_review_eval_observation.py` to validate both JSON Schemas, the exact case digest and ID, case-relative index bounds and ordering, and basic finding-count consistency. The validator deliberately permits observations such as a completed disposition paired with `substantive_analysis_completed: false`: representing that contradiction is necessary to measure false completion rather than censor it from evaluation data.

A trial that produced no review disposition is recorded as `reported_disposition: not-reported` with null finding counts. Do not normalize missing output into `incomplete-review` merely to fit the procedure's conceptual outcome vocabulary; the evaluation observation must preserve what the reviewer actually emitted or failed to emit.

Do not treat a valid observation record as evidence that the underlying review was correct. Validation establishes only that the evaluation record is structurally coherent and bound to the stated frozen inputs and evidence.

## Score behavior, not prose similarity

Do not require exact wording. Evaluate whether the run establishes the case's required observations and disposition under the canonical policy/procedure.

Useful aggregate dimensions include:

- blocking-defect recall for positive cases;
- false-positive rate on control cases;
- premature clean-verdict rate;
- false-completion/task-substitution rate;
- root-cause localization rate;
- required-investigation coverage; and
- repeated-run lower-tail reliability.

Report repeated-run distributions or worst-tail behavior rather than only the best or average run when reliability matters. This repository does not define a universal reviewer acceptance threshold in the evaluation corpus.

## Keep results non-authoritative

Evaluation observations and aggregate results may motivate changes to canonical semantic policy or procedure, but they do not become those authorities automatically. Any such change must enter the appropriate canonical layer through its normal reviewed lifecycle.
