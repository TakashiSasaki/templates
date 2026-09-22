# Trusted-Enforcement Feasibility Study and Investment Evaluation for Criteria C5, C7, and C8

**Document Status**: `COMPLETED` / `DECIDED`  
**Primary Recommendation**: **`DEFER_ENFORCEMENT_INVESTMENT`**  
**Architectural Direction**: **`SEPARATE_GENERAL_PLATFORM_PROJECT`**  
**Empirical Finding Preserved**: **`NOT_ESTABLISHED`**  
**Target Authority**: `policy`  
**Evaluation Baseline**: [`ed423a07c87929388dedee9b4cdff5a59b64bfb2`](https://github.com/TakashiSasaki/templates/commit/ed423a07c87929388dedee9b4cdff5a59b64bfb2)  
**Execution Environment**: Google Anti-Gravity / Gemini 3.8 Flash (Middle reasoning effort)  

---

## 1. Executive Summary

This study evaluates whether investing engineering resources to build a trusted execution and enforcement boundary for Criteria **C5** (opaque worker execution confinement), **C7** (independent network policy enforcement), and **C8** (trusted trial identity binding) is justified within the `policy` repository, versus preserving the current empirical result of **`NOT_ESTABLISHED`**.

Following the landed Policy baseline (`ac95d6ee681ef422c0a8e1f714e94fbc78ff83aa`, PRs #997–#1002 merged), the implementation of the real Google Anti-Gravity (`agy`) worker backend (PR #1004, `3d05429778d091412a754e58e4773687e29116f7`), the qualification probe report (PR #1003, `58ce9ef0aa4dc1c31ab8862011ba12c3a508904e`), and the structured probe provenance binding (PR #1005, `56b74bcca510cf3894d71ddca88fb53600b2f40a`), the capability qualification status is:
- **C1, C2, C3, C4, C9**: `ESTABLISHED`
- **C6**: `NOT_APPLICABLE` (non-Git fixture mode)
- **C5, C7, C8**: `NOT_ESTABLISHED`
- **Capability Decision**: `NOT_QUALIFIED`
- **Matched Model Trials Run**: `0`
- **Whole-Task-Cost Classification**: `NOT_ESTABLISHED`

Based on technical characterization of the host environment, Linux kernel isolation mechanisms, the Antigravity sandbox daemon, and the architectural scope of the `policy` template (ADR 0003, ADR 0005), this evaluation concludes:

1. **Explicit Recommendation**: **`DEFER_ENFORCEMENT_INVESTMENT`** within the `policy` repository.
2. **Architectural Placement**: Low-level operating system virtualization, container runtimes, and network packet isolation do not belong inside the application-neutral `policy` template. Any future investment in trusted agent sandboxing must be scoped to a **`SEPARATE_GENERAL_PLATFORM_PROJECT`**.
3. **Scientific Action**: Maintain the predeclared stopping rule and preserve **`NOT_ESTABLISHED`**. Do not execute un-isolated model trials.

---

## 2. Landed Baseline and Qualification Status

The qualification probe (`probe-agy-gemini38flash-20260922t064419z`) evaluated the real Google Anti-Gravity CLI (`agy` v1.2.8) with `gemini-3.8-flash-medium` against the predeclared capability criteria C1–C9:

| Criterion | Requirement | Qualification Status | Evidence Basis |
| :--- | :--- | :--- | :--- |
| **C1** | Worker startup | `ESTABLISHED` | `agy` CLI v1.2.8 initialized cleanly non-interactively using `--mode accept-edits --output-format stream-json`, exiting with code 0. |
| **C2** | Tool/workspace reachability | `ESTABLISHED` | Worker reached the workspace boundary, emitting structured `step_update` events in `stream-json`. |
| **C3** | Harmless workspace action | `ESTABLISHED` | Worker executed a single read-only `view_file` on `/tmp/test.txt` (11 bytes, exit code 0, SHA-256 verified invariant). Bound with machine-readable fields in PR #1005. |
| **C4** | Evaluator observation | `ESTABLISHED` | Evaluator captured and verified structured tool events, parameters, and results. |
| **C5** | Opaque execution confinement | `NOT_ESTABLISHED` | Host lacks an active sandbox daemon (`connection reset by peer`), unprivileged user namespaces, or seccomp supervision. Worker ran unsandboxed. |
| **C6** | Control-plane integrity | `NOT_APPLICABLE` | Evaluated against a non-Git fixture where `.git` absence was explicitly verified. |
| **C7** | Independent network enforcement | `NOT_ESTABLISHED` | Host lacks per-process network namespace (`CLONE_NEWNET`) or firewall packet filtering to independently verify external egress isolation. |
| **C8** | Trusted identity binding | `NOT_ESTABLISHED` | Evaluator-owned witness conforming to `policy-worker-boundary-v1` cannot be truthfully emitted because C5 and C7 are absent. |
| **C9** | Token usage observability | `ESTABLISHED` | Complete whole-task token usage reported in `result` event (`input_tokens`: 22,505, `output_tokens`: 258, `total_tokens`: 22,763). |

Under the predeclared protocol, a decision of `NOT_QUALIFIED` triggers the immediate stopping rule: zero model trials were authorized or run, preserving 100% of the trial budget and eliminating un-enforced observations.

---

## 3. Deep Technical Feasibility Analysis

### 3.1 Criterion C5: Opaque Worker Execution Confinement

#### What a Minimal Trusted Boundary for `agy` Requires
To satisfy C5, an opaque agent worker (which runs an LLM that generates arbitrary shell commands and file mutations) must execute inside an operating system confinement boundary that enforces:
1. **Process Supervision**: Strict confinement of the worker process tree, preventing fork bombs, background daemon detachment, or escape from process tracking.
2. **Filesystem Confinement**:
   - The root filesystem (`/`) must be mounted read-only.
   - Writable storage must be strictly restricted to a temporary in-memory `tmpfs` or isolated scratch fixture directory.
   - Host sensitive files and directories must be masked or unmounted: `.bare/` Git storage, parent worktrees, SSH keys, cloud credentials (`~/.gemini/antigravity-cli`, `~/.config/gcloud`), and local IPC sockets.
3. **Syscall Filtering**: Seccomp-bpf profile denying high-privilege syscalls (`ptrace`, `bpf`, `unshare`, `clone` without namespaces, `keyctl`, `mount`).

#### Host and Runtime Prerequisites
Providing this boundary on Linux requires one of:
- Linux unprivileged user namespaces (`kernel.unprivileged_userns_clone = 1` and `kernel.apparmor_restrict_unprivileged_userns = 0`);
- A setuid root helper binary (such as classic `bwrap` / Bubblewrap);
- A running container daemon (Docker, containerd, or Podman) with host root / daemon socket access;
- Or hardware virtualization / microVMs (e.g. Firecracker, gVisor `runsc`, Cloud Hypervisor).

#### Characterization of Antigravity Sandbox Mode (`agy --sandbox`)
The Google Anti-Gravity CLI supports a `--sandbox` flag. When executed in the host environment, invoking `agy --sandbox` fails immediately with:
```text
connecting to sandbox server: read unix @->@: recvmsg: connection reset by peer
```
Investigation reveals:
- The `agy` sandbox client attempts to connect to a local abstract Unix domain socket (`@->@`) managed by an Antigravity sandbox daemon.
- In this host execution environment (an unprivileged Linux container without access to the host kernel's nested user namespace features), the sandbox daemon cannot initialize its isolation supervisor.
- Because the supervisor crashes or closes the socket upon connection, the worker cannot execute with `--sandbox`.
- To allow the capability probe to run at all, `--sandbox` had to be bypassed (`positive_probe_used_trusted_sandbox: false`), confirming that C5 cannot be satisfied via Antigravity's built-in sandbox on this host.

#### External Supervisor Feasibility
Attempting to wrap `agy` in an external sandbox supervisor (such as `bwrap` or a rootless container) within the current environment encounters the same barrier:
- The container environment restricts `CLONE_NEWUSER` and filesystem remounting (`EPERM` / `Operation not permitted`).
- No setuid sandbox binaries are installed or permitted.
- Therefore, C5 cannot be satisfied on this host without elevating host privileges or migrating the execution environment to a bare-metal or KVM-backed virtual machine.

---

### 3.2 Criterion C7: Independent Network Policy Enforcement

#### What C7 Requires
Criterion C7 requires independent, verifiable, tamper-proof isolation of the worker process from external networks during trial execution.

#### Distinction Between Application-Level Denial and Kernel-Level Enforcement
It is critical to distinguish between application-level soft constraints and true kernel-level enforcement:
- **Application-Level Denial (Insufficient for C7)**:
  - Agent system prompts stating *"Do not use network access"* or *"Work locally only"*;
  - Non-interactive tool confirmation policies (e.g. `--mode accept-edits` refusing to spawn browser tools);
  - Evaluator post-hoc inspection of observed tool events.
  These mechanisms do not prevent an opaque worker executing shell commands (e.g. `curl`, `nc`, `python -c "import socket..."`) from establishing network connections.
- **Kernel-Level Enforcement (Required for C7)**:
  - The worker process tree must be placed in an isolated network namespace (`unshare -n` / `CLONE_NEWNET`) with only the loopback interface (`lo`) or no interfaces at all.
  - Or kernel packet filter rules (`iptables`, `nftables`, or eBPF cgroup filters) must drop all egress packets originating from the worker UID or cgroup.

#### Host Reality
Creating a private network namespace requires `CAP_NET_ADMIN` or unprivileged user namespace cloning (`CLONE_NEWUSER | CLONE_NEWNET`). Configuring firewall packet drops requires `CAP_NET_ADMIN`. Neither capability is granted in the current container execution environment. Consequently, C7 cannot be independently established on this host.

---

### 3.3 Criterion C8: Trusted Trial Identity Binding and Witness

#### Specification of `policy-worker-boundary-v1`
Criterion C8 requires generating an evaluator-owned witness record conforming to schema `policy-worker-boundary-v1`:

```json
{
  "schema": "policy-worker-boundary-v1",
  "trial_id": "<unique-trial-id>",
  "reference_digest": "<sha256-of-task-reference-root>",
  "infrastructure_revision": "3d05429778d091412a754e58e4773687e29116f7",
  "agy_identity": "/home/ubuntu/.local/bin/agy (v1.2.8, sha256: f71174a3...)",
  "model_runtime_identity": "gemini-3.8-flash-medium",
  "sandbox_enforcement_identity": "<supervisor-id-and-status>",
  "network_enforcement_identity": "<netns-or-firewall-status>",
  "run_log_identity": "<sha256-of-supervisor-event-log>",
  "opaque_worker_code": "enforced",
  "control_plane_integrity": "verified",
  "network_policy": "enforced"
}
```

#### Evaluator Ownership and Tamper-Proofing
- The witness must be produced directly by an independent supervisor process that runs outside the worker's address space, filesystem root, and process group.
- The worker must have no write access to the witness file or supervisor log.
- Any discrepancy between the reference digest, infrastructure revision, or runtime logs immediately invalidates the trial.

#### Why C8 Remains Unestablished
C8 is an attestation of C5, C6, and C7. Because C5 (confinement) and C7 (network isolation) are unestablished on this host, an evaluator cannot truthfully emit `"opaque_worker_code": "enforced"` or `"network_policy": "enforced"`. Emitting such a witness without the underlying kernel isolation would constitute false attestation and compromise the evaluation contract.

---

## 4. Architectural Boundary: Policy Template vs Platform Layer

A foundational question is whether trusted sandbox enforcement belongs inside the `policy` repository at all.

### 4.1 Canonical Scope of the `policy` Template
The `policy` repository is governed by clear architectural decisions:
- **ADR 0003: Application-Neutral Policy Scope**: The policy repository is an application-neutral engine for defining, generating, and validating agent operational rules across heterogeneous workflows.
- **ADR 0005: Single Policy Authority**: It serves as the single authority for policy concepts, contracts, and delivery formats (`agents-md`, `agents-md-staged`).

Its core concerns are:
1. Defining machine-readable policies (`.agent-policy.yml`, catalog, schemas);
2. Rendering policies into human- and agent-readable instructions (`AGENTS.md`);
3. Validating workspace conformance against established invariants;
4. Packaging policy libraries for distribution (`takashisasaki_agent_policy` wheel).

### 4.2 Non-Scope: OS Virtualization and Container Orchestration
Operating system-level container orchestration, kernel security modules, eBPF probes, and network namespace managers:
- Are **not** application-neutral policy logic;
- Introduce severe platform and architecture coupling (e.g. Linux x86_64 vs aarch64 vs macOS Darwin);
- Require elevated host privileges (`CAP_SYS_ADMIN`, `CAP_NET_ADMIN`, root);
- Balloon the testing and maintenance surface of `policy` with kernel-version-dependent virtualization scripts.

Attempting to build a bespoke container/namespace sandbox directly inside `policy` would violate the repository's architectural separation of concerns. Trusted enforcement belongs in an external runner or testbed platform.

---

## 5. Comparative Evaluation of Strategic Options

Three strategic paths are evaluated:

| Dimension | Option A: Defer Enforcement Investment (`DEFER_ENFORCEMENT_INVESTMENT`) | Option B: Minimal Boundary in `policy` (`INVEST_MINIMAL_BOUNDARY`) | Option C: Separate Platform Project (`SEPARATE_GENERAL_PLATFORM_PROJECT`) |
| :--- | :--- | :--- | :--- |
| **Scope & Placement** | Retain current baseline; record feasibility in `policy`; do not write OS virtualization code. | Construct minimal custom bwrap / netns wrapper scripts inside `policy/scripts/`. | Build a dedicated, reusable agent sandboxing harness in a separate platform/runner repository. |
| **Host Feasibility** | **100% Feasible**. Fully compatible with current container host. | **Infeasible**. Blocked by host container socket error and namespace restrictions. | **Feasible on Dedicated Host**. Deployed on KVM/microVM or bare-metal CI runner. |
| **Implementation Complexity** | Zero implementation needed. | High. Requires custom C/Python namespace wrappers, seccomp filters, and socket mocks. | High. Comprehensive microVM/container orchestration lifecycle. |
| **Maintenance Burden** | Zero ongoing maintenance overhead. | High & Fragile. Constant breakage across different developer environments and host kernels. | Moderate. Amortized across all agent experiments across the organization. |
| **Security Posture** | **Sound**. No un-isolated code executed; zero risk of false compliance. | **Poor / Fragile**. Minimal custom sandboxes frequently permit escapes. | **Robust**. Standardized hypervisor/gVisor isolation boundary. |
| **Estimated Time to Valid Trials** | Immediate closure of current phase. | 2–4 weeks (blocked on host privileges and debugging). | 4–8 weeks (standard platform engineering cycle). |
| **Architectural Cleanliness** | **High**. Preserves ADR 0003 and ADR 0005 boundary. | **Unacceptable**. Pollutes policy template with OS-level virtualization. | **High**. Clear decoupling between policy rules and execution harness. |
| **Scientific Value** | **High**. Clear, durable, honest negative capability record. | Low. Compromised by environment-specific workarounds. | High. Long-term platform for reproducible agent research. |

---

## 6. Authoritative Decision and Recommendation

### 6.1 Explicit Category Decision

The authoritative decision for the `policy` repository is:

# **`DEFER_ENFORCEMENT_INVESTMENT`**

### 6.2 Architectural Directive

Any future engineering investment in trusted agent confinement and network isolation must be undertaken as a:

# **`SEPARATE_GENERAL_PLATFORM_PROJECT`**

### 6.3 Detailed Justification

1. **Host Reality**: The current container host cannot support kernel-level user namespaces, network namespaces, or the Antigravity sandbox daemon without elevated host privileges. Any attempt to implement C5/C7 inside this container is technically blocked.
2. **Architectural Purity**: Embedding low-level virtualization and network packet filtering into `policy` violates the core mandate of an application-neutral policy template (ADR 0003). Sandboxing is a platform infrastructure concern, not a policy specification concern.
3. **Scientific and Empirical Rigor**: Preserving **`NOT_ESTABLISHED`** maintains absolute scientific integrity. In accordance with the decision hierarchy (1. trial validity → 2. task correctness → 3. policy compliance → 4. whole-task cost), no trials should be run when validity cannot be certified. Honoring the stopping rule is a successful demonstration of research governance.
4. **Operational Economy**: The staged-delivery prototype is opt-in and not adopted in production. Diverting extensive engineering resources to build a bespoke kernel supervisor for a prototype delivery mechanism is economically unwarranted.

---

## 7. Invariants Maintained and Revisit Conditions

### 7.1 Preserved Invariants
- **Default Instruction Renderer**: Full-text `agents-md` remains the default, authoritative delivery mechanism.
- **Staged Delivery Adoption**: Staged delivery (`agents-md-staged`) remains unadopted, unpromoted, and unpinned.
- **Trial Budget Preservation**: Zero un-isolated model trials were executed; no synthetic or estimated cost data was fabricated.
- **Stopping Rule**: The predeclared stopping rule was strictly respected.

### 7.2 Revisit Triggers
This evaluation should only be reopened if all of the following conditions are met:
1. **Certified Execution Infrastructure**: A dedicated execution environment (e.g. KVM microVM, gVisor container runtime, or privileged CI runner) providing verified kernel namespace isolation and packet filtering becomes available.
2. **Independent Platform Runner**: A separate platform project delivers an evaluator-certified supervisor capable of emitting valid `policy-worker-boundary-v1` witnesses.
3. **Strategic Delivery Priority**: The project leadership explicitly prioritizes whole-task-cost empirical comparison for instruction delivery.

### 7.3 Next Safe Action
Preserve **`NOT_ESTABLISHED`**. Maintain the landed Policy baseline (`ac95d6ee681ef422c0a8e1f714e94fbc78ff83aa`), conclude the staged Policy-delivery capability qualification, and proceed with normal canonical policy authoring and validation workflows.
