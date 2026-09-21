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
both isolated consumers. It first retains a verified candidate source/artifact
snapshot, builds the wheel used by both conditions from that snapshot, and
revalidates the snapshot before each installation, render, and trial use. Its
staged path invokes the actual external
`skills/agent-policy/scripts/run.py` and its lock-selected runtime cache; it
does not generate a test-only wrapper.

## Current evaluation-integrity contract

The evaluation runner is qualified as a diagnostic harness, not as a
performance result. Candidate source, runtime-lock bytes, Skill bytes, and the
wheel are retained from the verified provider revision. Wheel verification
covers package payloads and the complete install metadata closure, including
`METADATA`, `WHEEL`, `RECORD`, and declared console entry points. A changed or
lost retained file fails closed before it is used.

Each disposable task has a pre-trial reference outside the worker fixture.
Protected generators, checkers, evidence, and validators are compared with
that reference. Generated-artifact grading runs the retained checker against
the worker's outputs; review preparation is graded against retained expected
facts rather than executing a worker-modifiable validator. A common grade
composition requires task correctness, reference integrity, policy compliance,
and evidence validity, so an observed prohibited operation prevents a pass
for every task type.

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
historical attempts into valid matched outcomes.

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
The evaluator source used for this smoke has SHA-256
`6635ebbe1e4fd265c10b600d2d9c719d1c469bfc32a4ed20dc111175e8beabca`.
The clean-consumer smoke used Python 3.12.3, imported the installed package
from its venv site-packages, selected 47 rules with 24 startup rules, and
executed the candidate-bound copied external Skill `scripts/run.py` through
its runtime-cache selection. The external runner bytes were SHA-256
`59830765726e042f9b501448357ec59281997874a118163ee6ee96637187ba87`.
Both conditions also passed `validate`, `render`, and `check` from a nested
consumer directory using the installed package; C also completed nested
guidance retrieval. This smoke was rerun after the retained-artifact and
independent-grading repair; the complete redacted condition manifest is in
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
