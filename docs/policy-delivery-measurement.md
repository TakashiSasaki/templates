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
counts. It does not print policy bodies, secrets, protected prompts, or session
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
