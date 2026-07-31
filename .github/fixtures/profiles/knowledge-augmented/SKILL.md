---
name: contract-review-guide
description: Review a proposed public contract against a bounded local policy and report compatibility or escalation concerns.
---

# Contract review guide

## Purpose

Evaluate a proposed public contract using the repository's maintained review policy.

## Use this skill when

Use this skill when a change introduces or modifies caller-visible behavior and the local compatibility policy applies.

## Operational knowledge

Reference: references/review-policy.md
Read when: evaluating a proposed public contract or compatibility change
Provides: required compatibility checks, evidence standards, and escalation conditions
Authority or freshness notes: this repository-maintained policy is authoritative for this fixture

## Workflow

1. Read the proposed contract and identify caller-visible changes.
2. Read `references/review-policy.md`.
3. Compare the proposal with every applicable policy rule.
4. Report compliant points, violations, and any required escalation.

## Output requirements

Return a policy-grounded review that cites the applicable rule for every finding.

## Validation

Confirm that the policy file was read and that each conclusion maps to an explicit rule or stated absence of evidence.

## Safety and approval

Do not approve exceptions or compatibility breaks; identify them for an authorized maintainer.

Selected profiles: knowledge-augmented
