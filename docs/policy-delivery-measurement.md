# Policy delivery measurement

This document records the reproducible baseline and experiment protocol for
improving the presentation of selected Policy rules. It measures delivery
surfaces without changing Policy meaning, selection, severity, or enforcement.

## Current baseline

The baseline is generated with:

```bash
python3 scripts/measure_policy_delivery.py --repository . --format markdown
```

The measurement command uses the canonical `agent_policy.policy_loader` and
records the exact repository head, tree, configuration, toolchain identity,
source identities, generated output identities, UTF-8 byte counts, and line
counts. Enabled configured outputs include both their primary path and any
declared staged detail bundle. Generated Skill files are inventoried separately
from startup instructions. The report records the configured/adopted toolchain
identity separately from the executing package/module identity, and refuses to
label a checkout as an adopted-revision reconstruction without that evidence.
It does not print policy bodies, secrets, protected prompts, or session
transcripts.

At the initial baseline on 2026-09-21:

| Surface | Observed value |
| --- | ---: |
| Coding rules selected | 47 |
| Selected rule source bodies | 87,939 bytes / 641 lines |
| Generated `AGENTS.md` | 98,383 bytes / 862 lines |
| Generated review projection | 52,231 bytes / 623 lines |
| Generated Skills | 312,904 bytes / 4,423 lines |

The host was observed as Codex CLI `0.154.0` on Ubuntu arm64 with Python
3.12.3. The host did not expose an authorized record of exact prompt assembly,
per-file inclusion, truncation, or the model tokenizer. Those values remain
`Unobserved`; file size is not treated as prompt-token evidence.

## Frozen comparison protocol

The comparison uses fresh isolated processes and disposable fixture
repositories. Each trial uses the same short task wording, model/build,
permissions, tools, and task limit for all conditions. The parent conversation
and this implementation prompt are not injected into trial workers.

The conditions are:

| Condition | Delivery |
| --- | --- |
| A | Current actual configuration and host discovery behavior |
| B | Complete current full-text delivery, using an isolated per-process setting only when the host supports it |
| C | Opt-in staged startup projection with on-demand authenticated detail bundle |

The pilot is capped at six fresh agent trials and two concurrent workers. If A
and B are distinct and B is supported, use two task cases across A/B/C. If A and
B are equivalent or B cannot be represented safely, use three task cases across
A/C and report B as reconstructed or unavailable.

The deterministic rubric covers read-only investigation, a small repair with a
regression, generated-file handling, review-readiness preparation,
merge/publication preparation without the remote action, detail retrieval
before a dependent action, and a transition into a new operation.

Record per-trial tool calls, turns, wall time, input/cache/output usage, failed
retrievals, clarification or stop events, required-rule retrieval timing,
observed policy violations, and unnecessary procedure work when exposed. A
correct refusal, handoff, or wait for missing evidence is not scored as a
failure of autonomy.

Results are reported with sample size and dispersion. A small pilot does not
support a universal token-saving or compliance claim.

## Decision gate

The staged renderer is implemented only if the baseline or isolated pilot
shows a delivery problem that it addresses without a compliance regression or
an increase in whole-task cost. If the evidence is inconclusive, the measurement
and protocol remain useful diagnostics and the existing full-text self-host
output stays unchanged.

## Execution record

The first bounded pilot ran on 2026-09-21 JST with six fresh read-only CLI
trials, two per condition, and no remote actions. The CLI was Codex `0.154.0`.
The usage values below are the host's `turn.completed` accounting; they are not
an observation of the exact model prompt assembly.

| Condition | Input tokens (two trials) | Cached input | Output tokens | Result |
| --- | ---: | ---: | ---: | --- |
| A, current full output | 38,487 / 38,345 | 27,136 / 27,136 | 685 / 560 | 2/2 correct |
| B, isolated complete-output setting | 62,389 / 30,965 | 39,424 / 8,960 | 774 / 151 | 2/2 correct |
| C, opt-in staged output | 78,661 / 78,678 | 65,536 / 65,536 | 1,043 / 1,215 | 2/2 correct |

The static projection comparison for the same 47 selected rules was:

| Surface | UTF-8 bytes | Lines |
| --- | ---: | ---: |
| Existing full `AGENTS.md` | 98,383 | 862 |
| Staged startup `AGENTS.md` | 30,214 | 327 |
| Authenticated detail bundle | 146,587 | 1,706 |
| Grouped retrieval Skill | 8,229 | — |

The staged trials retrieved the requested operation-specific rule IDs and
reported them correctly. Two pre-existing generated Skills in the disposable
fixture emitted frontmatter warnings; the trials still completed, and this is
recorded as an environment warning rather than treated as a delivery win.
Input variance and the staged retrieval cost mean this six-trial pilot does
not demonstrate a whole-task token or time reduction. It does demonstrate a
reproducible smaller startup projection with complete, authenticated,
on-demand detail. The staged renderer therefore remains explicitly opt-in;
the current `agents-md` self-host output, Policy semantics, and global agent
settings are unchanged. A later adoption decision requires a clean installed
consumer experiment with direct discovery evidence.

## Measurement and decision-gate disposition

The original six-trial record did not establish the whole-task-cost condition
in the predeclared gate. Its input, cache, output, and retrieval observations
are too sparse and too variable to prove a reduction, and exact prompt
assembly, model-tokenizer boundaries, and complete condition isolation were not
observed. The gate is preserved; it is not retroactively redefined from the
observed results.

The staged renderer is therefore an explicitly opt-in, non-default, unqualified
experimental prototype for diagnostics. It is not a supported delivery mode,
has not been adopted by the self-host configuration, and has not changed
Policy semantics, global agent settings, or downstream pins. The redacted
per-trial record is committed in
[`policy-delivery-trial-record.json`](policy-delivery-trial-record.json).
Missing historical artifacts remain labelled `Unobserved`; no exact prompt or
hidden reasoning has been reconstructed.

The aggregate log measurement uses read-only SQLite metadata and the approved
`target`/`estimated_bytes` aggregate columns. Its digest identifies the
exported aggregate, not the physical database file, and the report explicitly
does not claim that SQLite never touched unselected pages.
