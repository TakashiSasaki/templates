# Reviewer evaluation corpus

`review-evals/` is **non-authoritative empirical and synthetic evaluation material** for pull-request review quality. It does not define semantic policy, `pr-review` procedure requirements, severity, merge authorization, or provider output formats.

The corpus answers a separate question: given the canonical semantic policy and provider-neutral review procedure, does a reviewer actually discover, falsify, localize, and correctly disposition material defect candidates?

## Case kinds

- `empirical` cases preserve compact facts from historical repository reviews. They record exact source identities when available, but historical reviewer text is evidence rather than authority.
- `semantic-transposition` cases express a failure mechanism without binding it to one programming language, framework, library, API, or provider. They are designed to test whether the same reasoning transfers across surface representations.
- control cases may intentionally contain no blocking defect. They measure unsupported-finding and false-positive behavior.

## Deterministic CI boundary

Normal repository CI validates only the corpus itself:

- JSON Schema conformance;
- unique stable case IDs;
- allowed risk-domain identifiers;
- positive and negative/control coverage;
- empirical provenance shape;
- required expected-review dispositions;
- separation from semantic/procedure authority.

Normal CI does **not** invoke a language model or declare a model/provider acceptable. Model execution, repeated trials, and comparative scoring are empirical activities outside deterministic policy-toolchain validation.

## Coverage observability

Use the deterministic coverage reporter to inspect how the current corpus is distributed across risk domains, case kinds, and expected review dispositions:

```console
python scripts/review_eval_coverage.py --format markdown
python scripts/review_eval_coverage.py --format json
```

The report distinguishes empirical history, semantic transpositions, controls, blocking cases, clean controls, and incomplete-review cases. It also emits `coverage_observations` such as `no-empirical`, `no-control`, or `no-incomplete-review` for dimensions that currently have no case in a risk domain.

Those observations are **not acceptance failures and do not create review-policy requirements**. A domain can legitimately lack a historical incident, control, or incomplete-review scenario. The matrix exists to make evaluation-suite blind spots and imbalances visible so future corpus work is deliberate rather than inferred from case counts. Deterministic CI verifies that the reporter faithfully summarizes the corpus; it does not turn every empty matrix cell into a mandatory new case.

## Evaluation dimensions

A run may be assessed for:

- applicable risk-domain coverage;
- blocking-defect recall;
- false-positive / unsupported-finding rate;
- root-cause localization;
- candidate falsification quality;
- premature clean-verdict rate;
- task-substitution / false-completion rate; and
- repeated-run lower-tail reliability.

A case's `expected_review` describes the minimum semantic outcome needed for that case. It is evaluation truth for the case, not a new repository policy rule.
