# Staged Policy-Delivery Experiment Report: Resumed Baseline and Capability Qualification

**Final Empirical Classification**: **`NOT_ESTABLISHED`**  
**Valid Matched Pairs**: **0**  
**Automated Review Status**: `unavailable_due_quota`  
**Execution Environment**: Google Anti-Gravity / Gemini 3.8 Flash (Middle reasoning effort)  

---

## 1. Executive Summary

This durable repository report records the completed experiment phase for the staged Policy-delivery research question:

> «Can the normal full-text Policy instruction delivery be replaced, for a selected coding-agent workflow, by a substantially smaller startup "AGENTS.md" plus authenticated on-demand "policy-guidance", while preserving task correctness and reducing whole-task cost?»

Following the landed Policy baseline (`ac95d6ee681ef422c0a8e1f714e94fbc78ff83aa`, PRs #997–#1002 merged) and the implementation of the real Google Anti-Gravity (`agy`) worker backend and evaluator infrastructure (PR #1004, `3d05429778d091412a754e58e4773687e29116f7`), the baseline and execution protocol were frozen in [`docs/policy-delivery-experiment-baseline.json`](policy-delivery-experiment-baseline.json). The Phase 2 capability qualification probe evaluated criteria C1–C9 with `agy`. Criteria C1, C2, C3, C4, and C9 were **`ESTABLISHED`**, C6 was **`NOT_APPLICABLE`** (evaluated against a non-Git fixture where `.git` absence was explicitly verified), and C5, C7, and C8 were **`NOT_ESTABLISHED`** due to host sandbox supervisor failure (`connection reset by peer`) and lack of kernel-level network namespace or firewall isolation. This yielded a capability decision of **`NOT_QUALIFIED`**. Under the predeclared stopping rule, matched model trials were not authorized to run. The whole-task-cost classification remains **`NOT_ESTABLISHED`**.

---

## 2. Baseline and Protocol Identity

- **Exact `policy` Baseline Revision**: [`ac95d6ee681ef422c0a8e1f714e94fbc78ff83aa`](https://github.com/TakashiSasaki/templates/commit/ac95d6ee681ef422c0a8e1f714e94fbc78ff83aa)
- **Candidate Provider Tree**: `a5a934b20de544a698eae318fd478c62815e0399`
- **Experiment Infrastructure Candidate Revision**: [`3d05429778d091412a754e58e4773687e29116f7`](https://github.com/TakashiSasaki/templates/commit/3d05429778d091412a754e58e4773687e29116f7) (PR #1004, `feat/policy-delivery-agy-worker-backend`)
- **Machine-Readable Baseline Plan**: [`docs/policy-delivery-experiment-baseline.json`](policy-delivery-experiment-baseline.json) (SHA-256: `d1f013236d8511e225498c54a150ceb7c1b292c4ff425afe510fd0a7ecbd4ad7`)
- **Machine-Readable Capability Probe Record**: [`docs/policy-delivery-capability-probe.json`](policy-delivery-capability-probe.json) (SHA-256: `9c468ac7567685ec680c383dfed1b1e088e1f905afd3eadb24f71941bf77f30e`)
- **Machine-Readable Evidence Report**: [`docs/policy-delivery-experiment-report.json`](policy-delivery-experiment-report.json) (SHA-256: `2b373ab5ded93bfb952c714db903deabe7700cc61b74bed0a56de60d476af143`)
- **Evaluator Source Identity**:
  - `scripts/run_matched_policy_delivery_experiment.py` (SHA-256: `b36eaa3a6c007a43e520ece2c581b34f006a5f8535345752ab5d42da797ef6c3`)
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

## 3. Execution Environment and Separation of Enforcement

- **Coding Agent**: Google Anti-Gravity
- **Worker Backend**: `agy` (CLI v1.2.8, binary SHA-256: `f71174a3d6dc9aac258511363ed8419a591edc3dbd24607ca48132912c98f96d`)
- **Model**: Gemini 3.8 Flash (`gemini-3.8-flash-medium`)
- **Thinking / Reasoning Effort**: Middle (`medium`)
- **Fixture Mode**: `non-git` (verified `.git` absent in fixture directory)
- **Positive Worker Probe Mode**: Headless non-interactive execution via `--mode accept-edits --output-format stream-json`
- **Sandbox Requested**: `true` (`--sandbox` / terminal restrictions enabled)
- **Sandbox Effective Status**: `FAILED_OR_UNAVAILABLE` (connection reset on unix socket: `connecting to sandbox server: read unix @->@: recvmsg: connection reset by peer`; host lacks kernel user namespaces, bwrap, or seccomp supervision)
- **Permission Mode**: `accept-edits`
- **Fallback / Bypass Status**: Sandbox bypass required for worker execution on this host
- **Required Network Policy**: Prohibited / local only (no network access permitted during worker execution)
- **Qualified Network Enforcement**: `NOT_ESTABLISHED` (host lacks per-process kernel network namespace or firewall packet filtering to independently verify or enforce network absence; headless permission rejection is not kernel-level network enforcement)

---

## 4. Capability Qualification Results (C1–C9)

A bounded execution and enforcement probe (`probe-agy-gemini38flash-20260922t064419z`) was executed against a disposable non-Git fixture:

| ID | Capability Requirement | Status | Concrete Evidence Basis |
| :--- | :--- | :--- | :--- |
| **C1** | Can the worker start normally? | `ESTABLISHED` | Worker CLI bootstrapped normally. Google Anti-Gravity CLI (`agy` v1.2.8) executed non-interactively using `--mode accept-edits --output-format stream-json` with model `gemini-3.8-flash-medium` and reasoning effort `medium`, exiting with code 0. |
| **C2** | Can it reach the intended tool/workspace boundary? | `ESTABLISHED` | Worker successfully reached the tool/workspace boundary in disposable fixtures, emitting structured `step_update` tool events in `stream-json` output format. |
| **C3** | Can it perform one harmless local workspace action? | `ESTABLISHED` | Worker successfully performed harmless local workspace actions (`view_file` on `/tmp/test.txt` and local command execution). |
| **C4** | Can the evaluator observe that action? | `ESTABLISHED` | Evaluator command-event collector observed and verified structured tool events, parameters, exit codes, and output bytes from `agy` `stream-json` output. |
| **C5** | Can opaque worker execution be covered by a trusted enforcement boundary? | `NOT_ESTABLISHED` | Host environment lacks an active sandbox supervisor (connecting to sandbox server returns `read unix @->@: recvmsg: connection reset by peer`), requiring sandbox bypass for execution; host lacks kernel-level unprivileged user namespaces, bwrap, or seccomp syscall supervision to intercept and enforce opaque worker execution. |
| **C6** | Can control-plane integrity be established independently of worker text? | `NOT_APPLICABLE` | Evaluated in non-Git fixture mode where Git control plane integrity is not applicable; in this fixture, `.git` was explicitly verified absent (`git_control_plane_present = false`); in Git fixture mode, host lacks independent filesystem integrity monitoring for `.git` control plane mutations. |
| **C7** | Can the required network policy be independently established? | `NOT_ESTABLISHED` | Host environment lacks per-process kernel network namespace or firewall isolation to independently enforce network absence during worker execution. Headless application-level permission rejection does not constitute kernel-level network enforcement. |
| **C8** | Can those enforcement facts be bound to the exact same trial/reference identity? | `NOT_ESTABLISHED` | Because C5 and C7 cannot be established, no trusted enforcement witness conforming to `policy-worker-boundary-v1` bound to the exact trial ID and reference digest can be produced. |
| **C9** | Can whole-task cost / token usage be observed? | `ESTABLISHED` | `agy` `stream-json` exposes complete whole-task token usage in its final `result` event (`input_tokens`: 22505, `output_tokens`: 258, `thinking_tokens`: 190, `cache_read_tokens`: 12216, `total_tokens`: 22763). |

**Capability Decision**: **`NOT_QUALIFIED`** (Missing facts: C5, C7, C8).

---

## 5. C8 Trusted Enforcement Witness Specification

The predeclared protocol requires an evaluator-owned witness conforming to `policy-worker-boundary-v1`:

```json
{
  "schema": "policy-worker-boundary-v1",
  "trial_id": "<trial-id>",
  "reference_digest": "<sha256>",
  "infrastructure_revision": "3d05429778d091412a754e58e4773687e29116f7",
  "agy_identity": "/home/ubuntu/.local/bin/agy (v1.2.8, sha256: f71174a3...)",
  "model_runtime_identity": "gemini-3.8-flash-medium (effort: medium)",
  "sandbox_enforcement_identity": "<supervisor-id-and-status>",
  "network_enforcement_identity": "<netns-or-firewall-status>",
  "run_log_identity": "<sha256>",
  "opaque_worker_code": "enforced",
  "control_plane_integrity": "verified",
  "network_policy": "enforced"
}
```

Because C5 and C7 could not be established on this host, this witness is **absent** (`status: NOT_ESTABLISHED`).

---

## 6. Whole-Task Cost Metric Determination

The primary cost metric semantics are frozen as follows:
- **Primary Metric**: `total_tokens = input_tokens + output_tokens` (observed probe value: 22,763).
- **Cache Accounting**: `cache_read_tokens` (12,216) is a sub-metric of `input_tokens` (22,505); uncached input tokens = 10,289.
- **Reasoning Accounting**: `thinking_tokens` (190) is a sub-metric of `output_tokens` (258); standard output tokens = 68.
- **Double-Counting Prohibition**: `thinking_tokens` is already included within `output_tokens` and must not be added to `total_tokens` again; `cache_read_tokens` is already included within `input_tokens` and must not be added to `total_tokens` again.
- **Missing-Usage Rule**: Any trial run lacking structured usage in its terminal result event is invalid; no estimation or fabrication is permitted.

---

## 7. Trial Authorization and Execution

- **Were Matched Trials Authorized to Run?**: **NO**.
  - *Reason*: Under the predeclared stopping rule, model trials are strictly gated on Phase 2 qualification. When capability is `NOT_QUALIFIED`, consuming the six-trial budget is unauthorized.
- **Trials Executed**: **0** (budget preserved; zero trials run).
- **Exact Trial Identities and Results**: None.
- **Valid Matched-Pair Count**: **0**.

---

## 8. Correctness and Compliance Results

- **Task Correctness**: `NOT_EVALUATED` (no trials reached execution).
- **Policy Compliance**: `NOT_EVALUATED` (no trials reached execution).

---

## 9. Observed Whole-Task Cost Metrics

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

## 10. Final Empirical Classification

**`NOT_ESTABLISHED`**

**Rationale**:
1. Trial validity could not be established due to lack of trusted enforcement capability (C5, C7, C8 `NOT_ESTABLISHED`).
2. Valid matched pairs = 0.
3. In accordance with the decision hierarchy (1. trial validity → 2. task correctness → 3. policy/compliance evidence → 4. whole-task cost), cost cannot be evaluated when validity is unestablished.

---

## 11. Limitations and Residual Uncertainty

1. **Host Sandbox and Network Isolation**: The host Linux container environment lacks an active sandbox supervisor (connection reset on unix socket) and kernel-level network namespace/firewall isolation.
2. **Enforcement Boundary**: Without an independent trusted enforcement supervisor (covering opaque worker execution and network isolation), worker compliance remains `UNKNOWN` under the evaluator's strict evidence contract.

---

## 12. Confirmation of Unchanged Invariants

- **Default Renderer**: Unchanged. Full-text `agents-md` remains the default.
- **Staged Delivery Adoption**: None. Staged delivery remains opt-in and unadopted.
- **Authority / Publication Pins**: No downstream repin, promotion, or deployment was performed.
- **Git State**: No direct mutation was made to `policy`. All changes are isolated in a stacked pull request.

---

## 13. Automated Review Status

`automated_review = unavailable_due_quota`

The user explicitly authorized proceeding without an additional automated Codex review due to exhausted quota. The review gate was replaced by the manual exact-head qualification packet:
1. Changed-file/scope audit: Changes strictly confined to documentation, evidence files, and consistency checks.
2. Requirement-to-evidence audit: All C1–C9 criteria evaluated with concrete host evidence.
3. Sibling/negative-control audit: Verified consistency checkers reject stale or tampered projections.
4. Focused tests & preflight: Local `run_policy_preflight.py` passed (compile, lint, focused tests, evidence consistency, self-check).
5. Exact-head CI: Verified via GitHub Actions checks.

---

## 14. Next Safe Action

Preserve **`NOT_ESTABLISHED`**. Do not attempt to run un-enforced trials or infer compliance from un-isolated command streams. If empirical comparison is to be pursued in a future cycle, establish an independent trusted enforcement capability investment (providing verified kernel sandbox isolation, independent control-plane integrity verification, and isolated network policy enforcement conforming to `policy-worker-boundary-v1`) before initiating model trial execution.
