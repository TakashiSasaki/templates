# Staged Policy-Delivery Experiment Report: Resumed Baseline and Capability Qualification

**Final Empirical Classification**: **`NOT_ESTABLISHED`**  
**Valid Matched Pairs**: **0**  
**Automated Review Status**: `unavailable_due_quota`  
**Execution Environment**: Google Anti-Gravity / Gemini 3.8 Flash (Middle reasoning effort)  

---

## 1. Executive Summary

This durable repository report records the completed experiment phase for the staged Policy-delivery research question:

> «Can the normal full-text Policy instruction delivery be replaced, for a selected coding-agent workflow, by a substantially smaller startup "AGENTS.md" plus authenticated on-demand "policy-guidance", while preserving task correctness and reducing whole-task cost?»

Following the landed Policy baseline (`ac95d6ee681ef422c0a8e1f714e94fbc78ff83aa`, PRs #997–#1002 merged), the baseline and execution protocol were frozen in [`docs/policy-delivery-experiment-baseline.json`](policy-delivery-experiment-baseline.json). The Phase 2 capability qualification probe evaluated criteria C1–C8 against a disposable Git fixture. All eight criteria were **`NOT_ESTABLISHED`**, yielding a capability decision of **`NOT_QUALIFIED`**. Under the predeclared stopping rule, matched model trials were not authorized to run. The whole-task-cost classification remains **`NOT_ESTABLISHED`**.

---

## 2. Baseline and Protocol Identity

- **Exact `policy` Baseline Revision**: [`ac95d6ee681ef422c0a8e1f714e94fbc78ff83aa`](https://github.com/TakashiSasaki/templates/commit/ac95d6ee681ef422c0a8e1f714e94fbc78ff83aa)
- **Candidate Provider Tree**: `a5a934b20de544a698eae318fd478c62815e0399`
- **Machine-Readable Baseline Plan**: [`docs/policy-delivery-experiment-baseline.json`](policy-delivery-experiment-baseline.json) (SHA-256: `f30daf31052a7bb92d060edcf1111e6d644239725978b9b5189610128e079bd4`)
- **Machine-Readable Evidence Report**: [`docs/policy-delivery-experiment-report.json`](policy-delivery-experiment-report.json)
- **Evaluator Source Identity**:
  - `scripts/run_matched_policy_delivery_experiment.py` (SHA-256: `4e38851dc6608d2a4d59bd7fce0cbbeffe9715842bd205854e8a1308d8d739ac`)
- **Evidence Specification & Checkers**:
  - `scripts/policy_delivery_evidence_spec.py` (SHA-256: `f64185a722afe2fb0ba8e55df96b750067465e7e809067ef9c2f61d676347d51`)
  - `scripts/check_policy_delivery_spec.py` (SHA-256: `2fc1b1adb31eba427729218c03c7c35e5f6a27795651d0feb04693e793b34f1a`)
  - `scripts/check_policy_delivery_evidence.py` (SHA-256: `c82435ed0cc95b6577e0aa5bb0debcb0de0f473c068a8dee5617507d8cbdf732`)
- **Runtime Lock Identity**: `.agent-policy.lock` (SHA-256: `ee092ecec223cf0995b8310554cec5a6652a6718d362ab10167f0bf2885f0ef3`)
- **Candidate Wheel Identity**: `takashisasaki_agent_policy-0.1.0-py3-none-any.whl` (SHA-256: `028c7f07790c710287b346c49b4e55c0d4ab15f9ab74db29a976443835ae621c`)
- **Staged Template**: `templates/AGENTS-staged.md.j2` (SHA-256: `3261d1855c6a7eb99bdb694391dc14988b03dfa994c2404a276cf9ba0297e143`)
- **Presentation Map**: `delivery/presentation-map.yml` (SHA-256: `e908150306a2bf64f4c18b279cb35d3ea34ca47b63814a162d8fac2d5137df0b`)
- **Policy Guidance Skill**: `skills/policy-guidance/SKILL.md` (SHA-256: `97dbb4bec5367480cef1612eece414b4b3ccbfc7980831d2430b7a7801714c52`)

---

## 3. Execution Environment

- **Coding Agent**: Google Anti-Gravity
- **Model**: Gemini 3.8 Flash
- **Thinking / Reasoning Effort**: Middle
- **Sandbox Mode**: `workspace-write` / isolated disposable Git fixture
- **Permissions**: Existing host permissions; no global setting changes; no dangerous bypass
- **Network Policy**: Enforced local only; no network access permitted

---

## 4. Capability Qualification Results (C1–C8)

A bounded execution and enforcement probe was run against a disposable Git repository fixture:

| ID | Capability Requirement | Status | Concrete Evidence Basis |
| :--- | :--- | :--- | :--- |
| **C1** | Can the worker start normally? | `NOT_ESTABLISHED` | Worker CLI bootstrap failed. Codex CLI fails immediately at startup turn due to exhausted usage limit (`https://chatgpt.com/codex/settings/usage`) and Linux container sandbox unavailability (`bwrap: loopback: Failed RTM_NEWADDR`); host lacks standalone non-interactive CLI runner for Anti-Gravity/Gemini conforming to evaluator command stream. |
| **C2** | Can it reach the intended tool/workspace boundary? | `NOT_ESTABLISHED` | Worker process failed before emitting structured tool command events; tool/workspace boundary was not reached in disposable fixture. |
| **C3** | Can it perform one harmless local workspace action? | `NOT_ESTABLISHED` | No autonomous tool action executed in the fixture. |
| **C4** | Can the evaluator observe that action? | `NOT_ESTABLISHED` | Evaluator command-event collector received no structured events. |
| **C5** | Can opaque worker execution be covered by a trusted enforcement boundary? | `NOT_ESTABLISHED` | Host lacks kernel-level sandbox/supervisor (no unprivileged user namespaces, no bwrap, no seccomp/eBPF) to intercept and enforce opaque worker execution. |
| **C6** | Can control-plane integrity be established independently of worker text? | `NOT_ESTABLISHED` | Host lacks independent filesystem/audit boundary to verify Git control-plane paths (`.git/config`, hooks, refs) independently of worker self-report. |
| **C7** | Can the required network policy be independently established? | `NOT_ESTABLISHED` | Host lacks per-process network namespace or firewall isolation to independently enforce network absence. |
| **C8** | Can those enforcement facts be bound to the exact same trial/reference identity? | `NOT_ESTABLISHED` | Without C5–C7, no trusted enforcement witness conforming to `policy-worker-boundary-v1` with trial ID and reference digest can be produced. |

**Capability Decision**: **`NOT_QUALIFIED`** (Missing facts: C1, C2, C3, C4, C5, C6, C7, C8).

---

## 5. Trial Authorization and Execution

- **Were Matched Trials Authorized to Run?**: **NO**.
  - *Reason*: Under the predeclared stopping rule, model trials are strictly gated on Phase 2 qualification. When capability is `NOT_QUALIFIED`, consuming the six-trial budget is unauthorized.
- **Trials Executed**: **0** (budget preserved; no trials run).
- **Exact Trial Identities and Results**: None.
- **Valid Matched-Pair Count**: **0**.

---

## 6. Correctness and Compliance Results

- **Task Correctness**: `NOT_EVALUATED` (no trials reached execution).
- **Policy Compliance**: `NOT_EVALUATED` (no trials reached execution).

---

## 7. Observed Whole-Task Cost Metrics

All cost metrics are explicitly **`UNAVAILABLE`** because no matched model trials were executed:

| Metric | Status / Value |
| :--- | :--- |
| **Total input tokens** | `UNAVAILABLE` |
| **Cached input tokens** | `UNAVAILABLE` |
| **Uncached input tokens** | `UNAVAILABLE` |
| **Output tokens** | `UNAVAILABLE` |
| **Reasoning output tokens** | `UNAVAILABLE` |
| **Tool round trips** | `UNAVAILABLE` |
| **Failed tool calls** | `UNAVAILABLE` |
| **Policy guidance round trips** | `UNAVAILABLE` |
| **Guidance retrieved bytes** | `UNAVAILABLE` |
| **Repeated guidance retrievals** | `UNAVAILABLE` |
| **Wall-clock duration** | `UNAVAILABLE` |
| **Retry / failure overhead** | `UNAVAILABLE` |

---

## 8. Final Empirical Classification

**`NOT_ESTABLISHED`**

**Rationale**:
1. Trial validity could not be established due to lack of trusted enforcement capability (C1–C8 `NOT_ESTABLISHED`).
2. Valid matched pairs = 0.
3. In accordance with the decision hierarchy (1. trial validity → 2. task correctness → 3. policy/compliance evidence → 4. whole-task cost), cost cannot be evaluated when validity is unestablished.

---

## 9. Limitations and Residual Uncertainty

1. **Host Sandbox Restrictions**: The host Linux container environment lacks unprivileged user namespace / loopback configuration privileges, causing bubblewrap (`bwrap`) to fail.
2. **Quota Exhaustion**: External Codex CLI quota is exhausted until Sep 25, 2026.
3. **Runner Interface**: The Google Anti-Gravity / Gemini environment currently lacks an external standalone non-interactive CLI runner interface that connects directly to `scripts/run_matched_policy_delivery_experiment.py`'s JSONL event stream.
4. **Enforcement Boundary**: Without an independent trusted enforcement supervisor (covering opaque Python execution, Git control-plane integrity, and network isolation), worker compliance remains `UNKNOWN` under the evaluator's strict evidence contract.

---

## 10. Confirmation of Unchanged Invariants

- **Default Renderer**: Unchanged. Full-text `agents-md` remains the default.
- **Staged Delivery Adoption**: None. Staged delivery remains opt-in and unadopted.
- **Authority / Publication Pins**: No downstream repin, promotion, or deployment was performed.
- **Git State**: No direct mutation was made to `policy`. All changes are isolated in a pull request.

---

## 11. Automated Review Status

`automated_review = unavailable_due_quota`

The user explicitly authorized proceeding without an additional automated Codex review due to exhausted quota. The review gate was replaced by the manual exact-head qualification packet:
1. Changed-file/scope audit: Changes strictly confined to documentation and evidence files (`docs/policy-delivery-experiment-baseline.json`, `docs/policy-delivery-capability-probe.json`, `docs/policy-delivery-experiment-report.json`, `docs/policy-delivery-experiment-report.md`, `docs/policy-delivery-matched-experiment.md`).
2. Requirement-to-evidence audit: All C1–C8 criteria evaluated with concrete host evidence.
3. Sibling/negative-control audit: Verified consistency checkers reject stale or tampered projections.
4. Focused tests & preflight: Local `run_policy_preflight.py` passed (595 tests, compile, lint, focused tests, evidence consistency, self-check).
5. Exact-head CI: All 8 GitHub Actions checks passed on PR #1003.

---

## 12. Next Safe Action

Preserve **`NOT_ESTABLISHED`**. Do not attempt to run un-enforced trials or infer compliance from un-isolated command streams. If empirical comparison is to be pursued in a future cycle, establish an independent trusted enforcement capability investment (providing verified kernel sandbox isolation, independent control-plane integrity verification, and isolated network policy enforcement conforming to `policy-worker-boundary-v1`) before initiating model trial execution.
