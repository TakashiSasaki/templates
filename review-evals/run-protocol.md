# Empirical reviewer evaluation protocol

This protocol is **non-authoritative evaluation guidance**. It does not change semantic policy, the `pr-review` procedure, provider integration contracts, or merge authorization.

## Freeze the evaluated inputs

For a comparative run, record immutable identities for:

- the evaluation case bytes;
- the provider-neutral `pr-review` procedure bundle;
- the semantic review-policy projection;
- the repository/change fixture or historical exact head when the case provides one;
- the reviewer/model/provider configuration being evaluated; and
- any external tooling configuration that can materially affect the run.

Do not compare runs that silently use different case, procedure, semantic-policy, or fixture revisions as though they were repeated samples of the same condition.

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

Report repeated-run distributions or worst-tail behavior rather than only the best or average run when reliability matters. This repository does not define a universal model/provider acceptance threshold in the evaluation corpus.

## Keep results non-authoritative

Evaluation results may motivate changes to canonical semantic policy or procedure, but they do not become those authorities automatically. Any such change must enter the appropriate canonical layer through its normal reviewed lifecycle.