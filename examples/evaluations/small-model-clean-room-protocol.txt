# Small-model clean-room evaluation protocol

This protocol defines a separate empirical evaluation of the public consumer experience. It is not a report of this maintenance work, and the current maintenance conversation must never be described as a clean-room run because it already contains repository knowledge.

## Isolation requirements

The evaluator must:

- start a fresh conversation with a fresh small coding model/session;
- run outside the repository maintainer's project and workspace;
- provide no previous reports, transcripts, artifacts, patches, or evaluator hints;
- avoid putting repository-specific commit SHAs, authority branch names, or entry-point paths in the prompt;
- provide only the neutral product task, the repository URL needed to locate the public target, and the success/reporting requirements;
- record any inherited system, project, workspace, repository-local, or tool instructions before interpreting the result.

The evaluator may not silently remove an inherited instruction. If an inherited instruction changes Git usage, network access, browser access, file locations, or user interaction, record it as part of the environment fingerprint and classify its impact.

## Run record

Capture the following before product work begins:

- evaluation identifier, date/time, model and session identifier;
- maintainer-project/workspace isolation confirmation;
- available tools and capabilities, without secrets;
- Git availability and whether Git operations were allowed;
- browser availability, WebDriver availability, and any browser sandbox limitations;
- network policy, allowed hosts, proxy restrictions, and offline constraints;
- operating system/runtime details relevant to the task;
- inherited instruction sources and a short impact note;
- user intervention count at each intervention, including what information or action was supplied.

The evaluator should retain the complete transcript, tool outputs, generated files, and final report. Redact credentials and unrelated private data without removing evidence needed to understand a failure.

## Required outcome record

The final report must distinguish:

- repository defect;
- documentation or discoverability defect;
- machine-contract defect;
- evaluator mistake;
- environment limitation;
- evidence-capture limitation.

For every failed or blocked item, record the first observed symptom, the exact action that exposed it, whether the same result is reproducible in an isolated control environment, and the release-readiness impact. A harness or environment limitation must not be rewritten as a repository defect merely because the product could not be exercised.

Record separately:

- entry-point discovery;
- canonical bootstrap discovery and execution;
- integrity verification from the exact received bytes;
- scaffold validation;
- product implementation;
- product evidence population;
- product-state validation;
- browser-proof prerequisite status;
- release-readiness status;
- recovery attempts, dead ends, and user interventions.

A successful scaffold validation is only a scaffold milestone. Product code alone is not implementation evidence, and planning/template evidence must not be reported as product evidence. Deferred required browser proof keeps release readiness NOT READY.

## Transcript completeness

The report must state one of:

- **complete** — the transcript and relevant tool outputs are available from the first prompt through the final report;
- **partial** — identify the missing interval and why it is unavailable;
- **unavailable** — explain why no transcript could be retained.

If the transcript is partial or unavailable, mark claims relying on the missing interval as NOT TESTED or BLOCKED rather than inferred PASS.

## Reproduction and attribution

After the run, replay only the minimum failing step in a separate maintainer-controlled diagnostic environment. Do not feed the clean-room model's report or artifacts into that replay. Compare the two records to separate:

- a repository behavior reproducible under controlled conditions;
- a discoverability or prompt-sequencing issue;
- a clean-room evaluator mistake;
- a missing capability or sandbox restriction in the harness;
- a byte-capture or serialization error.

The clean-room run is complete only when the scorecard records every requested dimension as PASS, FAIL, BLOCKED, or NOT TESTED and lists the next conditions for a future rerun.
