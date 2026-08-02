---
name: policy-response-preparer
description: Review supplied facts against a bounded local policy, fill a maintained response asset, normalize the result with a private helper, and report the generated output path.
---

# Policy response preparer

## Purpose

Prepare a standardized policy-grounded response from supplied facts and normalize the completed text for deterministic comparison or delivery.

## Use this skill when

Use this skill when a proposed public contract must be reviewed against the local compatibility policy and returned in the repository's standard response format.

## Operational knowledge

Reference: references/review-policy.md
Read when: evaluating the supplied contract facts and deciding whether compatibility or escalation concerns exist
Provides: required compatibility checks, evidence standards, and escalation conditions
Authority or freshness notes: this repository-maintained policy is authoritative for this fixture

## Assets

Asset: assets/response-template.txt
Use when: preparing the policy-grounded response after completing the review
Handling: copy the headings, replace each bracketed field with supported findings, and remove unused optional lines
Must remain unchanged: heading order and the final verification heading

## Helper scripts

Script: scripts/normalize.rb
Run when: the completed response must be normalized before comparison or delivery
Exact invocation: ruby scripts/normalize.rb INPUT OUTPUT
Working directory: repository root
Inputs and arguments: INPUT is the completed UTF-8 response and OUTPUT is the destination path
Stdout/result: prints the normalized output path after a successful write
Stderr/diagnostics: reports invalid arguments, unreadable input, invalid UTF-8, or write failures
Exit status: zero on success and nonzero on validation or file-system failure
Files or external state modified: writes or replaces only the caller-supplied OUTPUT path
Network access: NONE
Required permissions: read access to INPUT and write access to OUTPUT
Automatic execution allowed: YES
Human confirmation required: NO
Idempotency and retry behavior: repeated execution with the same input produces identical output and may be retried after correcting a reported failure

## Workflow

1. Read the supplied contract facts and identify caller-visible changes, missing evidence, and authorization boundaries.
2. Read `references/review-policy.md` and map each finding to an applicable rule.
3. Open `assets/response-template.txt`, preserve its heading order, and fill it only with supported findings.
4. Save the completed UTF-8 response to the caller-supplied input path for normalization.
5. Run `ruby scripts/normalize.rb INPUT OUTPUT` from the repository root and stop on a nonzero exit status.
6. Verify the normalized response and report the generated output path.

## Output requirements

Return the normalized response path and a policy-grounded response with no unfilled bracketed fields. Every compatibility conclusion must cite an applicable policy rule or state that evidence is insufficient.

## Validation

Confirm that every retained reference, asset, and helper was used according to its declaration; the heading order matches the asset; every finding maps to the policy; and the output is valid UTF-8 with LF line endings, no trailing horizontal whitespace, and one final newline.

## Safety and approval

Do not fabricate missing facts, approve compatibility exceptions, disclose unauthorized information, modify the input file, write outside the caller-supplied output path, or access the network.

Selected profiles: knowledge-augmented, asset-driven, script-assisted
