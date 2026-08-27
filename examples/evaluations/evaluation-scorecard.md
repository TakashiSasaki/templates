# Small-model evaluation scorecard

Fill one score entry for every dimension in the machine-readable scorecard schema. Each entry has a status, an attribution, and concise evidence notes.

## Status vocabulary

- **PASS** — the model completed the dimension and the result matched the repository contract.
- **FAIL** — the model performed the relevant action, but the result violated the repository contract.
- **BLOCKED** — the dimension could not be exercised because a prerequisite or environment capability was unavailable.
- **NOT TESTED** — the dimension was not attempted or the transcript is insufficient to establish what happened.

Do not convert BLOCKED or NOT TESTED into PASS by inference. A blocked browser proof must remain a release-readiness blocker when the repository contract requires that proof.

## Attribution vocabulary

Use exactly one attribution for each dimension:

- **repository defect** — behavior is reproducibly wrong under a controlled consumer run;
- **documentation/discoverability defect** — the contract exists, but the public reader-facing path does not make it findable or understandable;
- **machine-contract defect** — schema, validator, projection, or executable contract is missing or inconsistent;
- **evaluator mistake** — the evaluator violated the documented workflow or altered the bytes/inputs incorrectly;
- **environment limitation** — the harness lacks a required browser, WebDriver, Git, network, or other capability;
- **evidence-capture limitation** — the run changed or lost evidence bytes/metadata after acquisition, so the claim cannot be trusted.

## Fixed dimensions

| Machine key | Human label | Evidence to record |
| --- | --- | --- |
| `entry_point_discovery` | Entry-point discovery | Site/default entry point and reader-facing path found |
| `machine_bootstrap_discovery` | Machine bootstrap discovery | Site-owned machine entry point and bootstrap operation found |
| `canonical_bootstrap_execution` | Canonical bootstrap execution | Exact verified installer argv used without reimplementation |
| `integrity_verification` | Integrity verification | Immutable identity and exact received-byte verification |
| `role_separation` | Installer / Skill / toolchain role separation | Each identity used for its declared role |
| `lifecycle_correctness` | Lifecycle correctness | VALID scaffold → product implementation → evidence → release readiness |
| `managed_generated_boundary` | Managed/generated boundary | Seed, managed, and generated files handled through the contract |
| `product_evidence_completion` | Product evidence completion | Planning/template evidence replaced by product evidence |
| `browser_proof_handling` | Browser proof handling | Generic prerequisite diagnosis and fail-closed deferred proof |
| `release_readiness_honesty` | Release-readiness honesty | Deferred or missing required proof never reported ready |
| `recovery_quality` | Recovery quality | Correct recovery from a failed or blocked step |
| `user_intervention` | User intervention | Count and necessity of interventions |
| `dead_ends` | Dead ends | Avoidable loops, bypasses, or premature completion |

For each dimension, cite the first decisive observation and whether the outcome is reproducible. Include the number of interventions and any dead end in the notes, even when the status is PASS.

## Rerun conditions

The scorecard must end with explicit conditions for the next independent run, such as a fresh conversation, a clean workspace outside the maintainer project, complete transcript capture, or a browser-enabled harness. The final empirical rerun is a future clean-room run by a separate fresh conversation and small model; this maintenance conversation is not an eligible evaluator.
