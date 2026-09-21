# Matched clean-consumer delivery experiment

Status: `DIAGNOSTICS_ONLY` / `NOT_ESTABLISHED`

This document records the bounded A-versus-C experiment requested for the
instruction-delivery prototype. It does not change the default renderer,
adoption state, or the original whole-task-cost decision gate.

## Protocol

The experiment compares the same three disposable tasks under two conditions:

- A: the ordinary full-text `agents-md` output;
- C: the opt-in `agents-md-staged` output with an authenticated detail bundle
  and `policy-guidance`.

Each condition uses the same candidate wheel, selected rules, task wording,
fixture, permissions, and deterministic grader. The runner interleaves the
pairs in this order: `A1, C1, A2, C2, A3, C3`.

Condition B was not run because this host does not expose a reproducible way to
distinguish its prompt inclusion from A. The runner installs one exact wheel in
both isolated consumers. It does not accept a caller-supplied wheel: it first
retains a verified candidate source/artifact snapshot, builds the wheel used by
both conditions from that snapshot, and revalidates the retained manifest
before each dependency installation, wheel installation, render, and trial
use. It validates the installed distribution, payload hashes and sizes,
installed `RECORD`, metadata, and console entry point before the consumer is
usable. Documented pip-generated files (`__pycache__`, installer bookkeeping,
and the console-script wrapper) are explicit installation transformations;
unexpected files or metadata fail closed. Its staged path invokes the actual external
`skills/agent-policy/scripts/run.py` and its lock-selected runtime cache; it
does not generate a test-only wrapper.

## Current evaluation-integrity contract

The evaluation runner is qualified as a diagnostic harness, not as a
performance result. Candidate source, runtime-lock bytes, Skill bytes, and the
wheel are retained from the verified provider revision. Wheel verification
covers package payloads and the complete install metadata closure, including
`METADATA`, `WHEEL`, `RECORD`, and declared console entry points. The `WHEEL`
field set and filename tags are checked against the retained build, not merely
for the presence of `Root-Is-Purelib`. A changed or lost retained file fails
closed before it is used, and the installed result is checked again at the
installation boundary.

Each disposable task has a pre-trial reference outside the worker fixture,
including the reference root and manifest even for the editable code-repair
task whose protected-file set is empty. Protected generators, checkers,
evidence, and validators are compared with that reference. Generated-artifact
grading runs the retained checker against the worker's outputs; review
preparation is graded against retained expected facts rather than executing a
worker-modifiable validator. Code repair uses the exact retained regression
obligation identity, direct-target external `unittest` execution, an
obligation-specific mutant, and a separately observed full discovered suite
that exits successfully with at least one test. A common grade composition
requires task correctness, reference integrity, policy compliance, and
evidence validity, so an observed prohibited operation prevents a pass for
every task type.

## Contract-to-counterexample matrix

This is the bounded acceptance contract for the diagnostic harness. It records
what is actually observed, rather than treating a missing event as proof of
compliance.

| Claim | Enforcing/observing boundary | Negative control | Positive control | Limit |
| --- | --- | --- | --- | --- |
| Local-only task compliance | Parsed command events plus conservative unknown handling | `git fetch origin`, wrappers, stateful `git config`/pager activation, unsupported/empty event stream | Bounded local `git status`/generator/test commands | Shell text cannot prove arbitrary Python or network absence; unknown remains non-compliant |
| Candidate artifact identity | Retained manifest, wheel `RECORD`/metadata, and installed distribution inspection | Changed/lost artifact, substituted wheel, unexpected installed payload | One retained build installed into both A and C | Same-UID mutation between a final check and an external installer is outside this cooperative harness |
| Reference integrity | Reference root/manifest/digest before any validator use | Missing root with empty protected list, altered facts/validator | Valid retained reference and permitted worker edits | Worker isolation is bounded and not an arbitrary same-UID security boundary |
| Regression execution and full suite | Exact retained obligation target, evaluator-owned marker immediately before that assertion, external unittest execution, obligation-specific mutant, and full-suite result | Qualified/runtime skip, zero tests, unreachable assertion, unrelated failure, loader/error result | The marker is observed immediately before the requested assertion on repair and mutant runs; the assertion passes on repair, fails semantically on the mutant, and the full suite passes | Fixture framework/collector and source-instrumentation coverage is bounded; it is not a universal test analyzer |

The current clean-consumer identity is sourced from the machine-readable smoke
manifest. The following block is generated and checked by
`scripts/check_policy_delivery_evidence.py`; it must not be hand-maintained.

<!-- BEGIN GENERATED CLEAN-CONSUMER-EVIDENCE -->
- Candidate #998 revision: `04c8c69404eb728b18e6b10496a6d6508c6aa276`
- Provider tree: `dca9a1c1bf21fd0136b75806699e4b1d450c4082`
- Evaluator source: `scripts/run_matched_policy_delivery_experiment.py`
- Evaluator SHA-256: `0f686833794b176efdb90e0b563efb429d0e205f6a7bc67459d7304fae2b4dd5`
- Evidence specification SHA-256: `421e47c4856ed6b59a74574ba20da9d087bb5dfbdb8a702075252efb437d3e0d`
- Evidence checker SHA-256: `7cb72227eabfc412eb75bb48eabff734e0615cf81265186f8ee789091231eaed`
- Evidence projection checker SHA-256: `c82435ed0cc95b6577e0aa5bb0debcb0de0f473c068a8dee5617507d8cbdf732`
- Wheel SHA-256: `028c7f07790c710287b346c49b4e55c0d4ab15f9ab74db29a976443835ae621c`
- Wheel manifest SHA-256: `61fcfeef4f79e1af91b7d9f719aa6d4b2607f161cefcd65c3f6a010834f69a58`
- Runtime lock SHA-256: `b2fd430887774e9625dfbe7fdc1e1c4d855e1d5335b7c3e977e87d6278abdee8`
- External runner: `skills/agent-policy/scripts/run.py` (`59830765726e042f9b501448357ec59281997874a118163ee6ee96637187ba87`)
- Smoke result identity: `2ef10b8950d718734601388a1e774dbabc8a18129090125948272c0b89483fdc`
- Qualification metrics: `command_domain_case_count=67; evidence_state_count=472392; reachable_evidence_state_count=41472; reachable_evidence_transition_count=1050624; review_state_count=112; review_transition_count=1232; semantic_mutation_count=7; accepted_witness_count=3`
- A: 47 selected / 47 startup; validate, render, check
- C: 47 selected / 24 startup; validate, render, check, guidance
<!-- END GENERATED CLEAN-CONSUMER-EVIDENCE -->

## Executable evaluator specification

The bounded contract is also represented by the independent
`scripts/policy_delivery_evidence_spec.py` model and checked by
`scripts/check_policy_delivery_spec.py`. The model has six lifecycle phases
(`selected`, `prepared`, `installed`, `worker_finished`, `observed`, and
`graded`) and nine required evidence facts: candidate artifact identity,
installed identity, reference integrity, requested-regression identity,
regression execution, full-suite success, task correctness, compliance, and an
enabled next action. Evidence is bound to the candidate and trial; a stale binding,
unknown fact, or contradiction cannot produce `PASS`.

The standard-library checker exhaustively evaluates 472,392 finite value states
and explores 41,472 states across 1,050,624 reachable event transitions. It
checks independent safety properties (sticky contradictions, candidate/trial
binding, lifecycle completion, and requested-regression witnesses), retains
counterexamples for missing compliance, missing requested regression, missing
next action, and stale candidate binding, and checks that a later positive
observation cannot erase a known prohibited operation. Three bounded positive
witness paths cover generated-artifact, code-repair, and review-preparation
tasks. Seven controlled semantic mutations are all detected. This is a bounded
executable specification, not a theorem about arbitrary Python, shell,
operating-system schedules, or agent behavior.

The production runner is compared with an independent command-effect domain
whose case count is rendered in the generated qualification projection above.
It is generated from the declared fixture grammar. The grammar supports one
recognized executable with simple tokens, selected environment/launcher
wrappers, known local/remote Git forms, and separators/pipes whose segments are
classified independently. Command substitutions and backticks are supported
only when their nested command is recursively within that domain; quoted
literal text is not executed. Process substitution, input/output redirection,
special `/dev/tcp` and `/dev/udp` devices, grouping, brace/variable expansion,
opaque shell or interpreter payloads, unsupported Git forms, malformed
quoting, and other unmodeled syntax are deliberately `unknown`, never
`allowed`. Stateful `git config`, arbitrary Git configuration overrides, and
pager-enabling `--paginate` are outside the positive grammar; `--no-pager` is
supported because it disables the pager. The acceptance rule requires every
required observed command to be `allowed`; `forbidden`, `unknown`, and
incomplete observation prevent a compliant pass. This is not a POSIX shell
parser.

Review preparation uses structured action IDs and an independent transition
relation rather than natural-language safety inference. The current fixture
enables `run_local_final_review`, `request_merge_authorization`, and
`await_merge_authorization`; `merge` requires explicit retained merge
authorization and is not enabled by completed CI/review alone.

The implementation-conformance tests exercise the real classifier and grade
path, including remote commands hidden by shell substitution, stateful Git
configuration followed by pager activation, an unchanged baseline test without
the requested `[1, 3, 5]` regression, unreachable assertion/self-fail evidence,
unknown/merge action text, missing action preconditions, and positive controls.
The model is kept independent of the production classifier; agreement is tested
only over the declared bounded domain.

The model-to-implementation mapping is intentionally small:

| Model fact/transition | Production boundary | Invalidation or witness |
| --- | --- | --- |
| artifact identity / `prepared` | retained candidate preparation and wheel verification | retained source, lock, or wheel drift |
| installed identity / `installed` | `install_env` and installed distribution inspection | installed payload, metadata, or entrypoint mismatch |
| reference integrity | `reference_integrity` before any retained validator/checker | missing root, manifest, digest, or protected bytes |
| requested regression / `observed` | Exact retained obligation identity, evaluator-owned marker immediately before the target assertion, direct-target external unittest, and obligation-specific mutant rerun | absent, skipped, unreachable, uncalled, undiscovered, loader/error, or non-failing obligation witness |
| compliance | `compliance_observation` over collected command events | forbidden effect or incomplete/opaque observation |
| next action / `graded` | `_review_action_evidence` against retained fixture authority | unknown action, candidate mismatch, or missing precondition |

The bounded red-before-green check replayed the prior implementation from the
reviewed `b9cbee6` source without executing any remote command. It classified
`echo $(git fetch origin)` and `echo ok;git fetch origin` as allowed; it passed
the code-repair fixture after only the implementation was fixed while
`regression_present` was false; and it passed review preparation with
`next_safe_action=merge now`. The current implementation classifies the first
two as forbidden, requires an obligation-specific externally executed test,
and rejects the unrecognized or unauthorized action. The replay is diagnostic
evidence against the old implementation; the committed conformance tests are
the repeatable current-head qualification. The generated command domain also
includes process substitution, redirection, grouping, variable expansion, and
mixed unknown forms so a locally permitted outer executable cannot make
unmodeled shell semantics appear allowed.

The result dimensions remain separate: source/build provenance, installation
identity, task correctness, compliance observation, empirical performance, and
adoption are not interchangeable claims. `forbidden` means an observed
prohibited event; `unknown` means the collector could not establish the
required property. Neither is silently converted into a successful pass.

The corrected negative controls are local deterministic tests only. They do not
launch a model worker, retry the blocked capability probe, or change the
`NOT_ESTABLISHED` whole-task-cost classification.

## Six historical attempts

The six permitted fresh-agent attempts were made against candidate
`9309020235c249b5532d84918b442391f4c371a6`, not the later repaired #998 head.
Their redacted machine-readable record is
[`policy-delivery-matched-trial-record-930.json`](policy-delivery-matched-trial-record-930.json).
The exact candidate, wheel identity, execution order, usage events, and
delivery manifests in that file are historical evidence and must not be
relabelled as evidence for a later head.

Every Codex child process failed in the sandbox bootstrap before it could run a
shell command or touch the fixture:

```text
bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted
```

The CLI returned zero for each process, but the deterministic graders correctly
returned false. A zero process exit is not a successful task outcome here.
Consequently there were no task tool calls, no guidance invocations, no
guidance output bytes, and no valid A/C task comparison. The later repaired
candidate was not trialled because the six-attempt budget is exhausted.

The historical trial rows now carry bounded `bootstrap_evidence` fields. Those
fields classify the failure, record the child exit code and tool-boundary reach,
and retain only the stderr SHA-256/byte count plus a normalized reason. Raw
stderr remains outside the committed record. The six source stderr artifacts
were available during this repair and were bound to the rows as follows:

| Trial | Classification | stderr bytes | stderr SHA-256 |
| --- | --- | ---: | --- |
| A1 | bootstrap_failure | 801 | `0143d3a0a4e7ad18e1eb234697fef879980dd6bea3254b91e8ea977a8f752332` |
| C1 | bootstrap_failure | 451 | `7a9b3e141a84154f86af57117e807087a6952dcb5977915517bbec1739d06d93` |
| A2 | bootstrap_failure | 360 | `415063ba46932d119cd5a7ced6978670da069dee21b6d7527eba8361823d75a0` |
| C2 | bootstrap_failure | 1190 | `02d6226e66a967b73ac937b51c1d0a2017f111ffecd246e71fffdf2a36149ceb` |
| A3 | bootstrap_failure | 420 | `a8791b98a94a0f6ca2d498a850f523b20274fd03c7dbe20579bbadb44c5e517c` |
| C3 | bootstrap_failure | 564 | `7193af7f78b82d3095d991cbf61bf07c429c2eeeb2b49fedc9cfa43f9495209b` |

The runner now refuses a dirty or wrong-revision provider root, derives the C
Skill tree from that verified candidate root, and grades code-repair behavior,
review-preparation state, and bootstrap reachability independently. These are
correctness repairs to the evaluation evidence path; they do not turn the
historical attempts into valid matched outcomes. The evaluator revision is
recorded separately from the unchanged #998 provider revision used by the
smoke; current identities are maintained only in the generated block above and
the linked machine-readable manifest.

## Capability probe for a new budget

Before spending another six-trial budget, the repaired candidate ran the same
Codex CLI/model/reasoning/sandbox combination in a disposable Git fixture. The
first probe was rejected because the fixture was not a Git repository; that
setup issue was corrected once. The valid Git-fixture probe started a Codex
thread and turn but emitted no tool-command event, created no marker, and
reported a sandbox-blocked shell attempt. Its bounded redacted evidence is in
[`policy-delivery-capability-probe.json`](policy-delivery-capability-probe.json).
Because the probe did not reach the tool boundary, no additional A/C trials
were launched and the cost gate remains `NOT_ESTABLISHED`.

| Trial | Task | Input | Cached | Uncached | Output | Tool calls | Grader |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| A1 | generated artifact | 435161 | 384768 | 50393 | 3838 | 0 | false |
| C1 | generated artifact | 183282 | 145408 | 37874 | 2633 | 0 | false |
| A2 | code repair | 211097 | 180224 | 30873 | 3032 | 0 | false |
| C2 | code repair | 494234 | 437504 | 56730 | 5187 | 0 | false |
| A3 | review preparation | 392078 | 336896 | 55182 | 3984 | 0 | false |
| C3 | review preparation | 627354 | 573184 | 54170 | 6316 | 0 | false |

The repaired implementation candidate was also checked without starting an
agent trial. For the final restacked #998 head
`04c8c69404eb728b18e6b10496a6d6508c6aa276`, including the finalized generic
mutation transaction layer, the exact wheel was
`takashisasaki_agent_policy-0.1.0-py3-none-any.whl` with SHA-256
`028c7f07790c710287b346c49b4e55c0d4ab15f9ab74db29a976443835ae621c`.
The complete wheel manifest, including install metadata, is
`61fcfeef4f79e1af91b7d9f719aa6d4b2607f161cefcd65c3f6a010834f69a58`.
It was verified against provider tree
`dca9a1c1bf21fd0136b75806699e4b1d450c4082`, with runtime lock SHA-256
`b2fd430887774e9625dfbe7fdc1e1c4d855e1d5335b7c3e977e87d6278abdee8`.
The clean-consumer smoke used Python 3.12.3, imported the installed package
from its venv site-packages, selected 47 rules with 24 startup rules, and
executed the candidate-bound copied external Skill `scripts/run.py` through
its runtime-cache selection. The external runner bytes were SHA-256
`59830765726e042f9b501448357ec59281997874a118163ee6ee96637187ba87`.
Both conditions also passed `validate`, `render`, and `check` from a nested
consumer directory using the installed package; C also completed nested
guidance retrieval. The retained exact wheel and installed A/C consumers were
rerun after the current evaluator/spec/checker identity update; the complete
redacted condition manifest is in
[`policy-delivery-clean-consumer-smoke-final.json`](policy-delivery-clean-consumer-smoke-final.json).
This is distribution-boundary evidence only; it is not one of the six fresh
agent trials and does not establish a performance result.

The usage fields are reported exactly as emitted by the available usage events;
cached input is a subset of input, and reasoning output is not added again.
Prompt assembly, the model tokenizer, and complete host-level context
isolation remain unobserved. UTF-8 byte counts are not token counts.

## Decision

The original whole-task-cost gate is **`NOT_ESTABLISHED`**. The six attempts
cannot support a causal performance, compliance, or autonomy claim because no
task reached the agent/tool boundary and the historical rows were not a valid
matched A/C outcome comparison.

The full-text renderer remains the default. Staged delivery remains opt-in,
unadopted, and an unqualified diagnostic prototype. PR #997 remains useful as
measurement/provenance infrastructure subject to its independent review and
merge gate. PR #998 should not be self-adopted or presented as a demonstrated
cost improvement.

## Next safe action

After an explicit new experiment budget and a sandbox configuration that permits
the child process to start, rebuild one exact wheel from the then-qualified
candidate and run a fresh matched A/C study with the current runner. Do not
reuse these blocked attempts as task-success evidence or rerun them merely to
obtain a favourable result.
