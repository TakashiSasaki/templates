---
name: exclusive-profile-regression
description: Intentionally invalid repository fixture proving that the instruction-only tag cannot be combined with another concrete profile.
---

# Exclusive profile regression

## Purpose

Provide a bounded repository fixture that must be rejected solely because the exclusive `instruction-only` tag is combined with another concrete profile.

## Use this skill when

Use this fixture only while testing profile-selection validation.

## Workflow

1. Read the supplied text without loading operational resources.
2. Return a concise factual summary.
3. Validate that no files or external systems were modified.

## Output requirements

Return a concise summary derived only from the supplied text.

## Validation

Confirm that the result is supported by the supplied text and that the repository contains no operational resource files or optional contracts.

## Safety and approval

Remain read-only and do not access the network or modify external state.

Selected profiles: instruction-only, knowledge-augmented
