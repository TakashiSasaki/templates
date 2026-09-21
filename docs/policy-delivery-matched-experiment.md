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
both isolated consumers. Its staged path invokes the actual external
`skills/agent-policy/scripts/run.py` and its lock-selected runtime cache; it
does not generate a test-only wrapper.

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

| Trial | Task | Input | Cached | Uncached | Output | Tool calls | Grader |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| A1 | generated artifact | 435161 | 384768 | 50393 | 3838 | 0 | false |
| C1 | generated artifact | 183282 | 145408 | 37874 | 2633 | 0 | false |
| A2 | code repair | 211097 | 180224 | 30873 | 3032 | 0 | false |
| C2 | code repair | 494234 | 437504 | 56730 | 5187 | 0 | false |
| A3 | review preparation | 392078 | 336896 | 55182 | 3984 | 0 | false |
| C3 | review preparation | 627354 | 573184 | 54170 | 6316 | 0 | false |

The repaired evaluation candidate was also checked without starting an agent
trial. For #998 head
`6ee2ff1d006c91bce3fdf45e4e916e2933ae6223`, the exact wheel was
`takashisasaki_agent_policy-0.1.0-py3-none-any.whl` with SHA-256
`1d7155a21a47e3de258382d1f83ee2712a9cdd37b0a6129e40e6f85099a33638`.
The clean-consumer smoke used Python 3.12.3, imported the installed package
from its venv site-packages, selected 47 rules with 24 startup rules, and
executed the copied external Skill `scripts/run.py` through its runtime-cache
selection. The external runner bytes were SHA-256
`59830765726e042f9b501448357ec59281997874a118163ee6ee96637187ba87`.
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
