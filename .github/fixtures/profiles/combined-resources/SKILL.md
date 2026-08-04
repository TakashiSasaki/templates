---
name: policy-response-preparer
description: Review supplied facts against a bounded local policy, fill a maintained response asset, normalize the result with a private helper, and report the generated output path.
---

# Policy response preparer

## Purpose

Prepare a standardized policy-grounded response from supplied facts and normalize the completed text for deterministic comparison or delivery.

## Use this skill when

Use this skill when a proposed public contract must be reviewed against the local compatibility policy and returned in the repository's standard response format.

## Required inputs and prerequisites

Obtain the supplied contract facts, a caller-supplied staging path for the completed response, and a caller-supplied final output path. When the facts are provided in a file, treat that source as read-only. The facts source, staging path, and output path must refer to distinct files, including no hard-link or equivalent aliases.

## Operational knowledge

Reference: references/review-policy.md
Read when: evaluating the supplied contract facts and deciding whether compatibility or escalation concerns exist
Provides: required compatibility checks, evidence standards, and escalation conditions
Authority or freshness notes: this repository-maintained policy is authoritative for this fixture

## Assets

Asset: assets/response-template.txt
Use when: preparing the policy-grounded response after completing the review
Handling: copy the headings to the caller-supplied staging path, replace each bracketed field with supported findings, and remove unused optional lines
Must remain unchanged: heading order and the final verification heading

## Helper scripts

Script: scripts/normalize.rb
Run when: the staged completed response must be normalized before comparison or delivery
Exact invocation: ruby scripts/normalize.rb STAGING OUTPUT
Working directory: repository root
Inputs and arguments: STAGING is the caller-supplied file containing the completed UTF-8 response generated from the asset; OUTPUT is the distinct final destination path and must not alias STAGING
Stdout/result: prints the normalized output path after a successful write
Stderr/diagnostics: reports invalid arguments, aliased staging and output files, unreadable staging input, invalid UTF-8, or write failures
Exit status: zero on success and nonzero on validation or file-system failure
Files or external state modified: writes or replaces only the caller-supplied OUTPUT path; the supplied facts source and STAGING file remain unchanged
Network access: NONE
Required permissions: read access to the supplied facts and STAGING file and write access to OUTPUT
Automatic execution allowed: YES
Human confirmation required: NO
Idempotency and retry behavior: repeated execution with the same staging input produces identical output and may be retried after correcting a reported failure

## Workflow

1. Read the supplied contract facts without modifying their source and identify caller-visible changes, missing evidence, and authorization boundaries.
2. Read `references/review-policy.md` and map each finding to an applicable rule.
3. Open `assets/response-template.txt`, preserve its heading order, and fill it only with supported findings.
4. Save the completed UTF-8 response to the caller-supplied STAGING path, which must refer to a different file from both the supplied facts source and OUTPUT path.
5. Run `ruby scripts/normalize.rb STAGING OUTPUT` from the repository root and stop on a nonzero exit status.
6. Verify that the supplied facts and staged response are unchanged, verify the normalized response, and report the generated output path.

## Output requirements

Return the normalized response path and a policy-grounded response with no unfilled bracketed fields. Every compatibility conclusion must cite an applicable policy rule or state that evidence is insufficient.

## Validation

Confirm that every retained reference, asset, and helper was used according to its declaration; the heading order matches the asset; every finding maps to the policy; the supplied facts source and staging file are unchanged by normalization; and the output is valid UTF-8 with LF line endings, no trailing horizontal whitespace, and one final newline.

## Safety and approval

Do not fabricate missing facts, approve compatibility exceptions, disclose unauthorized information, modify the supplied facts source or staging file during normalization, use aliased files for facts, staging, and output, write outside the caller-supplied staging and output paths, or access the network.

Selected profiles: knowledge-augmented, asset-driven, script-assisted
